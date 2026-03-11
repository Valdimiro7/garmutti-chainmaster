from datetime import timedelta
from decimal import Decimal
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from procurement.models import PagamentoHistorico

logger = logging.getLogger(__name__)


@login_required
@require_GET
def pagamentos_historico_view(request):
    historicos = (
        PagamentoHistorico.objects
        .select_related(
            'pagamento',
            'pagamento__cliente',
            'pagamento__moeda',
            'pagamento__estado',
            'pagamento__purchase_order',
            'pagamento__purchase_order__quotacao',
            'dado_bancario',
            'factura',
            'factura__estado',
            'registado_por',
        )
        .order_by('-data_pagamento', '-id')
    )

    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    total_registos = historicos.count()

    total_valor = (
        historicos.aggregate(total=Sum('valor_pago')).get('total') or Decimal('0')
    )

    total_hoje = (
        historicos.filter(data_pagamento=today)
        .aggregate(total=Sum('valor_pago')).get('total') or Decimal('0')
    )

    total_semana = (
        historicos.filter(data_pagamento__gte=week_start, data_pagamento__lte=today)
        .aggregate(total=Sum('valor_pago')).get('total') or Decimal('0')
    )

    total_mes = (
        historicos.filter(data_pagamento__gte=month_start, data_pagamento__lte=today)
        .aggregate(total=Sum('valor_pago')).get('total') or Decimal('0')
    )

    total_com_factura = historicos.filter(factura__isnull=False).count()
    total_sem_factura = historicos.filter(factura__isnull=True).count()

    total_com_po = historicos.filter(pagamento__purchase_order__isnull=False).count()
    total_sem_po = historicos.filter(pagamento__purchase_order__isnull=True).count()

    clientes_unicos = (
        historicos.values('pagamento__cliente_id').distinct().count()
    )

    context = {
        'segment': 'historico_pagamentos',
        'historicos': historicos,
        'total_registos': total_registos,
        'total_valor': total_valor,
        'total_hoje': total_hoje,
        'total_semana': total_semana,
        'total_mes': total_mes,
        'total_com_factura': total_com_factura,
        'total_sem_factura': total_sem_factura,
        'total_com_po': total_com_po,
        'total_sem_po': total_sem_po,
        'clientes_unicos': clientes_unicos,
        'today': today.isoformat(),
    }
    return render(request, 'pagamentos/historico_pagamentos.html', context)


@login_required
@require_GET
def pagamento_historico_detail_json_view(request, historico_id):
    historico = get_object_or_404(
        PagamentoHistorico.objects.select_related(
            'pagamento',
            'pagamento__cliente',
            'pagamento__moeda',
            'pagamento__estado',
            'pagamento__purchase_order',
            'pagamento__purchase_order__quotacao',
            'dado_bancario',
            'factura',
            'factura__estado',
            'registado_por',
        ),
        id=historico_id,
    )

    pagamento = historico.pagamento
    po = pagamento.purchase_order if pagamento else None
    factura = historico.factura

    data = {
        'id': historico.id,
        'valor_pago': str(historico.valor_pago),
        'data_pagamento': historico.data_pagamento.isoformat() if historico.data_pagamento else '',
        'referencia': historico.referencia or '',
        'banco_origem': historico.banco_origem or '',
        'numero_transaccao': historico.numero_transaccao or '',
        'observacoes': historico.observacoes or '',
        'criado_em': historico.criado_em.isoformat() if historico.criado_em else '',
        'registado_por': (
            historico.registado_por.get_full_name().strip()
            if historico.registado_por and historico.registado_por.get_full_name().strip()
            else (historico.registado_por.username if historico.registado_por else '')
        ),

        'pagamento_id': pagamento.id if pagamento else '',
        'pagamento_numero': pagamento.numero if pagamento else '',
        'pagamento_estado': pagamento.estado.nome if pagamento and pagamento.estado else '',
        'pagamento_estado_codigo': pagamento.estado.codigo if pagamento and pagamento.estado else '',
        'cliente_nome': pagamento.cliente.nome if pagamento and pagamento.cliente else '',
        'moeda_simbolo': pagamento.moeda.simbolo if pagamento and pagamento.moeda else '',
        'moeda_codigo': pagamento.moeda.codigo if pagamento and pagamento.moeda else '',
        'valor_po': str(pagamento.valor_po) if pagamento else '0',
        'valor_recebido': str(pagamento.valor_recebido) if pagamento else '0',
        'saldo_pendente': str(pagamento.saldo_pendente) if pagamento else '0',
        'pagamento_data_prevista': pagamento.data_pagamento_prevista.isoformat() if pagamento and pagamento.data_pagamento_prevista else '',
        'pagamento_data_recebido': pagamento.data_pagamento_recebido.isoformat() if pagamento and pagamento.data_pagamento_recebido else '',
        'pagamento_referencia': pagamento.referencia_pagamento if pagamento else '',
        'pagamento_banco_origem': pagamento.banco_origem if pagamento else '',
        'pagamento_numero_transaccao': pagamento.numero_transaccao if pagamento else '',
        'pagamento_observacoes': pagamento.observacoes if pagamento else '',

        'po_numero': po.numero if po else '',
        'po_cliente_numero': po.po_cliente_numero if po else '',
        'po_valor_total': str(po.valor_total) if po else '0',
        'quotacao_numero': po.quotacao.numero if po and po.quotacao else '',

        'factura_id': factura.id if factura else '',
        'factura_numero': factura.numero if factura else '',
        'factura_estado': factura.estado.nome if factura and factura.estado else '',
        'factura_total': str(factura.total) if factura else '0',

        'dado_bancario': {
            'label': historico.dado_bancario.label_completo if historico.dado_bancario else '',
            'banco': historico.dado_bancario.banco if historico.dado_bancario else '',
            'moeda': historico.dado_bancario.moeda if historico.dado_bancario else '',
            'conta': historico.dado_bancario.conta if historico.dado_bancario else '',
            'nib': historico.dado_bancario.nib if historico.dado_bancario else '',
            'swift': historico.dado_bancario.swift if historico.dado_bancario else '',
            'iban': historico.dado_bancario.iban if historico.dado_bancario else '',
            'titular': historico.dado_bancario.titular if historico.dado_bancario else '',
        },
    }
    return JsonResponse(data)