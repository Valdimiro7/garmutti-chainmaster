from decimal import Decimal, InvalidOperation
import logging
import os

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
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
    estado = FacturaEstado.objects.filter(codigo='rascunho', activo=True).first()
    if not estado:
        raise ValueError('Estado "Rascunho" não encontrado.')
    return estado


def _calcular_totais(subtotal, desconto, iva_pct):
    """Retorna (subtotal_liq, iva_valor, total)."""
    subtotal_liq = subtotal - desconto
    if subtotal_liq < 0:
        subtotal_liq = Decimal('0')
    iva_valor = (subtotal_liq * iva_pct / 100).quantize(Decimal('0.01'))
    total = subtotal_liq + iva_valor
    return subtotal_liq, iva_valor, total


def _save_itens(factura, itens_data):
    """Apaga itens antigos e regrava os novos."""
    FacturaItem.objects.filter(factura_id=factura.id).delete()
    for i, item in enumerate(itens_data):
        descricao  = item.get('descricao', '').strip()
        if not descricao:
            continue
        quantidade = _parse_decimal(item.get('quantidade', '1'), '1')
        preco_unit = _parse_decimal(item.get('preco_unit', '0'))
        total_linha = (quantidade * preco_unit).quantize(Decimal('0.01'))
        FacturaItem.objects.create(
            factura_id  = factura.id,
            descricao   = descricao,
            unidade     = item.get('unidade', '').strip() or None,
            quantidade  = quantidade,
            preco_unit  = preco_unit,
            total_linha = total_linha,
            ordem       = i,
        )


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
@require_GET
def facturas_view(request):
    facturas = (
        Factura.objects
        .select_related('purchase_order', 'cliente', 'moeda', 'estado')
        .prefetch_related('itens')
        .order_by('-id')
    )

    clientes        = Cliente.objects.filter(estado=True).order_by('nome')
    estados         = FacturaEstado.objects.filter(activo=True).order_by('ordem')
    moedas          = Moeda.objects.filter(estado=True).order_by('codigo')
    dados_bancarios = DadoBancario.objects.filter(activo=True).order_by('ordem', 'banco')

    # POs confirmadas com select_related para quotacao e seus itens
    pos_confirmadas = (
        PurchaseOrder.objects
        .select_related('cliente', 'moeda', 'quotacao', 'quotacao__condicao_pagamento')
        .filter(estado__codigo='confirmada')
        .order_by('-id')
    )

    today = timezone.localdate()

    total_facturas   = facturas.count()
    total_emitidas   = facturas.filter(estado__codigo='pendente').count()
    total_pagas      = facturas.filter(estado__codigo='paga').count()
    total_vencidas   = facturas.filter(estado__codigo='vencida').count()

    valor_total_emitido = (
        facturas.exclude(estado__codigo='cancelada')
        .aggregate(t=Sum('total')).get('t') or Decimal('0')
    )
    valor_total_pago = (
        facturas.filter(estado__codigo__in=['paga', 'paga_parcial'])
        .aggregate(t=Sum('total')).get('t') or Decimal('0')
    )

    context = {
        'segment'            : 'facturas',
        'facturas'           : facturas,
        'clientes'           : clientes,
        'estados'            : estados,
        'moedas'             : moedas,
        'dados_bancarios'    : dados_bancarios,
        'pos_confirmadas'    : pos_confirmadas,
        'total_facturas'     : total_facturas,
        'total_emitidas'     : total_emitidas,
        'total_pagas'        : total_pagas,
        'total_vencidas'     : total_vencidas,
        'valor_total_emitido': valor_total_emitido,
        'valor_total_pago'   : valor_total_pago,
        'default_numero'     : _generate_factura_number(),
        'today'              : today.isoformat(),
        'iva_padrao'         : IVA_PADRAO,
    }
    return render(request, 'facturas/facturas.html', context)


