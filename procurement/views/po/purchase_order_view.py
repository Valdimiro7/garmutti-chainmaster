from datetime import date
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
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from procurement.models import (
    Cliente,
    Moeda,
    POEstado,
    PurchaseOrder,
    PurchaseOrderAnexo,
    Quotacao,
)

logger = logging.getLogger(__name__)


def _parse_decimal(value, default='0'):
    try:
        return Decimal(str(value or default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _generate_po_number():
    """
    Formato: PO-001/2026
    """
    year = timezone.now().year
    suffix = f'/{year}'
    ultimo = (
        PurchaseOrder.objects
        .filter(numero__endswith=suffix)
        .order_by('-id')
        .first()
    )

    seq = 1
    if ultimo and ultimo.numero:
        try:
            base = ultimo.numero.split('/')[0]
            seq = int(base.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1

    return f'PO-{seq:03d}/{year}'


def _get_estado_po_recebida():
    estado = POEstado.objects.filter(codigo='po_recebida', activo=True).first()
    if not estado:
        raise ValueError('Estado "PO Recebida" não encontrado.')
    return estado


def _get_estado_confirmada():
    return POEstado.objects.filter(codigo='confirmada', activo=True).first()


def _get_estado_cancelada():
    return POEstado.objects.filter(codigo='cancelada', activo=True).first()


@login_required
@require_GET
def purchase_orders_view(request):
    purchase_orders = (
        PurchaseOrder.objects
        .select_related('cliente', 'quotacao', 'moeda', 'estado', 'criado_por')
        .prefetch_related('anexos')
        .order_by('-id')
    )

    clientes = Cliente.objects.filter(estado=True).order_by('nome')
    moedas = Moeda.objects.filter(estado=True).order_by('-predefinida', 'codigo')

    # Sem "em_validacao"
    estados = (
        POEstado.objects
        .filter(activo=True)
        .exclude(codigo='em_validacao')
        .order_by('ordem', 'nome')
    )

    quotacoes = (
        Quotacao.objects
        .select_related('cliente', 'estado', 'moeda')
        .order_by('-id')
    )

    total = purchase_orders.count()
    total_recebida = purchase_orders.filter(estado__codigo='po_recebida').count()
    total_confirmada = purchase_orders.filter(estado__codigo='confirmada').count()
    total_cancelada = purchase_orders.filter(estado__codigo='cancelada').count()

    valor_total_recebida = (
        purchase_orders
        .filter(estado__codigo='po_recebida')
        .aggregate(total=Sum('valor_total'))
        .get('total') or Decimal('0')
    )

    valor_total_confirmada = (
        purchase_orders
        .filter(estado__codigo='confirmada')
        .aggregate(total=Sum('valor_total'))
        .get('total') or Decimal('0')
    )

    moeda_predefinida = moedas.filter(predefinida=True).first() or moedas.first()

    context = {
        'segment': 'purchase_orders',
        'purchase_orders': purchase_orders,
        'clientes': clientes,
        'moedas': moedas,
        'estados': estados,
        'quotacoes': quotacoes,

        'total': total,
        'total_recebida': total_recebida,
        'total_confirmada': total_confirmada,
        'total_cancelada': total_cancelada,

        'valor_total_recebida': valor_total_recebida,
        'valor_total_confirmada': valor_total_confirmada,

        'default_numero': _generate_po_number(),
        'today': date.today().isoformat(),
        'moeda_predefinida_id': moeda_predefinida.id if moeda_predefinida else '',
    }
    return render(request, 'purchase_orders/purchase_orders.html', context)


@login_required
@require_GET
def purchase_order_detail_json_view(request, po_id):
    po = get_object_or_404(
        PurchaseOrder.objects.select_related('cliente', 'quotacao', 'moeda', 'estado', 'criado_por'),
        id=po_id,
    )

    anexos = []
    for a in po.anexos.all():
        anexos.append({
            'id': a.id,
            'tipo_anexo': a.tipo_anexo,
            'nome_ficheiro': a.nome_ficheiro,
            'ficheiro': a.ficheiro.url if a.ficheiro else '',
            'observacao': a.observacao or '',
            'download_url': f'/purchase-orders/anexos/{a.id}/download/',
        })

    data = {
        'id': po.id,
        'numero': po.numero,
        'estado_id': po.estado_id,
        'estado_nome': po.estado.nome if po.estado else '',
        'estado_codigo': po.estado.codigo if po.estado else '',
        'quotacao_id': po.quotacao_id,
        'quotacao_numero': po.quotacao.numero if po.quotacao else '',
        'cliente_id': po.cliente_id,
        'cliente_nome': po.cliente.nome if po.cliente else '',
        'moeda_id': po.moeda_id,
        'moeda_codigo': po.moeda.codigo if po.moeda else '',
        'moeda_simbolo': po.moeda.simbolo if po.moeda else '',
        'po_cliente_numero': po.po_cliente_numero or '',
        'referencia_cliente': po.referencia_cliente or '',
        'data_po': po.data_po.isoformat() if po.data_po else '',
        'data_recebida': po.data_recebida.isoformat() if po.data_recebida else '',
        'valor_total': str(po.valor_total),
        'email_remetente': po.email_remetente or '',
        'assunto_email': po.assunto_email or '',
        'observacoes': po.observacoes or '',
        'criado_por': po.criado_por.get_full_name() if po.criado_por else '',
        'anexos': anexos,
        'pode_mudar_estado': (po.estado.codigo != 'confirmada') if po.estado else False,
    }
    return JsonResponse(data)


@login_required
@require_GET
def download_purchase_order_anexo_view(request, anexo_id):
    anexo = get_object_or_404(PurchaseOrderAnexo, id=anexo_id)

    if not anexo.ficheiro:
        raise Http404('Ficheiro não encontrado.')

    try:
        file_handle = anexo.ficheiro.open('rb')
    except Exception:
        logger.exception("Erro ao abrir anexo da PO %s", anexo_id)
        raise Http404('Ficheiro não encontrado.')

    content_type, _ = mimetypes.guess_type(anexo.nome_ficheiro or '')
    response = FileResponse(
        file_handle,
        as_attachment=True,
        filename=anexo.nome_ficheiro or os.path.basename(anexo.ficheiro.name),
        content_type=content_type or 'application/octet-stream'
    )
    return response


@login_required
@require_POST
@transaction.atomic
def create_purchase_order_view(request):
    try:
        po = _save_purchase_order(request, PurchaseOrder())
        messages.success(request, f'Purchase Order "{po.numero}" criada com sucesso.')
    except ValueError as e:
        logger.warning("Erro de validação ao criar PO: %s", e)
        messages.error(request, str(e))
    except Exception:
        logger.exception("Erro inesperado ao criar Purchase Order.")
        messages.error(request, 'Ocorreu um erro inesperado ao criar a Purchase Order.')
    return redirect('procurement:purchase_orders')


@login_required
@require_POST
@transaction.atomic
def update_purchase_order_view(request, po_id):
    po = get_object_or_404(PurchaseOrder, id=po_id)

    if po.estado and po.estado.codigo == 'confirmada':
        messages.error(request, 'PO confirmada não pode ser alterada.')
        return redirect('procurement:purchase_orders')

    try:
        po = _save_purchase_order(request, po)
        messages.success(request, f'Purchase Order "{po.numero}" actualizada com sucesso.')
    except ValueError as e:
        logger.warning("Erro de validação ao actualizar PO %s: %s", po_id, e)
        messages.error(request, str(e))
    except Exception:
        logger.exception("Erro inesperado ao actualizar Purchase Order %s.", po_id)
        messages.error(request, 'Ocorreu um erro inesperado ao actualizar a Purchase Order.')
    return redirect('procurement:purchase_orders')


@login_required
@require_POST
def change_estado_purchase_order_view(request, po_id):
    po = get_object_or_404(PurchaseOrder.objects.select_related('estado'), id=po_id)

    if po.estado and po.estado.codigo == 'confirmada':
        messages.error(request, 'PO confirmada não pode ter o estado alterado.')
        return redirect('procurement:purchase_orders')

    estado_id = request.POST.get('estado_id', '').strip()

    try:
        novo_estado = POEstado.objects.get(id=int(estado_id), activo=True)
    except (POEstado.DoesNotExist, ValueError):
        messages.error(request, 'Estado inválido.')
        return redirect('procurement:purchase_orders')

    # impedir usar estado em_validacao
    if novo_estado.codigo == 'em_validacao':
        messages.error(request, 'Estado inválido.')
        return redirect('procurement:purchase_orders')

    po.estado = novo_estado
    po.save(update_fields=['estado_id', 'actualizado_em'])
    messages.success(request, f'Estado da Purchase Order "{po.numero}" alterado para "{novo_estado.nome}".')
    return redirect('procurement:purchase_orders')


def _save_uploaded_files(request, po):
    po_files = request.FILES.getlist('po_anexos')
    email_files = request.FILES.getlist('email_anexos')

    for f in po_files:
        PurchaseOrderAnexo.objects.create(
            purchase_order_id=po.id,
            tipo_anexo='po',
            nome_ficheiro=f.name,
            ficheiro=f,
            observacao='Anexo da PO',
        )

    for f in email_files:
        PurchaseOrderAnexo.objects.create(
            purchase_order_id=po.id,
            tipo_anexo='email',
            nome_ficheiro=f.name,
            ficheiro=f,
            observacao='Conversa de email',
        )


def _save_purchase_order(request, po):
    POST = request.POST

    cliente_id = POST.get('cliente_id', '').strip()
    if not cliente_id:
        raise ValueError('Seleccione o cliente.')

    data_po = POST.get('data_po', '').strip()
    if not data_po:
        raise ValueError('Informe a data da PO.')

    is_new = not bool(po.pk)

    if is_new:
        po.numero = _generate_po_number()
        po.criado_por = request.user
        po.estado = _get_estado_po_recebida()

    quotacao_id = POST.get('quotacao_id', '').strip()
    po.cliente_id = int(cliente_id)
    po.quotacao_id = int(quotacao_id) if quotacao_id else None
    po.moeda_id = int(POST.get('moeda_id')) if POST.get('moeda_id') else None

    po.po_cliente_numero = POST.get('po_cliente_numero', '').strip() or None
    po.referencia_cliente = POST.get('referencia_cliente', '').strip() or None
    po.data_po = data_po
    po.data_recebida = POST.get('data_recebida') or None
    po.valor_total = _parse_decimal(POST.get('valor_total', '0'), '0')
    po.email_remetente = POST.get('email_remetente', '').strip() or None
    po.assunto_email = POST.get('assunto_email', '').strip() or None
    po.observacoes = POST.get('observacoes', '').strip() or None

    po.save()

    _save_uploaded_files(request, po)

    return po