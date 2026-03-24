from decimal import Decimal, InvalidOperation
import json
import logging
import os
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.template.loader import render_to_string

from weasyprint import HTML

from procurement.models import (
    Cliente,
    Factura,
    GuiaEntrega,
    GuiaEntregaItem,
    GuiaEstado,
    Moeda,
    PurchaseOrder,
)

logger = logging.getLogger(__name__)


def _parse_decimal(value, default='0'):
    try:
        return Decimal(str(value or default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _clean_nullable_fk(value):
    """
    Converte valores vazios ou textuais como 'null', 'None', 'undefined'
    para None. Mantém o valor original quando for válido.
    """
    if value is None:
        return None

    value = str(value).strip()

    if value in ['', 'null', 'None', 'undefined']:
        return None

    return value


def _generate_guia_number():
    year = timezone.now().year
    suffix = f'/{year}'
    ultimo = (
        GuiaEntrega.objects
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
    return f'GE-{seq:03d}/{year}'


def _get_estado_pendente():
    estado = GuiaEstado.objects.filter(codigo='pendente', activo=True).first()
    if not estado:
        raise ValueError('Estado "pendente" não encontrado.')
    return estado


def _save_itens(guia, itens_data):
    GuiaEntregaItem.objects.filter(guia_entrega_id=guia.id).delete()

    subtotal = Decimal('0')
    for i, item in enumerate(itens_data):
        descricao = (item.get('descricao') or '').strip()
        if not descricao:
            continue

        quantidade = _parse_decimal(item.get('quantidade', '1'), '1')
        preco_unit = _parse_decimal(item.get('preco_unit', '0'), '0')
        total_linha = (quantidade * preco_unit).quantize(Decimal('0.01'))

        GuiaEntregaItem.objects.create(
            guia_entrega_id=guia.id,
            descricao=descricao,
            unidade=(item.get('unidade') or '').strip() or None,
            quantidade=quantidade,
            preco_unit=preco_unit,
            total_linha=total_linha,
            ordem=i,
        )
        subtotal += total_linha

    if guia.subtotal != subtotal:
        guia.subtotal = subtotal
        guia.save(update_fields=['subtotal', 'actualizado_em'])


def _get_pos_disponiveis_para_guia(guia_actual=None):
    """
    Retorna apenas POs confirmadas que ainda não possuem guia de entrega
    activa/não-cancelada.

    Guias canceladas NÃO bloqueiam a PO.

    Se estiver a editar uma guia, a PO actual dessa guia continua disponível.
    """
    pos_com_guia_activa = (
        GuiaEntrega.objects
        .exclude(purchase_order__isnull=True)
        .exclude(estado__codigo='cancelada')
        .values_list('purchase_order_id', flat=True)
        .distinct()
    )

    qs = (
        PurchaseOrder.objects
        .select_related('cliente', 'moeda', 'quotacao')
        .filter(estado__codigo='confirmada')
        .exclude(id__in=pos_com_guia_activa)
        .order_by('-id')
    )

    if guia_actual and guia_actual.purchase_order_id:
        qs = (
            PurchaseOrder.objects
            .select_related('cliente', 'moeda', 'quotacao')
            .filter(
                Q(estado__codigo='confirmada') &
                (
                    ~Q(id__in=pos_com_guia_activa) |
                    Q(id=guia_actual.purchase_order_id)
                )
            )
            .order_by('-id')
        )

    return qs


@login_required
@require_GET
def guias_entrega_view(request):
    guias = (
        GuiaEntrega.objects
        .select_related(
            'cliente',
            'moeda',
            'estado',
            'purchase_order',
            'purchase_order__quotacao',
            'factura',
        )
        .prefetch_related('itens')
        .order_by('-id')
    )

    clientes = Cliente.objects.filter(estado=True).order_by('nome')
    moedas = Moeda.objects.filter(estado=True).order_by('codigo')
    estados = GuiaEstado.objects.filter(activo=True).order_by('ordem', 'nome')
    pos = _get_pos_disponiveis_para_guia()
    facturas = (
        Factura.objects
        .select_related('cliente', 'moeda', 'estado', 'purchase_order')
        .exclude(estado__codigo='cancelada')
        .order_by('-id')
    )

    today = timezone.localdate()

    total_guias = guias.count()
    total_pendentes = guias.filter(estado__codigo='pendente').count()
    total_entregues = guias.filter(estado__codigo='entregue').count()
    total_canceladas = guias.filter(estado__codigo='cancelada').count()

    valor_total = guias.aggregate(total=Sum('subtotal')).get('total') or Decimal('0')
    valor_entregue = (
        guias.filter(estado__codigo='entregue')
        .aggregate(total=Sum('subtotal')).get('total') or Decimal('0')
    )

    context = {
        'segment': 'guias_entrega',
        'guias': guias,
        'clientes': clientes,
        'moedas': moedas,
        'estados': estados,
        'pos': pos,
        'facturas': facturas,
        'total_guias': total_guias,
        'total_pendentes': total_pendentes,
        'total_entregues': total_entregues,
        'total_canceladas': total_canceladas,
        'valor_total': valor_total,
        'valor_entregue': valor_entregue,
        'default_numero': _generate_guia_number(),
        'today': today.isoformat(),
    }
    return render(request, 'guiaentregas/guias_entrega.html', context)


@login_required
@require_GET
def guia_entrega_detail_json_view(request, guia_id):
    guia = get_object_or_404(
        GuiaEntrega.objects.select_related(
            'cliente',
            'moeda',
            'estado',
            'purchase_order',
            'purchase_order__quotacao',
            'factura',
            'factura__estado',
        ).prefetch_related('itens'),
        id=guia_id,
    )

    itens = []
    for it in guia.itens.all():
        itens.append({
            'id': it.id,
            'descricao': it.descricao,
            'unidade': it.unidade or '',
            'quantidade': str(it.quantidade),
            'preco_unit': str(it.preco_unit),
            'total_linha': str(it.total_linha),
        })

    return JsonResponse({
        'id': guia.id,
        'numero': guia.numero,
        'cliente_id': guia.cliente_id,
        'cliente_nome': guia.cliente.nome if guia.cliente else '',
        'moeda_id': guia.moeda_id or '',
        'moeda_simbolo': guia.moeda.simbolo if guia.moeda else '',
        'estado_id': guia.estado_id,
        'estado_nome': guia.estado.nome if guia.estado else '',
        'estado_codigo': guia.estado.codigo if guia.estado else '',
        'estado_cor': guia.estado.cor if guia.estado else '#2E3E82',
        'purchase_order_id': guia.purchase_order_id or '',
        'purchase_order_numero': guia.purchase_order.numero if guia.purchase_order else '',
        'po_cliente_numero': guia.purchase_order.po_cliente_numero if guia.purchase_order else '',
        'factura_id': guia.factura_id or '',
        'factura_numero': guia.factura.numero if guia.factura else '',
        'data_guia': guia.data_guia.isoformat() if guia.data_guia else '',
        'data_entrega': guia.data_entrega.isoformat() if guia.data_entrega else '',
        'recebido_por': guia.recebido_por or '',
        'contacto_recebedor': guia.contacto_recebedor or '',
        'local_entrega': guia.local_entrega or '',
        'subtotal': str(guia.subtotal),
        'observacoes': guia.observacoes or '',
        'pdf_url': request.build_absolute_uri(f'/guias-entrega/{guia.id}/pdf/'),
        'itens': itens,
    })


@login_required
@require_POST
@transaction.atomic
def guia_entrega_create_view(request):
    try:
        cliente_id = request.POST.get('cliente_id')
        moeda_id = _clean_nullable_fk(request.POST.get('moeda_id'))
        purchase_order_id = _clean_nullable_fk(request.POST.get('purchase_order_id'))
        factura_id = _clean_nullable_fk(request.POST.get('factura_id'))
        data_guia = request.POST.get('data_guia')
        data_entrega = _clean_nullable_fk(request.POST.get('data_entrega'))
        recebido_por = request.POST.get('recebido_por', '').strip() or None
        contacto_recebedor = request.POST.get('contacto_recebedor', '').strip() or None
        local_entrega = request.POST.get('local_entrega', '').strip() or None
        observacoes = request.POST.get('observacoes', '').strip() or None
        itens_raw = json.loads(request.POST.get('itens_json', '[]'))

        if not cliente_id:
            return JsonResponse({'success': False, 'message': 'Cliente é obrigatório.'}, status=400)

        if not data_guia:
            return JsonResponse({'success': False, 'message': 'Data da guia é obrigatória.'}, status=400)

        if purchase_order_id:
            guia_existente = (
                GuiaEntrega.objects
                .filter(purchase_order_id=purchase_order_id)
                .exclude(estado__codigo='cancelada')
                .first()
            )
            if guia_existente:
                return JsonResponse({
                    'success': False,
                    'message': f'Esta PO já está associada à guia "{guia_existente.numero}".'
                }, status=400)

        guia = GuiaEntrega.objects.create(
            numero=_generate_guia_number(),
            purchase_order_id=purchase_order_id,
            cliente_id=cliente_id,
            moeda_id=moeda_id,
            estado=_get_estado_pendente(),
            factura_id=factura_id,
            data_guia=data_guia,
            data_entrega=data_entrega,
            recebido_por=recebido_por,
            contacto_recebedor=contacto_recebedor,
            local_entrega=local_entrega,
            subtotal=Decimal('0'),
            observacoes=observacoes,
            criado_por=request.user,
        )

        _save_itens(guia, itens_raw)

        return JsonResponse({
            'success': True,
            'message': f'Guia de entrega "{guia.numero}" criada com sucesso.',
            'guia_id': guia.id,
        })

    except Exception:
        logger.exception('Erro ao criar guia de entrega')
        return JsonResponse({'success': False, 'message': 'Erro ao criar guia de entrega.'}, status=500)


@login_required
@require_POST
@transaction.atomic
def guia_entrega_update_view(request, guia_id):
    try:
        guia = get_object_or_404(GuiaEntrega, id=guia_id)

        cliente_id = request.POST.get('cliente_id')
        moeda_id = _clean_nullable_fk(request.POST.get('moeda_id'))
        purchase_order_id = _clean_nullable_fk(request.POST.get('purchase_order_id'))
        factura_id = _clean_nullable_fk(request.POST.get('factura_id'))
        estado_id = _clean_nullable_fk(request.POST.get('estado_id')) or guia.estado_id
        data_guia = request.POST.get('data_guia')
        data_entrega = _clean_nullable_fk(request.POST.get('data_entrega'))
        recebido_por = request.POST.get('recebido_por', '').strip() or None
        contacto_recebedor = request.POST.get('contacto_recebedor', '').strip() or None
        local_entrega = request.POST.get('local_entrega', '').strip() or None
        observacoes = request.POST.get('observacoes', '').strip() or None
        itens_raw = json.loads(request.POST.get('itens_json', '[]'))

        if not cliente_id:
            return JsonResponse({'success': False, 'message': 'Cliente é obrigatório.'}, status=400)

        if not data_guia:
            return JsonResponse({'success': False, 'message': 'Data da guia é obrigatória.'}, status=400)

        if purchase_order_id:
            guia_existente = (
                GuiaEntrega.objects
                .filter(purchase_order_id=purchase_order_id)
                .exclude(estado__codigo='cancelada')
                .exclude(id=guia.id)
                .first()
            )
            if guia_existente:
                return JsonResponse({
                    'success': False,
                    'message': f'Esta PO já está associada à guia "{guia_existente.numero}".'
                }, status=400)

        guia.cliente_id = cliente_id
        guia.moeda_id = moeda_id
        guia.purchase_order_id = purchase_order_id
        guia.factura_id = factura_id
        guia.estado_id = estado_id
        guia.data_guia = data_guia
        guia.data_entrega = data_entrega
        guia.recebido_por = recebido_por
        guia.contacto_recebedor = contacto_recebedor
        guia.local_entrega = local_entrega
        guia.observacoes = observacoes
        guia.save()

        _save_itens(guia, itens_raw)

        return JsonResponse({
            'success': True,
            'message': f'Guia de entrega "{guia.numero}" actualizada com sucesso.',
        })

    except Exception:
        logger.exception('Erro ao actualizar guia de entrega %s', guia_id)
        return JsonResponse({'success': False, 'message': 'Erro ao actualizar guia de entrega.'}, status=500)


@login_required
@require_GET
def po_itens_para_guia_json_view(request, po_id):
    po = get_object_or_404(
        PurchaseOrder.objects.select_related('cliente', 'moeda', 'quotacao'),
        id=po_id,
    )

    itens = []
    if po.quotacao:
        for it in po.quotacao.itens.all().order_by('linha'):
            itens.append({
                'descricao': it.descricao,
                'unidade': it.unidade.sigla if getattr(it, 'unidade', None) else '',
                'quantidade': str(it.quantidade),
                'preco_unit': str(it.preco_unitario),
            })

    if not itens:
        itens = [{
            'descricao': f'Entrega referente à PO {po.po_cliente_numero or po.numero}',
            'unidade': 'un',
            'quantidade': '1',
            'preco_unit': str(po.valor_total or '0'),
        }]

    return JsonResponse({
        'po_numero': po.numero,
        'po_cliente_numero': po.po_cliente_numero or '',
        'po_valor_total': str(po.valor_total or '0'),
        'cliente_id': po.cliente_id,
        'moeda_id': po.moeda_id or '',
        'itens': itens,
    })


@login_required
@require_GET
def factura_itens_para_guia_json_view(request, factura_id):
    factura = get_object_or_404(
        Factura.objects.select_related('cliente', 'moeda', 'purchase_order'),
        id=factura_id,
    )

    itens = []
    for it in factura.itens.all().order_by('ordem', 'id'):
        itens.append({
            'descricao': it.descricao,
            'unidade': it.unidade or '',
            'quantidade': str(it.quantidade),
            'preco_unit': str(it.preco_unit),
        })

    if not itens:
        itens = [{
            'descricao': f'Entrega referente à Factura {factura.numero}',
            'unidade': 'un',
            'quantidade': '1',
            'preco_unit': str(factura.total or '0'),
        }]

    return JsonResponse({
        'factura_numero': factura.numero,
        'cliente_id': factura.cliente_id,
        'moeda_id': factura.moeda_id or '',
        'purchase_order_id': factura.purchase_order_id or '',
        'itens': itens,
    })


@login_required
@require_GET
def guia_entrega_pdf_view(request, guia_id):
    guia = get_object_or_404(
        GuiaEntrega.objects.select_related(
            'cliente', 'moeda', 'estado',
            'purchase_order', 'factura', 'criado_por',
        ).prefetch_related('itens'),
        id=guia_id,
    )

    try:
        from procurement.models import Organizacao
        organizacao = Organizacao.objects.filter(activo=True).order_by('id').first()
    except Exception:
        organizacao = None

    font_path = os.path.join(settings.STATIC_ROOT, 'assets', 'fonts').replace('\\', '/')

    html_string = render_to_string(
        'guiaentregas/guia_entrega_pdf.html',
        {
            'guia': guia,
            'organizacao': organizacao,
            'font_path': font_path,
        },
        request=request,
    )

    pdf_file = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/'),
    ).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Guia_Entrega_{guia.numero.replace("/", "-")}.pdf"'
    return response

@login_required
@require_POST
@transaction.atomic
def guia_entrega_change_estado_view(request, guia_id):
    guia = get_object_or_404(GuiaEntrega, id=guia_id)

    if guia.estado and guia.estado.codigo == 'entregue':
        return JsonResponse({
            'success': False,
            'message': 'Não é possível alterar o estado de uma guia já entregue.'
        }, status=400)

    estado_id = _clean_nullable_fk(request.POST.get('estado_id'))
    estado = get_object_or_404(GuiaEstado, id=estado_id, activo=True)

    guia.estado = estado

    if estado.codigo == 'entregue' and not guia.data_entrega:
        guia.data_entrega = timezone.localdate()

    guia.save(update_fields=['estado', 'data_entrega', 'actualizado_em'])

    return JsonResponse({
        'success': True,
        'message': f'Estado alterado para "{estado.nome}".'
    })