@login_required
@require_GET
def factura_detail_json_view(request, factura_id):
    factura = get_object_or_404(
        Factura.objects.select_related(
            'purchase_order', 'purchase_order__quotacao',
            'cliente', 'moeda', 'estado', 'dado_bancario',
        ),
        id=factura_id,
    )

    itens = []
    for it in factura.itens.all():
        itens.append({
            'id'         : it.id,
            'descricao'  : it.descricao,
            'unidade'    : it.unidade or '',
            'quantidade' : str(it.quantidade),
            'preco_unit' : str(it.preco_unit),
            'total_linha': str(it.total_linha),
        })

    # URLs de download — PO e Quotação
    po_download_url    = ''
    quot_download_url  = ''
    quotacao_numero    = ''
    po_valor_total     = ''
    po_cliente_numero  = ''
    po_numero_interno  = ''

    if factura.purchase_order:
        po = factura.purchase_order
        po_numero_interno = po.numero
        po_cliente_numero = po.po_cliente_numero or ''
        po_valor_total    = str(po.valor_total or '0')

        # Primeiro anexo de tipo 'po'
        po_anexo = PurchaseOrderAnexo.objects.filter(
            purchase_order_id=po.id, tipo_anexo='po'
        ).first()
        if po_anexo:
            po_download_url = reverse('procurement:po_anexo_download', args=[po_anexo.id])

        if po.quotacao:
            quotacao_numero   = po.quotacao.numero
            quot_download_url = reverse('procurement:quotacoes_download_pdf', args=[po.quotacao_id])

    data = {
        'id'                   : factura.id,
        'numero'               : factura.numero,
        'estado_codigo'        : factura.estado.codigo if factura.estado else '',
        'estado_nome'          : factura.estado.nome   if factura.estado else '',
        'estado_cor'           : factura.estado.cor    if factura.estado else '#2E3E82',
        'cliente_id'           : factura.cliente_id,
        'cliente_nome'         : factura.cliente.nome if factura.cliente else '',
        'moeda_id'             : factura.moeda_id or '',
        'moeda_simbolo'        : factura.moeda.simbolo if factura.moeda else '',
        'dado_bancario_id'     : factura.dado_bancario_id or '',
        'purchase_order_id'    : factura.purchase_order_id or '',
        'purchase_order_numero': po_numero_interno,
        'po_cliente_numero'    : po_cliente_numero,
        'po_valor_total'       : po_valor_total,
        'quotacao_numero'      : quotacao_numero,
        'po_download_url'      : po_download_url,
        'quot_download_url'    : quot_download_url,
        'data_emissao'         : factura.data_emissao.isoformat() if factura.data_emissao else '',
        'data_vencimento'      : factura.data_vencimento.isoformat() if factura.data_vencimento else '',
        'subtotal'             : str(factura.subtotal),
        'desconto'             : str(factura.desconto),
        'desconto_pct'         : str(factura.desconto_pct),
        'iva_pct'              : str(factura.iva_pct),
        'iva_valor'            : str(factura.iva_valor),
        'total'                : str(factura.total),
        'observacoes'          : factura.observacoes or '',
        'termos'               : factura.termos or '',
        'pdf_url'              : reverse('procurement:factura_pdf', args=[factura.id]),
        'itens'                : itens,
    }
    return JsonResponse(data)


