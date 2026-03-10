from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from procurement.models import CondicaoPagamento


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def condicoes_pagamento_view(request):
    condicoes = CondicaoPagamento.objects.all().order_by('ordem', 'nome')

    context = {
        'segment': 'condicoes_pagamento',
        'condicoes': condicoes,
        'total': condicoes.count(),
        'total_activas': condicoes.filter(activo=True).count(),
        'total_inactivas': condicoes.filter(activo=False).count(),
    }
    return render(request, 'configuracoes/condicoes_pagamento.html', context)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def condicao_pagamento_detail_json_view(request, condicao_id):
    condicao = get_object_or_404(CondicaoPagamento, id=condicao_id)

    data = {
        'id': condicao.id,
        'nome': condicao.nome,
        'descricao': condicao.descricao or '',
        'activo': condicao.activo,
        'ordem': condicao.ordem,
    }
    return JsonResponse(data)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def create_condicao_pagamento_view(request):
    nome = (request.POST.get('nome') or '').strip()

    if not nome:
        messages.error(request, 'O campo Nome é obrigatório.')
        return redirect('procurement:condicoes_pagamento')

    if CondicaoPagamento.objects.filter(nome__iexact=nome).exists():
        messages.error(request, f'Já existe uma condição de pagamento com o nome "{nome}".')
        return redirect('procurement:condicoes_pagamento')

    condicao = _save_condicao_pagamento(request, CondicaoPagamento())
    messages.success(request, f'Condição de pagamento "{condicao.nome}" criada com sucesso.')
    return redirect('procurement:condicoes_pagamento')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def update_condicao_pagamento_view(request, condicao_id):
    condicao = get_object_or_404(CondicaoPagamento, id=condicao_id)
    nome = (request.POST.get('nome') or '').strip()

    if not nome:
        messages.error(request, 'O campo Nome é obrigatório.')
        return redirect('procurement:condicoes_pagamento')

    if CondicaoPagamento.objects.filter(nome__iexact=nome).exclude(id=condicao.id).exists():
        messages.error(request, f'Já existe outra condição de pagamento com o nome "{nome}".')
        return redirect('procurement:condicoes_pagamento')

    condicao = _save_condicao_pagamento(request, condicao)
    messages.success(request, f'Condição de pagamento "{condicao.nome}" actualizada com sucesso.')
    return redirect('procurement:condicoes_pagamento')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def toggle_condicao_pagamento_status_view(request, condicao_id):
    condicao = get_object_or_404(CondicaoPagamento, id=condicao_id)
    condicao.activo = not condicao.activo
    condicao.save(update_fields=['activo'])

    estado_txt = 'activada' if condicao.activo else 'desactivada'
    messages.success(request, f'Condição de pagamento "{condicao.nome}" foi {estado_txt} com sucesso.')
    return redirect('procurement:condicoes_pagamento')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def delete_condicao_pagamento_view(request, condicao_id):
    condicao = get_object_or_404(CondicaoPagamento, id=condicao_id)
    nome = condicao.nome
    condicao.delete()

    messages.success(request, f'Condição de pagamento "{nome}" removida com sucesso.')
    return redirect('procurement:condicoes_pagamento')


# ──────────────────────────────────────────────────────────────────────────────
def _save_condicao_pagamento(request, condicao):
    condicao.nome = (request.POST.get('nome') or '').strip()
    condicao.descricao = (request.POST.get('descricao') or '').strip() or None
    condicao.activo = request.POST.get('activo', '1') == '1'
    condicao.ordem = int(request.POST.get('ordem') or 0)
    condicao.save()
    return condicao