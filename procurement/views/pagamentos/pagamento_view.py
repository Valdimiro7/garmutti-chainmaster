from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import logging
import mimetypes
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from procurement.models import (
    Pagamento,
    PagamentoAnexo,
    PagamentoEstado,
    PurchaseOrder,
)

logger = logging.getLogger(__name__)


def _parse_decimal(value, default='0'):
    try:
        return Decimal(str(value or default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _generate_pagamento_number():
    year = timezone.now().year
    suffix = f'/{year}'
    ultimo = (
        Pagamento.objects
        .filter(numero__endswith=suffix)
        .order_by('-id')
        .first()
    )
    seq = 1
    if ultimo and ultimo.numero:
        try:
            seq = int(ultimo.numero.split('/')[0].split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f'PAY-{seq:03d}/{year}'


def _get_estado_pendente():
    estado = PagamentoEstado.objects.filter(codigo='pendente', activo=True).first()
    if not estado:
        raise ValueError('Estado "Pendente" não encontrado.')
    return estado


def _actualizar_saldo_e_estado(pagamento):
    valor_po = pagamento.valor_po or Decimal('0')
    valor_recebido = pagamento.valor_recebido or Decimal('0')
    saldo = valor_po - valor_recebido
    if saldo < 0:
        saldo = Decimal('0')

    pagamento.saldo_pendente = saldo

    estado_recebido = PagamentoEstado.objects.filter(codigo='recebido', activo=True).first()
    estado_parcial = PagamentoEstado.objects.filter(codigo='parcial', activo=True).first()
    estado_pendente = PagamentoEstado.objects.filter(codigo='pendente', activo=True).first()

    if valor_recebido <= 0:
        if estado_pendente:
            pagamento.estado = estado_pendente
    elif valor_recebido >= valor_po and estado_recebido:
        pagamento.estado = estado_recebido
    elif valor_recebido < valor_po and estado_parcial:
        pagamento.estado = estado_parcial


def _get_or_create_pagamento_from_po(po, user=None):
    pagamento = Pagamento.objects.filter(purchase_order_id=po.id).first()
    if pagamento:
        return pagamento

    pagamento = Pagamento(
        numero=_generate_pagamento_number(),
        purchase_order_id=po.id,
        estado=_get_estado_pendente(),
        cliente_id=po.cliente_id,
        moeda_id=po.moeda_id,
        valor_po=po.valor_total or Decimal('0'),
        valor_recebido=Decimal('0'),
        saldo_pendente=po.valor_total or Decimal('0'),
        criado_por=user,
    )
    pagamento.save()
    return pagamento


def _save_uploaded_files(request, pagamento):
    pop_files = request.FILES.getlist('pop_anexos')
    outros_files = request.FILES.getlist('outros_anexos')

    for f in pop_files:
        PagamentoAnexo.objects.create(
            pagamento_id=pagamento.id,
            tipo_anexo='pop',
            nome_ficheiro=f.name,
            ficheiro=f,
            observacao='POP',
        )

    for f in outros_files:
        PagamentoAnexo.objects.create(
            pagamento_id=pagamento.id,
            tipo_anexo='outro',
            nome_ficheiro=f.name,
            ficheiro=f,
            observacao='Outro anexo do pagamento',
        )


@login_required
@require_GET
def pagamentos_view(request):
    confirmed_pos = (
        PurchaseOrder.objects
        .select_related('cliente', 'moeda', 'estado', 'quotacao')
        .filter(estado__codigo='confirmada')
        .order_by('-id')
    )

    pagamentos_ids = set(
        Pagamento.objects.values_list('purchase_order_id', flat=True)
    )

    for po in confirmed_pos:
        if po.id not in pagamentos_ids:
            _get_or_create_pagamento_from_po(po, request.user)

    pagamentos = (
        Pagamento.objects
        .select_related('purchase_order', 'cliente', 'moeda', 'estado', 'purchase_order__quotacao')
        .prefetch_related('anexos')
        .order_by('-id')
    )

    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    total_pendentes = pagamentos.filter(estado__codigo='pendente').count()
    total_recebidos = pagamentos.filter(estado__codigo='recebido').count()

    valor_diario = (
        pagamentos.filter(
            estado__codigo__in=['recebido', 'parcial'],
            data_pagamento_recebido=today
        ).aggregate(total=Sum('valor_recebido')).get('total') or Decimal('0')
    )

    valor_semanal = (
        pagamentos.filter(
            estado__codigo__in=['recebido', 'parcial'],
            data_pagamento_recebido__gte=week_start,
            data_pagamento_recebido__lte=today
        ).aggregate(total=Sum('valor_recebido')).get('total') or Decimal('0')
    )

    valor_mensal = (
        pagamentos.filter(
            estado__codigo__in=['recebido', 'parcial'],
            data_pagamento_recebido__gte=month_start,
            data_pagamento_recebido__lte=today
        ).aggregate(total=Sum('valor_recebido')).get('total') or Decimal('0')
    )

    total_saldo_pendente = (
        pagamentos.aggregate(total=Sum('saldo_pendente')).get('total') or Decimal('0')
    )

    context = {
        'segment': 'pagamentos',
        'pagamentos': pagamentos,
        'total_pendentes': total_pendentes,
        'total_recebidos': total_recebidos,
        'valor_diario': valor_diario,
        'valor_semanal': valor_semanal,
        'valor_mensal': valor_mensal,
        'total_saldo_pendente': total_saldo_pendente,
        'today': today.isoformat(),
    }
    return render(request, 'pagamentos/pagamentos.html', context)


@login_required
@require_GET
def pagamento_detail_json_view(request, pagamento_id):
    pagamento = get_object_or_404(
        Pagamento.objects.select_related(
            'purchase_order', 'cliente', 'moeda', 'estado', 'purchase_order__quotacao'
        ),
        id=pagamento_id,
    )

    anexos = []
    for a in pagamento.anexos.all():
        anexos.append({
            'id': a.id,
            'tipo_anexo': a.tipo_anexo,
            'nome_ficheiro': a.nome_ficheiro,
            'observacao': a.observacao or '',
            'download_url': reverse('procurement:pagamentos_anexo_download', args=[a.id]),
        })

    data = {
        'id': pagamento.id,
        'numero': pagamento.numero,
        'purchase_order_id': pagamento.purchase_order_id,
        'purchase_order_numero': pagamento.purchase_order.numero if pagamento.purchase_order else '',
        'po_cliente_numero': pagamento.purchase_order.po_cliente_numero if pagamento.purchase_order else '',
        'quotacao_numero': pagamento.purchase_order.quotacao.numero if pagamento.purchase_order and pagamento.purchase_order.quotacao else '',
        'cliente_nome': pagamento.cliente.nome if pagamento.cliente else '',
        'estado_nome': pagamento.estado.nome if pagamento.estado else '',
        'estado_codigo': pagamento.estado.codigo if pagamento.estado else '',
        'moeda_simbolo': pagamento.moeda.simbolo if pagamento.moeda else '',
        'data_pagamento_prevista': pagamento.data_pagamento_prevista.isoformat() if pagamento.data_pagamento_prevista else '',
        'data_pagamento_recebido': pagamento.data_pagamento_recebido.isoformat() if pagamento.data_pagamento_recebido else '',
        'valor_po': str(pagamento.valor_po),
        'valor_recebido': str(pagamento.valor_recebido),
        'saldo_pendente': str(pagamento.saldo_pendente),
        'referencia_pagamento': pagamento.referencia_pagamento or '',
        'banco_origem': pagamento.banco_origem or '',
        'numero_transaccao': pagamento.numero_transaccao or '',
        'observacoes': pagamento.observacoes or '',
        'anexos': anexos,
    }
    return JsonResponse(data)


@login_required
@require_POST
@transaction.atomic
def update_pagamento_view(request, pagamento_id):
    pagamento = get_object_or_404(Pagamento, id=pagamento_id)

    try:
        pagamento.data_pagamento_prevista = request.POST.get('data_pagamento_prevista') or None
        pagamento.data_pagamento_recebido = request.POST.get('data_pagamento_recebido') or None
        pagamento.valor_recebido = _parse_decimal(request.POST.get('valor_recebido', '0'))
        pagamento.referencia_pagamento = request.POST.get('referencia_pagamento', '').strip() or None
        pagamento.banco_origem = request.POST.get('banco_origem', '').strip() or None
        pagamento.numero_transaccao = request.POST.get('numero_transaccao', '').strip() or None
        pagamento.observacoes = request.POST.get('observacoes', '').strip() or None

        _actualizar_saldo_e_estado(pagamento)
        pagamento.save()
        _save_uploaded_files(request, pagamento)

        messages.success(request, f'Pagamento "{pagamento.numero}" actualizado com sucesso.')
    except Exception:
        logger.exception("Erro ao actualizar pagamento %s", pagamento_id)
        messages.error(request, 'Ocorreu um erro ao actualizar o pagamento.')

    return redirect('procurement:pagamentos')


@login_required
@require_GET
def download_pagamento_anexo_view(request, anexo_id):
    anexo = get_object_or_404(PagamentoAnexo, id=anexo_id)

    if not anexo.ficheiro:
        raise Http404('Ficheiro não encontrado.')

    try:
        file_handle = anexo.ficheiro.open('rb')
    except Exception:
        logger.exception("Erro ao abrir anexo do pagamento %s", anexo_id)
        raise Http404('Ficheiro não encontrado.')

    content_type, _ = mimetypes.guess_type(anexo.nome_ficheiro or '')
    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=anexo.nome_ficheiro or os.path.basename(anexo.ficheiro.name),
        content_type=content_type or 'application/octet-stream'
    )