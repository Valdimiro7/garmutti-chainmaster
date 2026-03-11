from decimal import Decimal, InvalidOperation
import logging
import os

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q, Value, DecimalField, F
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from procurement.models import (
    Cliente,
    DadoBancario,
    Factura,
    FacturaEstado,
    FacturaItem,
    FacturaDadoBancario,
    Moeda,
    PurchaseOrder,
    PurchaseOrderAnexo,
    Quotacao,
    QuotacaoItem,
)

logger = logging.getLogger(__name__)

IVA_PADRAO = Decimal('16')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_decimal(value, default='0'):
    try:
        return Decimal(str(value or default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _generate_factura_number():
    year = timezone.now().year
    suffix = f'/{year}'
    ultimo = (
        Factura.objects
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
    return f'FACT-{seq:03d}/{year}'


def _get_estado_rascunho():
    estado = (
        FacturaEstado.objects
        .filter(activo=True)
        .filter(Q(codigo='pendente') | Q(id=1))
        .order_by('codigo')
        .first()
    )
    if not estado:
        raise ValueError('Estado padrão para nova factura não encontrado.')
    return estado


def _calcular_totais(subtotal, desconto, iva_pct):
    subtotal_liq = subtotal - desconto
    if subtotal_liq < 0:
        subtotal_liq = Decimal('0')
    iva_valor = (subtotal_liq * iva_pct / 100).quantize(Decimal('0.01'))
    total = subtotal_liq + iva_valor
    return subtotal_liq, iva_valor, total


def _save_itens(factura, itens_data):
    FacturaItem.objects.filter(factura_id=factura.id).delete()
    for i, item in enumerate(itens_data):
        descricao = item.get('descricao', '').strip()
        if not descricao:
            continue
        quantidade = _parse_decimal(item.get('quantidade', '1'), '1')
        preco_unit = _parse_decimal(item.get('preco_unit', '0'))
        total_linha = (quantidade * preco_unit).quantize(Decimal('0.01'))
        FacturaItem.objects.create(
            factura_id=factura.id,
            descricao=descricao,
            unidade=item.get('unidade', '').strip() or None,
            quantidade=quantidade,
            preco_unit=preco_unit,
            total_linha=total_linha,
            ordem=i,
        )


def _save_dados_bancarios(factura, dado_bancario_ids):
    FacturaDadoBancario.objects.filter(factura_id=factura.id).delete()

    valid_ids = []
    for raw_id in dado_bancario_ids:
        try:
            db_id = int(raw_id)
            if db_id not in valid_ids:
                valid_ids.append(db_id)
        except (TypeError, ValueError):
            continue

    for ordem, db_id in enumerate(valid_ids):
        FacturaDadoBancario.objects.create(
            factura_id=factura.id,
            dado_bancario_id=db_id,
            ordem=ordem,
        )

    # Compatibilidade com campo antigo
    primeiro_id = valid_ids[0] if valid_ids else None
    if factura.dado_bancario_id != primeiro_id:
        factura.dado_bancario_id = primeiro_id
        factura.save(update_fields=['dado_bancario_id', 'actualizado_em'])



def _get_pos_disponiveis(factura_actual=None):
    """
    Retorna POs confirmadas, excluindo POs que já tenham
    pelo menos uma factura com estado 'paga' (id=2).
    Se estiver a editar uma factura, a PO actual continua disponível.
    """
    # IDs de POs que já têm factura paga
    pos_com_factura_paga = (
        Factura.objects
        .filter(estado__id=2)
        .exclude(purchase_order__isnull=True)
        .values_list('purchase_order_id', flat=True)
        .distinct()
    )

    qs = (
        PurchaseOrder.objects
        .select_related('cliente', 'moeda', 'quotacao', 'quotacao__condicao_pagamento')
        .filter(estado__codigo='confirmada')
        .exclude(id__in=pos_com_factura_paga)
        .order_by('-id')
    )

    # Se estiver a editar, re-inclui a PO actual mesmo que esteja excluída
    if factura_actual and factura_actual.purchase_order_id:
        qs_com_actual = (
            PurchaseOrder.objects
            .select_related('cliente', 'moeda', 'quotacao', 'quotacao__condicao_pagamento')
            .filter(
                Q(estado__codigo='confirmada') &
                (
                    ~Q(id__in=pos_com_factura_paga) |
                    Q(id=factura_actual.purchase_order_id)
                )
            )
            .order_by('-id')
        )
        return qs_com_actual

    return qs


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
@require_GET
def facturas_view(request):
    facturas = (
        Factura.objects
        .select_related('purchase_order', 'cliente', 'moeda', 'estado')
        .prefetch_related('itens', 'factura_dados_bancarios__dado_bancario')
        .order_by('-id')
    )

    clientes = Cliente.objects.filter(estado=True).order_by('nome')
    estados = FacturaEstado.objects.filter(activo=True).order_by('ordem')
    moedas = Moeda.objects.filter(estado=True).order_by('codigo')
    dados_bancarios = DadoBancario.objects.filter(activo=True).order_by('ordem', 'banco')
    pos_confirmadas = _get_pos_disponiveis()

    today = timezone.localdate()

    total_facturas = facturas.count()
    total_emitidas = facturas.filter(estado__codigo='pendente').count()
    total_pagas = facturas.filter(estado__codigo='paga').count()
    total_vencidas = facturas.filter(estado__codigo='vencida').count()

    valor_total_emitido = (
        facturas.exclude(estado__codigo='cancelada')
        .aggregate(t=Sum('total')).get('t') or Decimal('0')
    )
    valor_total_pago = (
        facturas.filter(estado__codigo__in=['paga', 'paga_parcial'])
        .aggregate(t=Sum('total')).get('t') or Decimal('0')
    )

    context = {
        'segment': 'facturas',
        'facturas': facturas,
        'clientes': clientes,
        'estados': estados,
        'moedas': moedas,
        'dados_bancarios': dados_bancarios,
        'pos_confirmadas': pos_confirmadas,
        'total_facturas': total_facturas,
        'total_emitidas': total_emitidas,
        'total_pagas': total_pagas,
        'total_vencidas': total_vencidas,
        'valor_total_emitido': valor_total_emitido,
        'valor_total_pago': valor_total_pago,
        'default_numero': _generate_factura_number(),
        'today': today.isoformat(),
        'iva_padrao': IVA_PADRAO,
    }
    return render(request, 'facturas/facturas.html', context)


@login_required
@require_GET
def factura_detail_json_view(request, factura_id):
    factura = get_object_or_404(
        Factura.objects.select_related(
            'purchase_order', 'purchase_order__quotacao',
            'cliente', 'moeda', 'estado', 'dado_bancario',
        ).prefetch_related(
            'itens',
            'factura_dados_bancarios__dado_bancario',
        ),
        id=factura_id,
    )

    itens = []
    for it in factura.itens.all():
        itens.append({
            'id': it.id,
            'descricao': it.descricao,
            'unidade': it.unidade or '',
            'quantidade': str(it.quantidade),
            'preco_unit': str(it.preco_unit),
            'total_linha': str(it.total_linha),
        })

    contas_bancarias = []
    conta_ids = []

    for rel in factura.factura_dados_bancarios.all():
        if rel.dado_bancario:
            conta_ids.append(rel.dado_bancario_id)
            contas_bancarias.append({
                'id': rel.dado_bancario_id,
                'label': rel.dado_bancario.label_completo,
            })

    if not contas_bancarias and factura.dado_bancario:
        conta_ids.append(factura.dado_bancario_id)
        contas_bancarias.append({
            'id': factura.dado_bancario_id,
            'label': factura.dado_bancario.label_completo,
        })

    po_download_url = ''
    quot_download_url = ''
    quotacao_numero = ''
    po_valor_total = ''
    po_cliente_numero = ''
    po_numero_interno = ''

    if factura.purchase_order:
        po = factura.purchase_order
        po_numero_interno = po.numero
        po_cliente_numero = po.po_cliente_numero or ''
        po_valor_total = str(po.valor_total or '0')

        po_anexo = PurchaseOrderAnexo.objects.filter(
            purchase_order_id=po.id, tipo_anexo='po'
        ).first()
        if po_anexo:
            po_download_url = reverse('procurement:po_anexo_download', args=[po_anexo.id])

        if po.quotacao:
            quotacao_numero = po.quotacao.numero
            quot_download_url = reverse('procurement:quotacoes_download_pdf', args=[po.quotacao_id])

    data = {
        'id': factura.id,
        'numero': factura.numero,
        'estado_id': factura.estado_id,
        'estado_codigo': factura.estado.codigo if factura.estado else '',
        'estado_nome': factura.estado.nome if factura.estado else '',
        'estado_cor': factura.estado.cor if factura.estado else '#2E3E82',
        'cliente_id': factura.cliente_id,
        'cliente_nome': factura.cliente.nome if factura.cliente else '',
        'moeda_id': factura.moeda_id or '',
        'moeda_simbolo': factura.moeda.simbolo if factura.moeda else '',
        'dado_bancario_ids': conta_ids,
        'dados_bancarios': contas_bancarias,
        'purchase_order_id': factura.purchase_order_id or '',
        'purchase_order_numero': po_numero_interno,
        'po_cliente_numero': po_cliente_numero,
        'po_valor_total': po_valor_total,
        'quotacao_numero': quotacao_numero,
        'po_download_url': po_download_url,
        'quot_download_url': quot_download_url,
        'data_emissao': factura.data_emissao.isoformat() if factura.data_emissao else '',
        'data_vencimento': factura.data_vencimento.isoformat() if factura.data_vencimento else '',
        'subtotal': str(factura.subtotal),
        'desconto': str(factura.desconto),
        'desconto_pct': str(factura.desconto_pct),
        'iva_pct': str(factura.iva_pct),
        'iva_valor': str(factura.iva_valor),
        'total': str(factura.total),
        'observacoes': factura.observacoes or '',
        'termos': factura.termos or '',
        'pdf_url': reverse('procurement:factura_pdf', args=[factura.id]),
        'itens': itens,
    }
    return JsonResponse(data)


@login_required
@require_POST
@transaction.atomic
def factura_create_view(request):
    import json

    try:
        po_id = request.POST.get('purchase_order_id') or None
        cliente_id = request.POST.get('cliente_id')
        moeda_id = request.POST.get('moeda_id') or None
        dado_bancario_ids = request.POST.getlist('dado_bancario_ids[]') or request.POST.getlist('dado_bancario_ids')
        estado_id = request.POST.get('estado_id') or None
        data_emissao = request.POST.get('data_emissao')
        data_vencimento = request.POST.get('data_vencimento') or None
        desconto = _parse_decimal(request.POST.get('desconto', '0'))
        iva_pct = _parse_decimal(request.POST.get('iva_pct', '16'), '16')
        observacoes = request.POST.get('observacoes', '').strip() or None
        termos = request.POST.get('termos', '').strip() or None

        itens_raw = json.loads(request.POST.get('itens_json', '[]'))

        subtotal = sum(
            _parse_decimal(it.get('quantidade', '1'), '1') * _parse_decimal(it.get('preco_unit', '0'))
            for it in itens_raw
            if it.get('descricao', '').strip()
        )

        _, iva_valor, total = _calcular_totais(subtotal, desconto, iva_pct)

        if estado_id:
            estado = get_object_or_404(FacturaEstado, id=estado_id)
        else:
            estado = _get_estado_rascunho()

        # validação da PO
        if po_id:
            po = get_object_or_404(PurchaseOrder, id=po_id)
            total_facturas_pagas = (
                Factura.objects
                .filter(purchase_order_id=po_id, estado__codigo='paga')
                .aggregate(t=Sum('total')).get('t') or Decimal('0')
            )
            if total_facturas_pagas >= (po.valor_total or Decimal('0')):
                return JsonResponse({
                    'success': False,
                    'message': 'Esta PO já possui facturas pagas na totalidade e não pode ser associada a uma nova factura.'
                }, status=400)

        factura = Factura.objects.create(
            numero=_generate_factura_number(),
            purchase_order_id=po_id,
            estado=estado,
            cliente_id=cliente_id,
            moeda_id=moeda_id,
            dado_bancario_id=None,
            data_emissao=data_emissao,
            data_vencimento=data_vencimento,
            subtotal=subtotal,
            desconto=desconto,
            desconto_pct=(desconto / subtotal * 100).quantize(Decimal('0.01')) if subtotal > 0 else Decimal('0'),
            iva_pct=iva_pct,
            iva_valor=iva_valor,
            total=total,
            observacoes=observacoes,
            termos=termos,
            criado_por=request.user,
        )

        _save_itens(factura, itens_raw)
        _save_dados_bancarios(factura, dado_bancario_ids)

        return JsonResponse({
            'success': True,
            'message': f'Factura "{factura.numero}" criada com sucesso.',
            'factura_id': factura.id,
            'numero': factura.numero,
        })

    except Exception:
        logger.exception('Erro ao criar factura')
        return JsonResponse({'success': False, 'message': 'Erro ao criar factura.'}, status=500)


@login_required
@require_POST
@transaction.atomic
def factura_update_view(request, factura_id):
    import json

    factura = get_object_or_404(Factura, id=factura_id)

    if factura.estado and factura.estado.codigo == 'cancelada':
        return JsonResponse({'success': False, 'message': 'Não é possível editar uma factura cancelada.'}, status=400)

    try:
        po_id = request.POST.get('purchase_order_id') or None
        cliente_id = request.POST.get('cliente_id')
        moeda_id = request.POST.get('moeda_id') or None
        dado_bancario_ids = request.POST.getlist('dado_bancario_ids[]') or request.POST.getlist('dado_bancario_ids')
        estado_id = request.POST.get('estado_id') or None
        data_emissao = request.POST.get('data_emissao')
        data_vencimento = request.POST.get('data_vencimento') or None
        desconto = _parse_decimal(request.POST.get('desconto', '0'))
        iva_pct = _parse_decimal(request.POST.get('iva_pct', '16'), '16')
        observacoes = request.POST.get('observacoes', '').strip() or None
        termos = request.POST.get('termos', '').strip() or None

        itens_raw = json.loads(request.POST.get('itens_json', '[]'))

        subtotal = sum(
            _parse_decimal(it.get('quantidade', '1'), '1') * _parse_decimal(it.get('preco_unit', '0'))
            for it in itens_raw
            if it.get('descricao', '').strip()
        )

        _, iva_valor, total = _calcular_totais(subtotal, desconto, iva_pct)

        if estado_id:
            factura.estado = get_object_or_404(FacturaEstado, id=estado_id)

        if po_id:
            po = get_object_or_404(PurchaseOrder, id=po_id)
            total_facturas_pagas = (
                Factura.objects
                .filter(purchase_order_id=po_id, estado__codigo='paga')
                .exclude(id=factura.id)
                .aggregate(t=Sum('total')).get('t') or Decimal('0')
            )
            if total_facturas_pagas >= (po.valor_total or Decimal('0')):
                return JsonResponse({
                    'success': False,
                    'message': 'Esta PO já possui facturas pagas na totalidade e não pode ser associada.'
                }, status=400)

        factura.purchase_order_id = po_id
        factura.cliente_id = cliente_id
        factura.moeda_id = moeda_id
        factura.data_emissao = data_emissao
        factura.data_vencimento = data_vencimento
        factura.subtotal = subtotal
        factura.desconto = desconto
        factura.desconto_pct = (desconto / subtotal * 100).quantize(Decimal('0.01')) if subtotal > 0 else Decimal('0')
        factura.iva_pct = iva_pct
        factura.iva_valor = iva_valor
        factura.total = total
        factura.observacoes = observacoes
        factura.termos = termos
        factura.save()

        _save_itens(factura, itens_raw)
        _save_dados_bancarios(factura, dado_bancario_ids)

        return JsonResponse({
            'success': True,
            'message': f'Factura "{factura.numero}" actualizada com sucesso.',
        })

    except Exception:
        logger.exception('Erro ao actualizar factura %s', factura_id)
        return JsonResponse({'success': False, 'message': 'Erro ao actualizar factura.'}, status=500)


@login_required
@require_POST
def factura_change_estado_view(request, factura_id):
    factura = get_object_or_404(Factura, id=factura_id)
    estado_id = request.POST.get('estado_id')
    estado = get_object_or_404(FacturaEstado, id=estado_id, activo=True)

    factura.estado = estado
    factura.save(update_fields=['estado', 'actualizado_em'])

    return JsonResponse({'success': True, 'message': f'Estado alterado para "{estado.nome}".'})


@login_required
@require_GET
def factura_pdf_view(request, factura_id):
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    from weasyprint import HTML

    factura = get_object_or_404(
        Factura.objects.select_related(
            'cliente', 'moeda', 'estado', 'dado_bancario',
            'purchase_order', 'purchase_order__quotacao',
            'purchase_order__quotacao__condicao_pagamento',
        ).prefetch_related(
            'itens',
            'factura_dados_bancarios__dado_bancario',
        ),
        id=factura_id,
    )

    try:
        from procurement.models import Organizacao
        organizacao = Organizacao.objects.filter(activo=True).order_by('id').first()
    except Exception:
        organizacao = None

    html_string = render_to_string(
        'facturas/factura_pdf.html',
        {'factura': factura, 'organizacao': organizacao},
        request=request,
    )

    pdf_file = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/'),
    ).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="Factura_{factura.numero.replace("/", "-")}.pdf"'
    )
    return response


@login_required
@require_GET
def po_itens_json_view(request, po_id):
    po = get_object_or_404(
        PurchaseOrder.objects.select_related(
            'quotacao', 'quotacao__condicao_pagamento', 'cliente', 'moeda'
        ),
        id=po_id,
    )

    itens = []
    termos = ''
    quotacao_numero = ''
    quot_download_url = ''
    po_download_url = ''

    if po.quotacao:
        q = po.quotacao
        quotacao_numero = q.numero

        try:
            quot_download_url = reverse('procurement:quotacoes_download_pdf', args=[q.id])
        except Exception:
            pass

        if q.condicao_pagamento and q.condicao_pagamento.descricao:
            termos = q.condicao_pagamento.descricao
        elif q.observacoes:
            termos = q.observacoes

        for it in QuotacaoItem.objects.filter(quotacao_id=q.id).order_by('linha'):
            itens.append({
                'descricao': it.descricao,
                'unidade': it.unidade.sigla if it.unidade else '',
                'quantidade': str(it.quantidade),
                'preco_unit': str(it.preco_unitario),
            })

    if not itens:
        itens = [{
            'descricao': f'Fornecimento conforme PO {po.po_cliente_numero or po.numero}',
            'unidade': 'un',
            'quantidade': '1',
            'preco_unit': str(po.valor_total or '0'),
        }]

    po_anexo = PurchaseOrderAnexo.objects.filter(
        purchase_order_id=po.id, tipo_anexo='po'
    ).first()
    if po_anexo:
        try:
            po_download_url = reverse('procurement:po_anexo_download', args=[po_anexo.id])
        except Exception:
            pass

    return JsonResponse({
        'po_numero': po.numero,
        'po_cliente_numero': po.po_cliente_numero or '',
        'po_valor_total': str(po.valor_total or '0'),
        'cliente_id': po.cliente_id,
        'moeda_id': po.moeda_id or '',
        'quotacao_numero': quotacao_numero,
        'quot_download_url': quot_download_url,
        'po_download_url': po_download_url,
        'termos': termos,
        'itens': itens,
    })
    
    
    

@login_required
@require_GET
def factura_check_pagamento_view(request, factura_id):
    from procurement.models import Pagamento, PagamentoHistorico

    factura = get_object_or_404(
        Factura.objects.select_related('purchase_order', 'cliente', 'moeda'),
        id=factura_id,
    )

    # Históricos já associados a ESTA factura
    tem_historico = PagamentoHistorico.objects.filter(factura_id=factura_id).exists()
    historicos_ja_associados = list(
        PagamentoHistorico.objects
        .filter(factura_id=factura_id)
        .values_list('id', flat=True)
    )

    # Históricos disponíveis:
    #   - Não associados a NENHUMA factura (factura_id IS NULL)
    #   - OU já associados a ESTA factura (para mostrar como seleccionados)
    #   - Filtro de PO: da mesma PO desta factura OU sem PO
    qs = PagamentoHistorico.objects.select_related(
        'pagamento', 'pagamento__cliente', 'pagamento__moeda',
        'pagamento__purchase_order', 'dado_bancario'
    ).filter(
        Q(factura__isnull=True) | Q(factura_id=factura_id)
    )

    if factura.purchase_order_id:
        qs = qs.filter(
            Q(pagamento__purchase_order_id=factura.purchase_order_id) |
            Q(pagamento__purchase_order__isnull=True)
        )
    else:
        qs = qs.filter(pagamento__purchase_order__isnull=True)

    historicos_disponiveis = []
    for h in qs.order_by('-data_pagamento'):
        p = h.pagamento
        historicos_disponiveis.append({
            'id': h.id,
            'ja_associado': h.id in historicos_ja_associados,
            'pagamento_numero': p.numero,
            'cliente_nome': p.cliente.nome if p.cliente else '—',
            'moeda_simbolo': p.moeda.simbolo if p.moeda else '',
            'valor_pago': str(h.valor_pago),
            'data_pagamento': h.data_pagamento.isoformat() if h.data_pagamento else '',
            'referencia': h.referencia or '',
            'banco_origem': h.banco_origem or '',
            'numero_transaccao': h.numero_transaccao or '',
            'po_numero': p.purchase_order.numero if p.purchase_order else None,
            'dado_bancario': h.dado_bancario.label_completo if h.dado_bancario else '',
        })

    return JsonResponse({
        'tem_historico': tem_historico,
        'historicos_disponiveis': historicos_disponiveis,
        'historicos_ja_associados': historicos_ja_associados,
    })


@login_required
@require_POST
@transaction.atomic
def factura_change_estado_com_pagamento_view(request, factura_id):
    import json
    from procurement.models import PagamentoHistorico

    factura = get_object_or_404(Factura, id=factura_id)
    estado_id = request.POST.get('estado_id')
    historico_ids_raw = request.POST.get('historico_ids', '[]')

    try:
        historico_ids = [int(i) for i in json.loads(historico_ids_raw)]
    except (ValueError, TypeError):
        historico_ids = []

    estado = get_object_or_404(FacturaEstado, id=estado_id, activo=True)
    factura.estado = estado
    factura.save(update_fields=['estado', 'actualizado_em'])

    if historico_ids:
        # Desvincula históricos desta factura que não estão na nova lista
        PagamentoHistorico.objects.filter(
            factura_id=factura_id
        ).exclude(id__in=historico_ids).update(factura=None)

        # Vincula os seleccionados (apenas os que ainda não têm factura)
        updated = PagamentoHistorico.objects.filter(
            id__in=historico_ids
        ).filter(
            Q(factura__isnull=True) | Q(factura_id=factura_id)
        ).update(factura=factura)

        # Se a factura não tem PO, tenta herdar da PO do primeiro histórico
        if not factura.purchase_order_id:
            primeiro = PagamentoHistorico.objects.select_related('pagamento__purchase_order').filter(
                id__in=historico_ids,
                pagamento__purchase_order__isnull=False
            ).first()
            if primeiro:
                factura.purchase_order_id = primeiro.pagamento.purchase_order_id
                factura.save(update_fields=['purchase_order_id', 'actualizado_em'])

    return JsonResponse({
        'success': True,
        'message': f'Estado alterado para "{estado.nome}".'
    })