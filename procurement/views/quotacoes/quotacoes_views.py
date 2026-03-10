from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from weasyprint import HTML

from procurement.models import (
    Cliente,
    Moeda,
    Organizacao,
    Quotacao,
    QuotacaoDescricaoSugerida,
    QuotacaoItem,
    RFQ,
    Unidade,
)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _parse_decimal(value, default='0'):
    try:
        return Decimal(str(value or default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _get_organizacao():
    return Organizacao.objects.filter(activo=True).order_by('id').first()


def _generate_quotacao_number():
    year   = timezone.now().year
    prefix = f'QT-{year}-'
    ultimo = (
        Quotacao.objects
        .filter(numero__startswith=prefix)
        .order_by('-id')
        .first()
    )
    seq = 1
    if ultimo and ultimo.numero:
        try:
            seq = int(ultimo.numero.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f'{prefix}{seq:05d}'


def _calcular_totais(itens_data, percentagem_iva_geral):
    """Recalcula subtotal, IVA e total a partir da lista de dicts de itens."""
    subtotal  = Decimal('0')
    total_iva = Decimal('0')

    for item in itens_data:
        tl  = _parse_decimal(item.get('total_liquido', 0))
        iva = _parse_decimal(item.get('percentagem_iva', percentagem_iva_geral))
        subtotal  += tl
        total_iva += tl * iva / Decimal('100')

    return subtotal, total_iva, subtotal + total_iva


def _upsert_descricao_sugerida(descricao: str):
    """Insere ou incrementa o contador de descrições sugeridas."""
    descricao = descricao.strip()
    if not descricao:
        return
    obj = QuotacaoDescricaoSugerida.objects.filter(descricao=descricao).first()
    if obj:
        QuotacaoDescricaoSugerida.objects.filter(pk=obj.pk).update(vezes=obj.vezes + 1)
    else:
        QuotacaoDescricaoSugerida.objects.create(descricao=descricao)


# ─── list / main view ─────────────────────────────────────────────────────────

@login_required
@require_GET
def quotacoes_view(request):
    quotacoes = (
        Quotacao.objects
        .select_related('cliente', 'rfq', 'moeda', 'criado_por')
        .prefetch_related('itens')
        .order_by('-id')
    )

    clientes  = Cliente.objects.filter(estado=True).order_by('nome')
    unidades  = Unidade.objects.filter(activo=True).order_by('ordem', 'nome')
    moedas    = Moeda.objects.filter(estado=True).order_by('-predefinida', 'codigo')
    rfqs      = (
        RFQ.objects
        .select_related('cliente')
        .exclude(estado__codigo__in=['cancelado', 'fechado'])
        .order_by('-id')
    )

    # Sugestões de descrições (top 200 mais usadas)
    sugestoes = list(
        QuotacaoDescricaoSugerida.objects
        .order_by('-vezes', 'descricao')
        .values_list('descricao', flat=True)[:200]
    )

    # Contadores por estado
    total            = quotacoes.count()
    total_rascunho   = quotacoes.filter(estado='rascunho').count()
    total_enviada    = quotacoes.filter(estado='enviada').count()
    total_aceite     = quotacoes.filter(estado='aceite').count()
    total_cancelada  = quotacoes.filter(estado='cancelada').count()

    moeda_predefinida = moedas.filter(predefinida=True).first() or moedas.first()

    context = {
        'segment':             'quotacoes',
        'quotacoes':           quotacoes,
        'clientes':            clientes,
        'unidades':            unidades,
        'moedas':              moedas,
        'rfqs':                rfqs,
        'sugestoes_json':      sugestoes,
        'total':               total,
        'total_rascunho':      total_rascunho,
        'total_enviada':       total_enviada,
        'total_aceite':        total_aceite,
        'total_cancelada':     total_cancelada,
        'default_numero':      _generate_quotacao_number(),
        'today':               date.today().isoformat(),
        'moeda_predefinida_id': moeda_predefinida.id if moeda_predefinida else '',
    }
    return render(request, 'quotacoes/quotacoes.html', context)


# ─── detail JSON (para modal editar) ──────────────────────────────────────────

@login_required
@require_GET
def quotacao_detail_json_view(request, quotacao_id):
    q = get_object_or_404(
        Quotacao.objects.select_related('cliente', 'moeda', 'rfq'),
        id=quotacao_id,
    )

    itens = list(
        q.itens.select_related('unidade').values(
            'id', 'linha', 'descricao', 'quantidade',
            'unidade_id', 'preco_unitario', 'percentagem_iva',
            'total_liquido', 'comentarios', 'especificacoes',
        )
    )

    data = {
        'id':                  q.id,
        'numero':              q.numero,
        'estado':              q.estado,
        'rfq_id':              q.rfq_id,
        'cliente_id':          q.cliente_id,
        'moeda_id':            q.moeda_id,
        'data_quotacao':       q.data_quotacao.isoformat() if q.data_quotacao else '',
        'validade':            q.validade.isoformat() if q.validade else '',
        'prazo_entrega':       q.prazo_entrega or '',
        'local_entrega':       q.local_entrega or '',
        'pessoa_contacto':     q.pessoa_contacto or '',
        'email_cliente':       q.email_cliente or '',
        'telefone_cliente':    q.telefone_cliente or '',
        'cambio':              str(q.cambio),
        'percentagem_iva':     str(q.percentagem_iva),
        'pagamento_condicoes': q.pagamento_condicoes or '',
        'entidade':            q.entidade or '',
        'referencia_cliente':  q.referencia_cliente or '',
        'observacoes':         q.observacoes or '',
        'termos_condicoes':    q.termos_condicoes or '',
        'subtotal':            str(q.subtotal),
        'total_iva':           str(q.total_iva),
        'total':               str(q.total),
        'itens':               itens,
    }
    return JsonResponse(data)


# ─── itens de um RFQ (para pré-popular items ao seleccionar RFQ) ───────────────

@login_required
@require_GET
def rfq_itens_json_view(request, rfq_id):
    rfq = get_object_or_404(RFQ.objects.select_related('cliente'), id=rfq_id)

    itens = list(
        rfq.itens.select_related('unidade').values(
            'linha', 'descricao', 'quantidade',
            'unidade_id', 'comentarios', 'especificacoes',
        )
    )
    return JsonResponse({
        'cliente_id':       rfq.cliente_id,
        'local_entrega':    rfq.local_entrega or '',
        'prazo_entrega':    '',
        'pessoa_contacto':  rfq.pessoa_contacto or '',
        'email_cliente':    rfq.email_cliente or '',
        'telefone_cliente': rfq.telefone_cliente or '',
        'itens':            itens,
    })


# ─── preview HTML ─────────────────────────────────────────────────────────────

@login_required
@require_GET
def quotacao_preview_html_view(request, quotacao_id):
    q = get_object_or_404(
        Quotacao.objects.select_related('cliente', 'moeda', 'rfq', 'criado_por')
                        .prefetch_related('itens__unidade'),
        id=quotacao_id,
    )
    organizacao = _get_organizacao()
    html = render_to_string(
        'quotacoes/includes/quotacao_document_inner.html',
        {'quotacao': q, 'organizacao': organizacao, 'preview_mode': True},
        request=request,
    )
    return HttpResponse(html)


# ─── download PDF ─────────────────────────────────────────────────────────────

@login_required
@require_GET
def quotacao_download_pdf_view(request, quotacao_id):
    q = get_object_or_404(
        Quotacao.objects.select_related('cliente', 'moeda', 'rfq', 'criado_por')
                        .prefetch_related('itens__unidade'),
        id=quotacao_id,
    )
    organizacao = _get_organizacao()

    html_string = render_to_string(
        'quotacoes/quotacao_pdf.html',
        {'quotacao': q, 'organizacao': organizacao, 'preview_mode': False},
        request=request,
    )
    pdf_file = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/'),
    ).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{q.numero}.pdf"'
    return response


# ─── create ───────────────────────────────────────────────────────────────────

@login_required
@require_POST
@transaction.atomic
def create_quotacao_view(request):
    try:
        q = _save_quotacao(request, Quotacao())
        messages.success(request, f'Quotação "{q.numero}" criada com sucesso.')
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Erro ao criar quotação: {e}')
    return redirect('procurement:quotacoes')


# ─── update ───────────────────────────────────────────────────────────────────

@login_required
@require_POST
@transaction.atomic
def update_quotacao_view(request, quotacao_id):
    q = get_object_or_404(Quotacao, id=quotacao_id)
    try:
        q = _save_quotacao(request, q)
        messages.success(request, f'Quotação "{q.numero}" actualizada com sucesso.')
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Erro ao actualizar quotação: {e}')
    return redirect('procurement:quotacoes')


# ─── mudar estado ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def change_estado_quotacao_view(request, quotacao_id):
    q          = get_object_or_404(Quotacao, id=quotacao_id)
    novo_estado = request.POST.get('estado', '').strip()
    estados_validos = [c[0] for c in Quotacao.ESTADO_CHOICES]

    if novo_estado not in estados_validos:
        messages.error(request, 'Estado inválido.')
        return redirect('procurement:quotacoes')

    q.estado = novo_estado
    q.save(update_fields=['estado', 'actualizado_em'])
    messages.success(request, f'Estado da quotação "{q.numero}" alterado para "{q.get_estado_display()}".')
    return redirect('procurement:quotacoes')


# ─── save helper ──────────────────────────────────────────────────────────────

def _save_quotacao(request, quotacao):
    POST = request.POST

    cliente_id = POST.get('cliente_id', '').strip()
    if not cliente_id:
        raise ValueError('Seleccione o cliente.')

    # ── itens ──────────────────────────────────────────────────────────────────
    descricoes      = POST.getlist('item_descricao[]')
    quantidades     = POST.getlist('item_quantidade[]')
    unidades        = POST.getlist('item_unidade_id[]')
    precos          = POST.getlist('item_preco_unitario[]')
    ivas_item       = POST.getlist('item_percentagem_iva[]')
    comentarios_l   = POST.getlist('item_comentarios[]')
    especificacoes_l = POST.getlist('item_especificacoes[]')

    n = max(len(descricoes), len(quantidades), len(precos))
    pct_iva_geral = _parse_decimal(POST.get('percentagem_iva', '16'), '16')

    itens_validos = []
    for i in range(n):
        desc = (descricoes[i] if i < len(descricoes) else '').strip()
        if not desc:
            continue
        qtd  = _parse_decimal(quantidades[i] if i < len(quantidades) else '1', '1')
        preco = _parse_decimal(precos[i] if i < len(precos) else '0', '0')
        pct   = _parse_decimal(ivas_item[i] if i < len(ivas_item) else str(pct_iva_geral), str(pct_iva_geral))
        uid   = unidades[i] if i < len(unidades) else ''
        com   = (comentarios_l[i] if i < len(comentarios_l) else '').strip()
        esp   = (especificacoes_l[i] if i < len(especificacoes_l) else '').strip()

        if qtd <= 0:
            raise ValueError(f'A quantidade do item "{desc}" deve ser maior que zero.')

        itens_validos.append({
            'linha':           len(itens_validos) + 1,
            'descricao':       desc,
            'quantidade':      qtd,
            'unidade_id':      int(uid) if uid else None,
            'preco_unitario':  preco,
            'percentagem_iva': pct,
            'total_liquido':   qtd * preco,
            'comentarios':     com or None,
            'especificacoes':  esp or None,
        })

    if not itens_validos:
        raise ValueError('Adicione pelo menos um item na quotação.')

    subtotal, total_iva, total = _calcular_totais(itens_validos, pct_iva_geral)

    now    = timezone.now()
    is_new = not bool(quotacao.pk)

    if is_new:
        quotacao.numero     = _generate_quotacao_number()
        quotacao.criado_por = request.user
        quotacao.criado_em  = now

    rfq_id = POST.get('rfq_id', '').strip()

    quotacao.rfq_id              = int(rfq_id) if rfq_id else None
    quotacao.cliente_id          = int(cliente_id)
    quotacao.estado              = POST.get('estado', 'rascunho') if not is_new else 'rascunho'
    quotacao.data_quotacao       = POST.get('data_quotacao') or date.today()
    quotacao.validade            = POST.get('validade') or None
    quotacao.prazo_entrega       = POST.get('prazo_entrega', '').strip() or None
    quotacao.local_entrega       = POST.get('local_entrega', '').strip() or None
    quotacao.pessoa_contacto     = POST.get('pessoa_contacto', '').strip() or None
    quotacao.email_cliente       = POST.get('email_cliente', '').strip() or None
    quotacao.telefone_cliente    = POST.get('telefone_cliente', '').strip() or None
    quotacao.moeda_id            = int(POST.get('moeda_id')) if POST.get('moeda_id') else None
    quotacao.cambio              = _parse_decimal(POST.get('cambio', '1'), '1')
    quotacao.percentagem_iva     = pct_iva_geral
    quotacao.pagamento_condicoes = POST.get('pagamento_condicoes', '').strip() or None
    quotacao.entidade            = POST.get('entidade', '').strip() or None
    quotacao.referencia_cliente  = POST.get('referencia_cliente', '').strip() or None
    quotacao.observacoes         = POST.get('observacoes', '').strip() or None
    quotacao.termos_condicoes    = POST.get('termos_condicoes', '').strip() or None
    quotacao.subtotal            = subtotal
    quotacao.total_iva           = total_iva
    quotacao.total               = total
    quotacao.actualizado_em      = now

    quotacao.save()

    # Substituir itens
    QuotacaoItem.objects.filter(quotacao_id=quotacao.id).delete()
    for item in itens_validos:
        QuotacaoItem.objects.create(quotacao_id=quotacao.id, **item)
        _upsert_descricao_sugerida(item['descricao'])

    return quotacao