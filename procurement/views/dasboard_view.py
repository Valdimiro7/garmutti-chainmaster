from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.shortcuts import render
from django.utils import timezone

from procurement.models import (
    Cliente,
    Factura,
    Fornecedor,
    GuiaEntrega,
    Pagamento,
    PagamentoHistorico,
    PurchaseOrder,
    Quotacao,
    RFQ,
    Recibo,
)


@login_required
def dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=today.weekday())
    last_30_days = today - timedelta(days=29)

    # ─────────────────────────────────────────────────────────────
    # KPIs Principais
    # ─────────────────────────────────────────────────────────────
    total_clientes = Cliente.objects.filter(estado=True).count()
    total_fornecedores = Fornecedor.objects.filter(estado=True).count()
    total_rfqs = RFQ.objects.count()
    total_quotacoes = Quotacao.objects.count()
    total_pos = PurchaseOrder.objects.count()
    total_facturas = Factura.objects.count()
    total_pagamentos = Pagamento.objects.count()
    total_guias = GuiaEntrega.objects.count()
    total_recibos = Recibo.objects.count()

    rfqs_novas = RFQ.objects.filter(estado__codigo='novo').count()
    quotacoes_pendentes = Quotacao.objects.filter(estado__codigo='pendente').count()
    facturas_pendentes = Factura.objects.filter(estado__codigo='pendente').count()
    pagamentos_pendentes = Pagamento.objects.filter(estado__codigo='pendente').count()
    guias_pendentes = GuiaEntrega.objects.filter(estado__codigo='pendente').count()

    valor_facturado_mes = (
        Factura.objects.filter(
            data_emissao__gte=month_start,
            data_emissao__lte=today
        ).exclude(estado__codigo='cancelada')
        .aggregate(total=Sum('total')).get('total') or Decimal('0')
    )

    valor_recebido_mes = (
        PagamentoHistorico.objects.filter(
            data_pagamento__gte=month_start,
            data_pagamento__lte=today
        ).aggregate(total=Sum('valor_pago')).get('total') or Decimal('0')
    )

    valor_pos_mes = (
        PurchaseOrder.objects.filter(
            data_po__gte=month_start,
            data_po__lte=today
        ).aggregate(total=Sum('valor_total')).get('total') or Decimal('0')
    )

    valor_guias_mes = (
        GuiaEntrega.objects.filter(
            data_guia__gte=month_start,
            data_guia__lte=today
        ).aggregate(total=Sum('subtotal')).get('total') or Decimal('0')
    )

    # ─────────────────────────────────────────────────────────────
    # Gráfico 30 dias – RFQ, Quotações, POs, Facturas
    # ─────────────────────────────────────────────────────────────
    chart_labels = []
    rfq_series = []
    quot_series = []
    po_series = []
    factura_series = []
    pagamento_series = []

    for i in range(30):
        d = last_30_days + timedelta(days=i)
        chart_labels.append(d.strftime('%d/%m'))

        rfq_series.append(RFQ.objects.filter(data_rfq=d).count())
        quot_series.append(Quotacao.objects.filter(data_quotacao=d).count())
        po_series.append(PurchaseOrder.objects.filter(data_po=d).count())
        factura_series.append(Factura.objects.filter(data_emissao=d).count())
        pagamento_series.append(PagamentoHistorico.objects.filter(data_pagamento=d).count())

    # ─────────────────────────────────────────────────────────────
    # Distribuição por estados
    # ─────────────────────────────────────────────────────────────
    pagamentos_estado_qs = (
        Pagamento.objects.values('estado__nome')
        .annotate(total=Count('id'))
        .order_by('estado__nome')
    )
    pagamentos_estado_labels = [x['estado__nome'] or 'Sem Estado' for x in pagamentos_estado_qs]
    pagamentos_estado_values = [x['total'] for x in pagamentos_estado_qs]

    facturas_estado_qs = (
        Factura.objects.values('estado__nome')
        .annotate(total=Count('id'))
        .order_by('estado__nome')
    )
    facturas_estado_labels = [x['estado__nome'] or 'Sem Estado' for x in facturas_estado_qs]
    facturas_estado_values = [x['total'] for x in facturas_estado_qs]

    guias_estado_qs = (
        GuiaEntrega.objects.values('estado__nome')
        .annotate(total=Count('id'))
        .order_by('estado__nome')
    )
    guias_estado_labels = [x['estado__nome'] or 'Sem Estado' for x in guias_estado_qs]
    guias_estado_values = [x['total'] for x in guias_estado_qs]

    # ─────────────────────────────────────────────────────────────
    # Top clientes por facturação
    # ─────────────────────────────────────────────────────────────
    top_clientes = (
        Factura.objects.exclude(estado__codigo='cancelada')
        .values('cliente__nome')
        .annotate(
            total_facturado=Sum('total'),
            total_facturas=Count('id')
        )
        .order_by('-total_facturado')[:8]
    )

    # ─────────────────────────────────────────────────────────────
    # Tabelas recentes
    # ─────────────────────────────────────────────────────────────
    rfqs_recentes = (
        RFQ.objects.select_related('cliente', 'estado')
        .order_by('-id')[:5]
    )

    facturas_recentes = (
        Factura.objects.select_related('cliente', 'estado', 'moeda')
        .order_by('-id')[:5]
    )

    pagamentos_recentes = (
        PagamentoHistorico.objects.select_related(
            'pagamento',
            'pagamento__cliente',
            'pagamento__moeda',
            'factura',
        )
        .order_by('-criado_em')[:5]
    )

    guias_recentes = (
        GuiaEntrega.objects.select_related('cliente', 'estado', 'moeda')
        .order_by('-id')[:5]
    )

    # ─────────────────────────────────────────────────────────────
    # Cartões extras
    # ─────────────────────────────────────────────────────────────
    total_recebido_hoje = (
        PagamentoHistorico.objects.filter(data_pagamento=today)
        .aggregate(total=Sum('valor_pago')).get('total') or Decimal('0')
    )

    total_recebido_semana = (
        PagamentoHistorico.objects.filter(
            data_pagamento__gte=week_start,
            data_pagamento__lte=today
        ).aggregate(total=Sum('valor_pago')).get('total') or Decimal('0')
    )

    context = {
        'segment': 'dashboard',

        'total_clientes': total_clientes,
        'total_fornecedores': total_fornecedores,
        'total_rfqs': total_rfqs,
        'total_quotacoes': total_quotacoes,
        'total_pos': total_pos,
        'total_facturas': total_facturas,
        'total_pagamentos': total_pagamentos,
        'total_guias': total_guias,
        'total_recibos': total_recibos,

        'rfqs_novas': rfqs_novas,
        'quotacoes_pendentes': quotacoes_pendentes,
        'facturas_pendentes': facturas_pendentes,
        'pagamentos_pendentes': pagamentos_pendentes,
        'guias_pendentes': guias_pendentes,

        'valor_facturado_mes': valor_facturado_mes,
        'valor_recebido_mes': valor_recebido_mes,
        'valor_pos_mes': valor_pos_mes,
        'valor_guias_mes': valor_guias_mes,
        'total_recebido_hoje': total_recebido_hoje,
        'total_recebido_semana': total_recebido_semana,

        'chart_labels': chart_labels,
        'rfq_series': rfq_series,
        'quot_series': quot_series,
        'po_series': po_series,
        'factura_series': factura_series,
        'pagamento_series': pagamento_series,

        'pagamentos_estado_labels': pagamentos_estado_labels,
        'pagamentos_estado_values': pagamentos_estado_values,

        'facturas_estado_labels': facturas_estado_labels,
        'facturas_estado_values': facturas_estado_values,

        'guias_estado_labels': guias_estado_labels,
        'guias_estado_values': guias_estado_values,

        'top_clientes': top_clientes,
        'rfqs_recentes': rfqs_recentes,
        'facturas_recentes': facturas_recentes,
        'pagamentos_recentes': pagamentos_recentes,
        'guias_recentes': guias_recentes,
        
        "page_title": "Garmutti ChainMaster",
        "system_name": "Procurement Management System"
    }

    return render(request, 'dashboard/dashboard.html', context)