@login_required
@require_POST
@transaction.atomic
def factura_create_view(request):
    import json

    try:
        po_id            = request.POST.get('purchase_order_id') or None
        cliente_id       = request.POST.get('cliente_id')
        moeda_id         = request.POST.get('moeda_id') or None
        dado_bancario_id = request.POST.get('dado_bancario_id') or None
        estado_id        = request.POST.get('estado_id') or None
        data_emissao     = request.POST.get('data_emissao')
        data_vencimento  = request.POST.get('data_vencimento') or None
        desconto         = _parse_decimal(request.POST.get('desconto', '0'))
        iva_pct          = _parse_decimal(request.POST.get('iva_pct', '16'), '16')
        observacoes      = request.POST.get('observacoes', '').strip() or None
        termos           = request.POST.get('termos', '').strip() or None

        itens_raw = json.loads(request.POST.get('itens_json', '[]'))

        # Calcular subtotal a partir dos itens
        subtotal = sum(
            _parse_decimal(it.get('quantidade', '1'), '1') * _parse_decimal(it.get('preco_unit', '0'))
            for it in itens_raw
            if it.get('descricao', '').strip()
        )

        _, iva_valor, total = _calcular_totais(subtotal, desconto, iva_pct)

        # Estado
        if estado_id:
            estado = get_object_or_404(FacturaEstado, id=estado_id)
        else:
            estado = _get_estado_rascunho()

        factura = Factura.objects.create(
            numero           = _generate_factura_number(),
            purchase_order_id= po_id,
            estado           = estado,
            cliente_id       = cliente_id,
            moeda_id         = moeda_id,
            dado_bancario_id = dado_bancario_id,
            data_emissao     = data_emissao,
            data_vencimento  = data_vencimento,
            subtotal         = subtotal,
            desconto         = desconto,
            desconto_pct     = (desconto / subtotal * 100).quantize(Decimal('0.01')) if subtotal > 0 else Decimal('0'),
            iva_pct          = iva_pct,
            iva_valor        = iva_valor,
            total            = total,
            observacoes      = observacoes,
            termos           = termos,
            criado_por       = request.user,
        )

        _save_itens(factura, itens_raw)

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

    # Não permite editar facturas canceladas
    if factura.estado and factura.estado.codigo == 'cancelada':
        return JsonResponse({'success': False, 'message': 'Não é possível editar uma factura cancelada.'}, status=400)

    try:
        po_id            = request.POST.get('purchase_order_id') or None
        cliente_id       = request.POST.get('cliente_id')
        moeda_id         = request.POST.get('moeda_id') or None
        dado_bancario_id = request.POST.get('dado_bancario_id') or None
        estado_id        = request.POST.get('estado_id') or None
        data_emissao     = request.POST.get('data_emissao')
        data_vencimento  = request.POST.get('data_vencimento') or None
        desconto         = _parse_decimal(request.POST.get('desconto', '0'))
        iva_pct          = _parse_decimal(request.POST.get('iva_pct', '16'), '16')
        observacoes      = request.POST.get('observacoes', '').strip() or None
        termos           = request.POST.get('termos', '').strip() or None

        itens_raw = json.loads(request.POST.get('itens_json', '[]'))

        subtotal = sum(
            _parse_decimal(it.get('quantidade', '1'), '1') * _parse_decimal(it.get('preco_unit', '0'))
            for it in itens_raw
            if it.get('descricao', '').strip()
        )

        _, iva_valor, total = _calcular_totais(subtotal, desconto, iva_pct)

        if estado_id:
            factura.estado = get_object_or_404(FacturaEstado, id=estado_id)

        factura.purchase_order_id = po_id
        factura.cliente_id        = cliente_id
        factura.moeda_id          = moeda_id
        factura.dado_bancario_id  = dado_bancario_id
        factura.data_emissao      = data_emissao
        factura.data_vencimento   = data_vencimento
        factura.subtotal          = subtotal
        factura.desconto          = desconto
        factura.desconto_pct      = (desconto / subtotal * 100).quantize(Decimal('0.01')) if subtotal > 0 else Decimal('0')
        factura.iva_pct           = iva_pct
        factura.iva_valor         = iva_valor
        factura.total             = total
        factura.observacoes       = observacoes
        factura.termos            = termos
        factura.save()

        _save_itens(factura, itens_raw)

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
    factura   = get_object_or_404(Factura, id=factura_id)
    estado_id = request.POST.get('estado_id')
    estado    = get_object_or_404(FacturaEstado, id=estado_id, activo=True)

    # Validação: se já existe pagamento completo, não pode ser "paga" novamente manualmente — só informativo
    factura.estado = estado
    factura.save(update_fields=['estado', 'actualizado_em'])

    return JsonResponse({'success': True, 'message': f'Estado alterado para "{estado.nome}".'})


