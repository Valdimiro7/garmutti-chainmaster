from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from procurement.models import (
    Cliente,
    Factura,
    Moeda,
    Recibo,
    PagamentoHistorico,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_decimal(value, default='0'):
    try:
        return Decimal(str(value or default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _generate_recibo_number():
    """Formato REC-001/2025"""
    year = timezone.now().year
    suffix = f'/{year}'
    ultimo = (
        Recibo.objects
        .filter(numero__endswith=suffix)
        .order_by('-id')
        .first()
    )
    seq = 1
    if ultimo and ultimo.numero:
        try:
            seq = int(ultimo.numero.split('-')[1].split('/')[0]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f'REC-{seq:03d}/{year}'


def _get_organizacao():
    try:
        from procurement.models import Organizacao
        return Organizacao.objects.filter(activo=True).order_by('id').first()
    except Exception:
        return None


def _get_factura_payment_context(factura):
    """
    Contexto financeiro da factura baseado no histórico de pagamentos da PO
    e nos recibos já emitidos.

    Regras:
    - Só pode emitir recibo se existir histórico de pagamento da PO.
    - Recibo não pode ultrapassar o valor já pago no histórico e ainda não coberto por recibos.
    - Se a factura estiver com estado 'Paga' (id=2), saldo da factura = 0.
    """
    total_historico_pagamento = Decimal('0')
    pagamento_id = None

    if factura.purchase_order_id:
        pagamento = getattr(factura.purchase_order, 'pagamento', None)
        if pagamento:
            pagamento_id = pagamento.id
            total_historico_pagamento = (
                PagamentoHistorico.objects
                .filter(pagamento_id=pagamento.id)
                .aggregate(t=Sum('valor_pago'))
                .get('t') or Decimal('0')
            )

    total_recibado = (
        Recibo.objects
        .filter(factura_id=factura.id, anulado=False)
        .aggregate(t=Sum('valor_recebido'))
        .get('t') or Decimal('0')
    )

    tem_historico_pagamento = total_historico_pagamento > 0

    # Quanto já foi pago no histórico mas ainda não transformado em recibo
    valor_disponivel_para_recibo = total_historico_pagamento - total_recibado
    if valor_disponivel_para_recibo < 0:
        valor_disponivel_para_recibo = Decimal('0')

    # Saldo da factura
    if factura.estado_id == 2:  # Paga
        saldo_factura = Decimal('0')
    else:
        saldo_factura = factura.total - total_historico_pagamento
        if saldo_factura < 0:
            saldo_factura = Decimal('0')

    return {
        'pagamento_id': pagamento_id,
        'tem_historico_pagamento': tem_historico_pagamento,
        'total_historico_pagamento': total_historico_pagamento,
        'total_recibado': total_recibado,
        'valor_disponivel_para_recibo': valor_disponivel_para_recibo,
        'saldo_factura': saldo_factura,
    }


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
@require_GET
def recibos_view(request):
    recibos = (
        Recibo.objects
        .select_related('factura', 'factura__purchase_order', 'cliente', 'moeda')
        .order_by('-id')
    )

    # Apenas facturas:
    # - Paga (id=2) ou Paga parcial (id=3)
    # - com PO
    # - com pagamento
    # - com histórico de pagamento
    facturas_qs = (
        Factura.objects
        .select_related('cliente', 'moeda', 'purchase_order', 'estado')
        .filter(
            estado_id__in=[2, 3],
            purchase_order__isnull=False,
            purchase_order__pagamento__isnull=False,
            purchase_order__pagamento__historico__isnull=False,
        )
        .distinct()
        .order_by('-id')
    )

    facturas = []
    for f in facturas_qs:
        ctx = _get_factura_payment_context(f)

        # Mostrar no dropdown apenas se existir histórico de pagamento
        # e houver valor disponível para novo recibo
        if ctx['tem_historico_pagamento'] and ctx['valor_disponivel_para_recibo'] > 0:
            f.valor_disponivel_para_recibo = ctx['valor_disponivel_para_recibo']
            f.total_historico_pagamento = ctx['total_historico_pagamento']
            f.total_recibado = ctx['total_recibado']
            f.saldo_factura = ctx['saldo_factura']
            facturas.append(f)

    moedas = Moeda.objects.filter(estado=True).order_by('codigo')
    today = timezone.localdate()

    total_recibos = recibos.count()
    total_anulados = recibos.filter(anulado=True).count()
    total_activos = total_recibos - total_anulados
    valor_total = (
        recibos.filter(anulado=False)
        .aggregate(t=Sum('valor_recebido')).get('t') or Decimal('0')
    )

    context = {
        'segment': 'recibos',
        'recibos': recibos,
        'facturas': facturas,
        'moedas': moedas,
        'total_recibos': total_recibos,
        'total_activos': total_activos,
        'total_anulados': total_anulados,
        'valor_total': valor_total,
        'default_numero': _generate_recibo_number(),
        'today': today.isoformat(),
        'formas_pagamento': [
            'Transferência Bancária',
            'Cheque',
            'Numerário',
            'Depósito Bancário',
            'Cartão',
            'Outro',
        ],
    }
    return render(request, 'recibos/recibos.html', context)


@login_required
@require_GET
def recibo_detail_json_view(request, recibo_id):
    recibo = get_object_or_404(
        Recibo.objects.select_related(
            'factura', 'factura__purchase_order',
            'factura__purchase_order__quotacao',
            'factura__cliente', 'factura__moeda',
            'cliente', 'moeda',
        ),
        id=recibo_id,
    )

    f = recibo.factura
    po = f.purchase_order if f else None

    factura_pdf_url = reverse('procurement:factura_pdf', args=[f.id]) if f else ''
    po_download_url = ''
    if po:
        from procurement.models import PurchaseOrderAnexo
        po_anexo = PurchaseOrderAnexo.objects.filter(
            purchase_order_id=po.id, tipo_anexo='po'
        ).first()
        if po_anexo:
            try:
                po_download_url = reverse('procurement:po_anexo_download', args=[po_anexo.id])
            except Exception:
                pass

    return JsonResponse({
        'id': recibo.id,
        'numero': recibo.numero,
        'anulado': recibo.anulado,
        'motivo_anulacao': recibo.motivo_anulacao or '',
        'factura_id': recibo.factura_id,
        'factura_numero': f.numero if f else '',
        'factura_total': str(f.total) if f else '0',
        'po_cliente_numero': po.po_cliente_numero if po else '',
        'po_numero': po.numero if po else '',
        'cliente_id': recibo.cliente_id,
        'cliente_nome': recibo.cliente.nome if recibo.cliente else '',
        'moeda_id': recibo.moeda_id or '',
        'moeda_simbolo': recibo.moeda.simbolo if recibo.moeda else 'Mt',
        'data_recibo': recibo.data_recibo.isoformat() if recibo.data_recibo else '',
        'valor_recebido': str(recibo.valor_recebido),
        'forma_pagamento': recibo.forma_pagamento or '',
        'referencia': recibo.referencia or '',
        'observacoes': recibo.observacoes or '',
        'factura_pdf_url': factura_pdf_url,
        'po_download_url': po_download_url,
        'pdf_url': reverse('procurement:recibo_pdf', args=[recibo.id]),
    })


@login_required
@require_GET
def factura_info_json_view(request, factura_id):
    """
    Devolve dados da factura para pré-preencher o modal de recibo.
    Agora baseado no histórico de pagamentos da PO.
    """
    f = get_object_or_404(
        Factura.objects.select_related(
            'cliente', 'moeda', 'purchase_order', 'estado', 'purchase_order__pagamento'
        ),
        id=factura_id,
    )

    ctx = _get_factura_payment_context(f)

    return JsonResponse({
        'factura_id': f.id,
        'factura_numero': f.numero,
        'factura_total': str(f.total),
        'cliente_id': f.cliente_id,
        'cliente_nome': f.cliente.nome if f.cliente else '',
        'moeda_id': f.moeda_id or '',
        'moeda_codigo': f.moeda.codigo if f.moeda else '',
        'moeda_simbolo': f.moeda.simbolo if f.moeda else 'Mt',
        'po_cliente_numero': f.purchase_order.po_cliente_numero if f.purchase_order else '',
        'estado_id': f.estado_id,
        'estado_codigo': f.estado.codigo if f.estado else '',
        'estado_nome': f.estado.nome if f.estado else '',
        'tem_historico_pagamento': ctx['tem_historico_pagamento'],
        'total_historico_pagamento': str(ctx['total_historico_pagamento']),
        'valor_ja_recebido': str(ctx['total_recibado']),
        'valor_disponivel_para_recibo': str(ctx['valor_disponivel_para_recibo']),
        'saldo_pendente': str(ctx['saldo_factura']),
    })


@login_required
@require_POST
@transaction.atomic
def recibo_create_view(request):
    try:
        factura_id = request.POST.get('factura_id', '').strip()
        moeda_id = request.POST.get('moeda_id', '').strip() or None
        data_recibo = request.POST.get('data_recibo', '').strip()
        valor_recebido = _parse_decimal(request.POST.get('valor_recebido', '0'))
        forma_pagamento = request.POST.get('forma_pagamento', '').strip() or None
        referencia = request.POST.get('referencia', '').strip() or None
        observacoes = request.POST.get('observacoes', '').strip() or None

        if not factura_id:
            return JsonResponse({'success': False, 'message': 'Seleccione a factura.'}, status=400)
        if valor_recebido <= 0:
            return JsonResponse({'success': False, 'message': 'O valor recebido deve ser maior que zero.'}, status=400)
        if not data_recibo:
            return JsonResponse({'success': False, 'message': 'Indique a data do recibo.'}, status=400)

        factura = get_object_or_404(
            Factura.objects.select_related(
                'cliente', 'moeda', 'estado', 'purchase_order', 'purchase_order__pagamento'
            ),
            id=factura_id
        )

        # Só pode emitir recibo para facturas Paga ou Paga parcial
        if factura.estado_id not in [2, 3]:
            return JsonResponse({
                'success': False,
                'message': 'Só é permitido emitir recibo para facturas com estado Paga ou Paga Parcial.'
            }, status=400)

        # Factura precisa de estar ligada a uma PO e a um pagamento
        if not factura.purchase_order_id:
            return JsonResponse({
                'success': False,
                'message': 'Esta factura não está ligada a uma Purchase Order.'
            }, status=400)

        pagamento = getattr(factura.purchase_order, 'pagamento', None)
        if not pagamento:
            return JsonResponse({
                'success': False,
                'message': 'Esta factura não possui pagamento relacionado na PO.'
            }, status=400)

        ctx = _get_factura_payment_context(factura)

        # Não permitir recibo sem histórico de pagamento
        if not ctx['tem_historico_pagamento']:
            return JsonResponse({
                'success': False,
                'message': 'Não é permitido emitir recibo para esta factura porque a PO não possui histórico de pagamento.'
            }, status=400)

        # Não permitir ultrapassar o disponível vindo do histórico
        if ctx['valor_disponivel_para_recibo'] <= 0:
            return JsonResponse({
                'success': False,
                'message': 'Não existe valor disponível no histórico de pagamento para emitir novo recibo.'
            }, status=400)

        if valor_recebido > ctx['valor_disponivel_para_recibo']:
            return JsonResponse({
                'success': False,
                'message': (
                    f'O valor do recibo não pode ser maior que o valor disponível no histórico de pagamento '
                    f'({ctx["valor_disponivel_para_recibo"]}).'
                )
            }, status=400)

        recibo = Recibo.objects.create(
            numero=_generate_recibo_number(),
            factura_id=int(factura_id),
            cliente_id=factura.cliente_id,
            moeda_id=int(moeda_id) if moeda_id else factura.moeda_id,
            data_recibo=data_recibo,
            valor_recebido=valor_recebido,
            forma_pagamento=forma_pagamento,
            referencia=referencia,
            observacoes=observacoes,
            criado_por=request.user,
        )

        _update_factura_estado(factura)

        return JsonResponse({
            'success': True,
            'message': f'Recibo {recibo.numero} emitido com sucesso.',
            'recibo_id': recibo.id,
            'numero': recibo.numero,
            'pdf_url': reverse('procurement:recibo_pdf', args=[recibo.id]),
        })

    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Erro: {e}'}, status=500)


@login_required
@require_POST
def recibo_anular_view(request, recibo_id):
    recibo = get_object_or_404(Recibo, id=recibo_id)
    if recibo.anulado:
        return JsonResponse({'success': False, 'message': 'Recibo já está anulado.'}, status=400)

    motivo = request.POST.get('motivo', '').strip() or None
    recibo.anulado = True
    recibo.motivo_anulacao = motivo
    recibo.save(update_fields=['anulado', 'motivo_anulacao', 'actualizado_em'])

    factura = Factura.objects.select_related('estado').filter(id=recibo.factura_id).first()
    if factura:
        _update_factura_estado(factura)

    return JsonResponse({'success': True, 'message': f'Recibo {recibo.numero} anulado.'})


@login_required
@require_GET
def recibo_pdf_view(request, recibo_id):
    from weasyprint import HTML

    recibo = get_object_or_404(
        Recibo.objects.select_related(
            'factura', 'factura__purchase_order',
            'factura__purchase_order__quotacao',
            'cliente', 'moeda',
            'criado_por',
        ),
        id=recibo_id,
    )

    organizacao = _get_organizacao()

    html_string = render_to_string(
        'recibos/recibo_pdf.html',
        {'recibo': recibo, 'organizacao': organizacao},
        request=request,
    )

    pdf_file = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/'),
    ).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="Recibo_{recibo.numero.replace("/", "-")}.pdf"'
    )
    return response


# ---------------------------------------------------------------------------
# Helper interno — actualiza estado da factura com base nos recibos
# ---------------------------------------------------------------------------

def _update_factura_estado(factura):
    """
    Actualiza o estado da factura:
    - pendente
    - paga_parcial
    - paga

    Continua a usar os recibos activos como base.
    """
    from procurement.models import FacturaEstado

    total_recebido = (
        Recibo.objects
        .filter(factura_id=factura.id, anulado=False)
        .aggregate(t=Sum('valor_recebido')).get('t') or Decimal('0')
    )

    if total_recebido <= 0:
        codigo = 'pendente'
    elif total_recebido >= factura.total:
        codigo = 'paga'
    else:
        codigo = 'paga_parcial'

    estado = FacturaEstado.objects.filter(codigo=codigo).first()
    if estado and factura.estado_id != estado.id:
        factura.estado = estado
        factura.save(update_fields=['estado_id', 'actualizado_em'])