from datetime import datetime
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET
from weasyprint import HTML

from procurement.models import (
    Cliente,
    Factura,
    Fornecedor,
    GuiaEntrega,
    Pagamento,
    PagamentoHistorico,
    PurchaseOrder,
    Quotacao,
    Recibo,
    RFQ,
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        return None


def _get_organizacao():
    try:
        from procurement.models import Organizacao
        return Organizacao.objects.filter(activo=True).order_by('id').first()
    except Exception:
        return None


def _apply_date_filter(qs, field_name, data_inicio=None, data_fim=None):
    if data_inicio:
        qs = qs.filter(**{f"{field_name}__gte": data_inicio})
    if data_fim:
        qs = qs.filter(**{f"{field_name}__lte": data_fim})
    return qs


def _get_report_config(report_type):
    """
    Define:
    - queryset base
    - nome amigável
    - campo de data
    """
    reports = {
        'clientes': {
            'title': 'Relatório de Clientes',
            'qs': Cliente.objects.all().order_by('nome'),
            'date_field': 'criado_em',
        },
        'fornecedores': {
            'title': 'Relatório de Fornecedores',
            'qs': Fornecedor.objects.all().order_by('nome'),
            'date_field': 'criado_em',
        },
        'rfqs': {
            'title': 'Relatório de RFQs',
            'qs': RFQ.objects.select_related('cliente', 'estado').order_by('-id'),
            'date_field': 'data_rfq',
        },
        'quotacoes': {
            'title': 'Relatório de Quotações',
            'qs': Quotacao.objects.select_related('cliente', 'estado', 'moeda').order_by('-id'),
            'date_field': 'data_quotacao',
        },
        'purchase_orders': {
            'title': 'Relatório de Purchase Orders',
            'qs': PurchaseOrder.objects.select_related('cliente', 'estado', 'moeda').order_by('-id'),
            'date_field': 'data_po',
        },
        'facturas': {
            'title': 'Relatório de Facturas',
            'qs': Factura.objects.select_related('cliente', 'estado', 'moeda', 'purchase_order').order_by('-id'),
            'date_field': 'data_emissao',
        },
        'guias': {
            'title': 'Relatório de Guias de Entrega',
            'qs': GuiaEntrega.objects.select_related('cliente', 'estado', 'moeda', 'factura').order_by('-id'),
            'date_field': 'data_guia',
        },
        'pagamentos': {
            'title': 'Relatório de Pagamentos',
            'qs': Pagamento.objects.select_related('cliente', 'estado', 'moeda', 'purchase_order').order_by('-id'),
            'date_field': 'data_pagamento_prevista',
        },
        'pagamento_historico': {
            'title': 'Relatório de Histórico de Pagamentos',
            'qs': PagamentoHistorico.objects.select_related(
                'pagamento', 'pagamento__cliente', 'factura', 'dado_bancario'
            ).order_by('-id'),
            'date_field': 'data_pagamento',
        },
        'recibos': {
            'title': 'Relatório de Recibos',
            'qs': Recibo.objects.select_related('cliente', 'factura', 'moeda').order_by('-id'),
            'date_field': 'data_recibo',
        },
    }
    return reports.get(report_type)


def _build_report_data(report_type, data_inicio=None, data_fim=None):
    config = _get_report_config(report_type)
    if not config:
        return None

    qs = _apply_date_filter(config['qs'], config['date_field'], data_inicio, data_fim)

    rows = []
    summary = {
        'total_registos': 0,
        'valor_total': Decimal('0.00'),
    }

    if report_type == 'clientes':
        rows = list(qs)
        summary['total_registos'] = len(rows)

    elif report_type == 'fornecedores':
        rows = list(qs)
        summary['total_registos'] = len(rows)

    elif report_type == 'rfqs':
        rows = list(qs)
        summary['total_registos'] = len(rows)

    elif report_type == 'quotacoes':
        rows = list(qs)
        summary['total_registos'] = len(rows)
        summary['valor_total'] = qs.aggregate(t=Sum('total')).get('t') or Decimal('0.00')

    elif report_type == 'purchase_orders':
        rows = list(qs)
        summary['total_registos'] = len(rows)
        summary['valor_total'] = qs.aggregate(t=Sum('valor_total')).get('t') or Decimal('0.00')

    elif report_type == 'facturas':
        rows = list(qs)
        summary['total_registos'] = len(rows)
        summary['valor_total'] = qs.aggregate(t=Sum('total')).get('t') or Decimal('0.00')

    elif report_type == 'guias':
        rows = list(qs)
        summary['total_registos'] = len(rows)
        summary['valor_total'] = qs.aggregate(t=Sum('subtotal')).get('t') or Decimal('0.00')

    elif report_type == 'pagamentos':
        rows = list(qs)
        summary['total_registos'] = len(rows)
        summary['valor_total'] = qs.aggregate(t=Sum('valor_recebido')).get('t') or Decimal('0.00')

    elif report_type == 'pagamento_historico':
        rows = list(qs)
        summary['total_registos'] = len(rows)
        summary['valor_total'] = qs.aggregate(t=Sum('valor_pago')).get('t') or Decimal('0.00')

    elif report_type == 'recibos':
        rows = list(qs)
        summary['total_registos'] = len(rows)
        summary['valor_total'] = qs.filter(anulado=False).aggregate(t=Sum('valor_recebido')).get('t') or Decimal('0.00')

    return {
        'title': config['title'],
        'report_type': report_type,
        'rows': rows,
        'summary': summary,
        'date_field': config['date_field'],
    }


# ---------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------

@login_required
@require_GET
def reports_view(request):
    today = timezone.localdate()

    report_cards = [
        {'key': 'clientes', 'title': 'Clientes', 'icon': 'groups', 'desc': 'Lista completa de clientes'},
        {'key': 'fornecedores', 'title': 'Fornecedores', 'icon': 'inventory_2', 'desc': 'Lista completa de fornecedores'},
        {'key': 'rfqs', 'title': 'RFQs', 'icon': 'request_quote', 'desc': 'Pedidos de cotação'},
        {'key': 'quotacoes', 'title': 'Quotações', 'icon': 'description', 'desc': 'Relatório de quotações emitidas'},
        {'key': 'purchase_orders', 'title': 'Purchase Orders', 'icon': 'receipt_long', 'desc': 'Ordens de compra'},
        {'key': 'facturas', 'title': 'Facturas', 'icon': 'article', 'desc': 'Facturação emitida'},
        {'key': 'guias', 'title': 'Guias de Entrega', 'icon': 'local_shipping', 'desc': 'Guias e entregas'},
        {'key': 'pagamentos', 'title': 'Pagamentos', 'icon': 'payments', 'desc': 'Pagamentos e saldos'},
        {'key': 'pagamento_historico', 'title': 'Histórico de Pagamentos', 'icon': 'history', 'desc': 'Movimentos de pagamento'},
        {'key': 'recibos', 'title': 'Recibos', 'icon': 'receipt', 'desc': 'Recibos emitidos'},
    ]

    context = {
        'segment': 'relatorios',
        'today': today.isoformat(),
        'report_cards': report_cards,
    }
    return render(request, 'relatorios/relatorios.html', context)


@login_required
@require_GET
def reports_preview_json_view(request):
    report_type = request.GET.get('report_type', '').strip()
    data_inicio = _parse_date(request.GET.get('data_inicio'))
    data_fim = _parse_date(request.GET.get('data_fim'))

    report_data = _build_report_data(report_type, data_inicio, data_fim)
    if not report_data:
        return JsonResponse({'success': False, 'message': 'Tipo de relatório inválido.'}, status=400)

    rows = report_data['rows'][:10]  # preview limitado

    preview_rows = []
    for row in rows:
        if report_type == 'clientes':
            preview_rows.append({
                'col1': row.nome,
                'col2': row.nuit or '—',
                'col3': row.email or '—',
                'col4': 'Activo' if row.estado else 'Inactivo',
            })

        elif report_type == 'fornecedores':
            preview_rows.append({
                'col1': row.nome,
                'col2': row.nuit or '—',
                'col3': row.email or '—',
                'col4': 'Activo' if row.estado else 'Inactivo',
            })

        elif report_type == 'rfqs':
            preview_rows.append({
                'col1': row.numero,
                'col2': row.cliente.nome if row.cliente else '—',
                'col3': row.data_rfq.strftime('%d/%m/%Y') if row.data_rfq else '—',
                'col4': row.estado.nome if row.estado else '—',
            })

        elif report_type == 'quotacoes':
            preview_rows.append({
                'col1': row.numero,
                'col2': row.cliente.nome if row.cliente else '—',
                'col3': f'{row.total:.2f}',
                'col4': row.estado.nome if row.estado else '—',
            })

        elif report_type == 'purchase_orders':
            preview_rows.append({
                'col1': row.numero,
                'col2': row.cliente.nome if row.cliente else '—',
                'col3': f'{row.valor_total:.2f}',
                'col4': row.estado.nome if row.estado else '—',
            })

        elif report_type == 'facturas':
            preview_rows.append({
                'col1': row.numero,
                'col2': row.cliente.nome if row.cliente else '—',
                'col3': f'{row.total:.2f}',
                'col4': row.estado.nome if row.estado else '—',
            })

        elif report_type == 'guias':
            preview_rows.append({
                'col1': row.numero,
                'col2': row.cliente.nome if row.cliente else '—',
                'col3': row.data_guia.strftime('%d/%m/%Y') if row.data_guia else '—',
                'col4': row.estado.nome if row.estado else '—',
            })

        elif report_type == 'pagamentos':
            preview_rows.append({
                'col1': row.numero,
                'col2': row.cliente.nome if row.cliente else '—',
                'col3': f'{row.valor_recebido:.2f}',
                'col4': row.estado.nome if row.estado else '—',
            })

        elif report_type == 'pagamento_historico':
            preview_rows.append({
                'col1': row.pagamento.numero if row.pagamento else '—',
                'col2': row.factura.numero if row.factura else '—',
                'col3': f'{row.valor_pago:.2f}',
                'col4': row.data_pagamento.strftime('%d/%m/%Y') if row.data_pagamento else '—',
            })

        elif report_type == 'recibos':
            preview_rows.append({
                'col1': row.numero,
                'col2': row.factura.numero if row.factura else '—',
                'col3': f'{row.valor_recebido:.2f}',
                'col4': 'Anulado' if row.anulado else 'Activo',
            })

    return JsonResponse({
        'success': True,
        'title': report_data['title'],
        'total_registos': report_data['summary']['total_registos'],
        'valor_total': f"{report_data['summary']['valor_total']:.2f}",
        'rows': preview_rows,
    })


@login_required
@require_GET
def reports_pdf_view(request):
    report_type = request.GET.get('report_type', '').strip()
    data_inicio = _parse_date(request.GET.get('data_inicio'))
    data_fim = _parse_date(request.GET.get('data_fim'))

    report_data = _build_report_data(report_type, data_inicio, data_fim)
    if not report_data:
        return HttpResponse('Tipo de relatório inválido.', status=400)

    organizacao = _get_organizacao()

    html_string = render_to_string(
        'relatorios/relatorios_pdf.html',
        {
            'report': report_data,
            'organizacao': organizacao,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'gerado_em': timezone.localtime(),
        },
        request=request,
    )

    pdf_file = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/'),
    ).write_pdf()

    filename = f"{report_type}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response