@login_required
@require_GET
def factura_pdf_view(request, factura_id):
    """Gera e devolve o PDF da factura usando ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
    import io

    factura = get_object_or_404(
        Factura.objects.select_related(
            'cliente', 'moeda', 'estado', 'dado_bancario',
            'purchase_order', 'purchase_order__quotacao',
        ),
        id=factura_id,
    )

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18*mm, leftMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title=f'Factura {factura.numero}',
    )

    W, H = A4
    col_w = W - 36*mm

    # ── Cores ──────────────────────────────────────────────────────────────
    BLUE       = colors.HexColor('#2E3E82')
    BLUE_LIGHT = colors.HexColor('#eef2ff')
    GREY_LINE  = colors.HexColor('#dee2e6')
    GREY_TEXT  = colors.HexColor('#6c757d')
    WHITE      = colors.white
    BLACK      = colors.HexColor('#1f2937')

    styles = getSampleStyleSheet()

    def sty(name, **kw):
        base = styles[name]
        return ParagraphStyle(name + str(id(kw)), parent=base, **kw)

    title_sty   = sty('Normal', fontSize=22, textColor=WHITE, fontName='Helvetica-Bold', leading=28)
    label_sty   = sty('Normal', fontSize=8,  textColor=GREY_TEXT, fontName='Helvetica', leading=11)
    value_sty   = sty('Normal', fontSize=10, textColor=BLACK, fontName='Helvetica-Bold', leading=14)
    normal_sty  = sty('Normal', fontSize=9,  textColor=BLACK, fontName='Helvetica', leading=13)
    small_sty   = sty('Normal', fontSize=8,  textColor=GREY_TEXT, fontName='Helvetica', leading=11)
    right_sty   = sty('Normal', fontSize=9,  textColor=BLACK, fontName='Helvetica', leading=13, alignment=TA_RIGHT)
    right_b_sty = sty('Normal', fontSize=10, textColor=BLACK, fontName='Helvetica-Bold', leading=14, alignment=TA_RIGHT)
    total_sty   = sty('Normal', fontSize=12, textColor=WHITE, fontName='Helvetica-Bold', leading=16, alignment=TA_RIGHT)
    sym = factura.moeda.simbolo if factura.moeda else ''

    def fmt(v):
        try:
            return f'{sym} {float(v):,.2f}'.strip()
        except Exception:
            return str(v)

    story = []

    # ── Cabeçalho azul ─────────────────────────────────────────────────────
    header_data = [[
        Paragraph('<b>GARMUTTI</b><br/><font size="10" color="#ffffff">Empreendimentos, Lda</font>', title_sty),
        Paragraph(f'FACTURA<br/><font size="13">{factura.numero}</font>', sty('Normal', fontSize=22, textColor=WHITE, fontName='Helvetica-Bold', leading=26, alignment=TA_RIGHT)),
    ]]
    header_tbl = Table(header_data, colWidths=[col_w * 0.55, col_w * 0.45])
    header_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BLUE),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 14),
        ('BOTTOMPADDING',(0,0),(-1,-1),14),
        ('LEFTPADDING', (0,0),(0,-1), 14),
        ('RIGHTPADDING',(-1,0),(-1,-1),14),
        ('ROUNDEDCORNERS', [8, 8, 8, 8]),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 10*mm))

    # ── Info: cliente + datas ───────────────────────────────────────────────
    cli = factura.cliente
    info_data = [[
        # Coluna esquerda — cliente
        Table([
            [Paragraph('FACTURADO A', label_sty)],
            [Paragraph(cli.nome if cli else '—', value_sty)],
            [Paragraph(getattr(cli, 'nuit', '') or '', small_sty)],
            [Paragraph(getattr(cli, 'endereco', '') or '', small_sty)],
            [Paragraph(getattr(cli, 'email', '') or '', small_sty)],
        ], colWidths=[col_w * 0.45], style=[('BOTTOMPADDING',(0,0),(-1,-1),2)]),

        # Coluna direita — datas e referências
        Table([
            [Paragraph('DATA DE EMISSÃO', label_sty),
             Paragraph(factura.data_emissao.strftime('%d/%m/%Y') if factura.data_emissao else '—', value_sty)],
            [Paragraph('DATA DE VENCIMENTO', label_sty),
             Paragraph(factura.data_vencimento.strftime('%d/%m/%Y') if factura.data_vencimento else '—', value_sty)],
            [Paragraph('PO DO CLIENTE', label_sty),
             Paragraph(factura.purchase_order.po_cliente_numero if factura.purchase_order and factura.purchase_order.po_cliente_numero else '—', value_sty)],
            [Paragraph('ESTADO', label_sty),
             Paragraph(factura.estado.nome if factura.estado else '—', value_sty)],
        ], colWidths=[col_w * 0.28, col_w * 0.27],
           style=[('BOTTOMPADDING',(0,0),(-1,-1),4),('ALIGN',(1,0),(1,-1),'RIGHT')]),
    ]]
    info_tbl = Table(info_data, colWidths=[col_w * 0.45, col_w * 0.55])
    info_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0),(-1,-1),'TOP'),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 8*mm))

    # ── Tabela de itens ─────────────────────────────────────────────────────
    col_desc = col_w * 0.42
    col_un   = col_w * 0.10
    col_qty  = col_w * 0.12
    col_pu   = col_w * 0.18
    col_tot  = col_w * 0.18

    item_header = [
        Paragraph('<b>Descrição</b>', sty('Normal', fontSize=8, textColor=WHITE, fontName='Helvetica-Bold')),
        Paragraph('<b>Unid.</b>',     sty('Normal', fontSize=8, textColor=WHITE, fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Paragraph('<b>Qtd.</b>',      sty('Normal', fontSize=8, textColor=WHITE, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
        Paragraph('<b>Preço Unit.</b>',sty('Normal', fontSize=8, textColor=WHITE, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
        Paragraph('<b>Total</b>',     sty('Normal', fontSize=8, textColor=WHITE, fontName='Helvetica-Bold', alignment=TA_RIGHT)),
    ]

    rows = [item_header]
    for it in factura.itens.all():
        rows.append([
            Paragraph(it.descricao, normal_sty),
            Paragraph(it.unidade or '', sty('Normal', fontSize=9, textColor=BLACK, alignment=TA_CENTER)),
            Paragraph(f'{float(it.quantidade):g}', right_sty),
            Paragraph(fmt(it.preco_unit), right_sty),
            Paragraph(fmt(it.total_linha), right_sty),
        ])

    items_tbl = Table(rows, colWidths=[col_desc, col_un, col_qty, col_pu, col_tot])
    items_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,0),  BLUE),
        ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, BLUE_LIGHT]),
        ('GRID',          (0,0), (-1,-1), 0.4, GREY_LINE),
        ('TOPPADDING',    (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING',   (0,0), (0,-1),  8),
        ('RIGHTPADDING',  (-1,0),(-1,-1), 8),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(items_tbl)
    story.append(Spacer(1, 6*mm))

    # ── Totais ──────────────────────────────────────────────────────────────
    totais_data = [
        [Paragraph('Subtotal', normal_sty),         Paragraph(fmt(factura.subtotal),  right_sty)],
        [Paragraph(f'Desconto ({factura.desconto_pct}%)', normal_sty), Paragraph(f'- {fmt(factura.desconto)}', right_sty)],
        [Paragraph(f'IVA ({factura.iva_pct}%)',     normal_sty),       Paragraph(fmt(factura.iva_valor), right_sty)],
    ]
    totais_tbl = Table(totais_data, colWidths=[col_w * 0.75, col_w * 0.25])
    totais_tbl.setStyle(TableStyle([
        ('ALIGN',        (1,0), (1,-1), 'RIGHT'),
        ('TOPPADDING',   (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0), (-1,-1), 4),
        ('LINEBELOW',    (0,-1),(-1,-1), 0.5, GREY_LINE),
    ]))
    story.append(totais_tbl)
    story.append(Spacer(1, 2*mm))

    total_data = [[
        Paragraph('', normal_sty),
        Table([[Paragraph('TOTAL', total_sty), Paragraph(fmt(factura.total), total_sty)]],
              colWidths=[col_w * 0.12, col_w * 0.13],
              style=[
                  ('BACKGROUND', (0,0),(-1,-1), BLUE),
                  ('TOPPADDING', (0,0),(-1,-1), 8),
                  ('BOTTOMPADDING',(0,0),(-1,-1),8),
                  ('LEFTPADDING',(0,0),(0,-1),10),
                  ('RIGHTPADDING',(-1,0),(-1,-1),10),
                  ('ROUNDEDCORNERS',[6,6,6,6]),
              ]),
    ]]
    total_tbl = Table(total_data, colWidths=[col_w * 0.75, col_w * 0.25])
    story.append(total_tbl)
    story.append(Spacer(1, 8*mm))

    # ── Dados bancários ─────────────────────────────────────────────────────
    if factura.dado_bancario:
        db = factura.dado_bancario
        banco_rows = [[Paragraph('DADOS PARA PAGAMENTO', sty('Normal', fontSize=8, textColor=WHITE, fontName='Helvetica-Bold'))]]
        banco_tbl_header = Table(banco_rows, colWidths=[col_w])
        banco_tbl_header.setStyle(TableStyle([
            ('BACKGROUND', (0,0),(-1,-1), BLUE),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
            ('LEFTPADDING',(0,0),(-1,-1),10),
        ]))
        story.append(banco_tbl_header)

        fields = []
        if db.banco:    fields.append(('Banco', db.banco))
        if db.titular:  fields.append(('Titular', db.titular))
        if db.conta:    fields.append(('Nº Conta', db.conta))
        if db.nib:      fields.append(('NIB', db.nib))
        if db.iban:     fields.append(('IBAN', db.iban))
        if db.swift:    fields.append(('SWIFT', db.swift))
        if db.moeda:    fields.append(('Moeda', db.moeda))

        banco_data = [[Paragraph(k, label_sty), Paragraph(v, value_sty)] for k, v in fields]
        banco_body = Table(banco_data, colWidths=[col_w * 0.25, col_w * 0.75])
        banco_body.setStyle(TableStyle([
            ('BACKGROUND', (0,0),(-1,-1), BLUE_LIGHT),
            ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
            ('LEFTPADDING',(0,0),(-1,-1),10),
            ('LINEBELOW',(0,0),(-1,-2),0.3,GREY_LINE),
        ]))
        story.append(banco_body)
        story.append(Spacer(1, 6*mm))

    # ── Observações e termos ────────────────────────────────────────────────
    if factura.observacoes:
        story.append(Paragraph('OBSERVAÇÕES', label_sty))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(factura.observacoes, normal_sty))
        story.append(Spacer(1, 4*mm))

    if factura.termos:
        story.append(HRFlowable(width='100%', thickness=0.5, color=GREY_LINE))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph('TERMOS E CONDIÇÕES', label_sty))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(factura.termos, small_sty))

    # ── Rodapé ──────────────────────────────────────────────────────────────
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=GREY_LINE))
    story.append(Spacer(1, 3*mm))
    footer_data = [[
        Paragraph('Garmutti Empreendimentos, Lda  |  garmutti.co.mz', small_sty),
        Paragraph(f'Documento gerado automaticamente  |  {factura.numero}',
                  sty('Normal', fontSize=8, textColor=GREY_TEXT, alignment=TA_RIGHT)),
    ]]
    footer_tbl = Table(footer_data, colWidths=[col_w * 0.6, col_w * 0.4])
    story.append(footer_tbl)

    doc.build(story)
    buffer.seek(0)

    response = FileResponse(
        buffer,
        as_attachment=False,
        filename=f'Factura_{factura.numero.replace("/","_")}.pdf',
        content_type='application/pdf',
    )
    return response


@login_required
@require_GET
def po_itens_json_view(request, po_id):
    """
    Devolve itens e termos da Quotação ligada à PO.
    Se não existir Quotação, devolve uma linha genérica com o valor da PO.
    """
    po = get_object_or_404(
        PurchaseOrder.objects.select_related(
            'quotacao', 'quotacao__condicao_pagamento', 'cliente', 'moeda'
        ),
        id=po_id,
    )

    itens  = []
    termos = ''
    quotacao_numero   = ''
    quot_download_url = ''
    po_download_url   = ''

    # ── Itens e termos da Quotação ────────────────────────────────────────
    if po.quotacao:
        q = po.quotacao
        quotacao_numero = q.numero

        # URL PDF da quotação (usa weasyprint — rota já existente)
        try:
            quot_download_url = reverse('procurement:quotacoes_download_pdf', args=[q.id])
        except Exception:
            pass

        # Termos: condição de pagamento da quotação
        if q.condicao_pagamento and q.condicao_pagamento.descricao:
            termos = q.condicao_pagamento.descricao
        elif q.observacoes:
            termos = q.observacoes

        # Itens da quotação → itens da factura
        for it in QuotacaoItem.objects.filter(quotacao_id=q.id).order_by('linha'):
            itens.append({
                'descricao' : it.descricao,
                'unidade'   : it.unidade.sigla if it.unidade else '',
                'quantidade': str(it.quantidade),
                'preco_unit': str(it.preco_unitario),
            })

    # ── Fallback: linha genérica com valor da PO ──────────────────────────
    if not itens:
        itens = [{
            'descricao' : f'Fornecimento conforme PO {po.po_cliente_numero or po.numero}',
            'unidade'   : 'un',
            'quantidade': '1',
            'preco_unit': str(po.valor_total or '0'),
        }]

    # ── URL download da PO (primeiro anexo tipo 'po') ─────────────────────
    po_anexo = PurchaseOrderAnexo.objects.filter(
        purchase_order_id=po.id, tipo_anexo='po'
    ).first()
    if po_anexo:
        try:
            po_download_url = reverse('procurement:po_anexo_download', args=[po_anexo.id])
        except Exception:
            pass

    return JsonResponse({
        'po_numero'        : po.numero,
        'po_cliente_numero': po.po_cliente_numero or '',
        'po_valor_total'   : str(po.valor_total or '0'),
        'cliente_id'       : po.cliente_id,
        'moeda_id'         : po.moeda_id or '',
        'quotacao_numero'  : quotacao_numero,
        'quot_download_url': quot_download_url,
        'po_download_url'  : po_download_url,
        'termos'           : termos,
        'itens'            : itens,
    })