from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from procurement.models import DadoBancario


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def metodos_pagamento_view(request):
    metodos = DadoBancario.objects.all().order_by('ordem', 'banco')

    context = {
        'segment': 'metodos_pagamento',
        'metodos': metodos,
        'total': metodos.count(),
        'total_activos': metodos.filter(activo=True).count(),
        'total_inactivos': metodos.filter(activo=False).count(),
        'total_predefinidos': metodos.filter(predefinido=True).count(),
    }
    return render(request, 'configuracoes/metodos_pagamento.html', context)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def metodo_pagamento_detail_json_view(request, metodo_id):
    metodo = get_object_or_404(DadoBancario, id=metodo_id)

    data = {
        'id': metodo.id,
        'banco': metodo.banco,
        'moeda': metodo.moeda,
        'conta': metodo.conta or '',
        'nib': metodo.nib or '',
        'swift': metodo.swift or '',
        'iban': metodo.iban or '',
        'titular': metodo.titular or '',
        'predefinido': metodo.predefinido,
        'activo': metodo.activo,
        'ordem': metodo.ordem,
    }
    return JsonResponse(data)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def create_metodo_pagamento_view(request):
    banco = (request.POST.get('banco') or '').strip()
    moeda = (request.POST.get('moeda') or 'MZN').strip().upper()

    if not banco:
        messages.error(request, 'O campo Banco é obrigatório.')
        return redirect('procurement:metodos_pagamento')

    if DadoBancario.objects.filter(banco=banco, moeda=moeda).exists():
        messages.error(request, f'Já existe um método de pagamento para o banco "{banco}" com a moeda "{moeda}".')
        return redirect('procurement:metodos_pagamento')

    metodo = _save_metodo_pagamento(request, DadoBancario())
    messages.success(request, f'Método de pagamento "{metodo.banco}" criado com sucesso.')
    return redirect('procurement:metodos_pagamento')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def update_metodo_pagamento_view(request, metodo_id):
    metodo = get_object_or_404(DadoBancario, id=metodo_id)

    banco = (request.POST.get('banco') or '').strip()
    moeda = (request.POST.get('moeda') or 'MZN').strip().upper()

    if not banco:
        messages.error(request, 'O campo Banco é obrigatório.')
        return redirect('procurement:metodos_pagamento')

    if DadoBancario.objects.filter(banco=banco, moeda=moeda).exclude(id=metodo.id).exists():
        messages.error(request, f'Já existe outro método de pagamento para o banco "{banco}" com a moeda "{moeda}".')
        return redirect('procurement:metodos_pagamento')

    metodo = _save_metodo_pagamento(request, metodo)
    messages.success(request, f'Método de pagamento "{metodo.banco}" actualizado com sucesso.')
    return redirect('procurement:metodos_pagamento')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def toggle_metodo_pagamento_status_view(request, metodo_id):
    metodo = get_object_or_404(DadoBancario, id=metodo_id)
    metodo.activo = not metodo.activo
    metodo.save(update_fields=['activo'])

    estado = 'activado' if metodo.activo else 'desactivado'
    messages.success(request, f'Método de pagamento "{metodo.banco}" foi {estado} com sucesso.')
    return redirect('procurement:metodos_pagamento')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def definir_metodo_pagamento_predefinido_view(request, metodo_id):
    metodo = get_object_or_404(DadoBancario, id=metodo_id)

    DadoBancario.objects.filter(predefinido=True).update(predefinido=False)
    metodo.predefinido = True
    metodo.save(update_fields=['predefinido'])

    messages.success(request, f'"{metodo.banco}" foi definido como método de pagamento predefinido.')
    return redirect('procurement:metodos_pagamento')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def delete_metodo_pagamento_view(request, metodo_id):
    metodo = get_object_or_404(DadoBancario, id=metodo_id)
    nome = metodo.banco
    metodo.delete()

    messages.success(request, f'Método de pagamento "{nome}" removido com sucesso.')
    return redirect('procurement:metodos_pagamento')


# ──────────────────────────────────────────────────────────────────────────────
def _save_metodo_pagamento(request, metodo):
    banco = (request.POST.get('banco') or '').strip()
    moeda = (request.POST.get('moeda') or 'MZN').strip().upper()
    conta = (request.POST.get('conta') or '').strip() or None
    nib = (request.POST.get('nib') or '').strip() or None
    swift = (request.POST.get('swift') or '').strip() or None
    iban = (request.POST.get('iban') or '').strip() or None
    titular = (request.POST.get('titular') or '').strip() or None
    ordem = int(request.POST.get('ordem') or 0)
    predefinido = request.POST.get('predefinido', '0') == '1'
    activo = request.POST.get('activo', '1') == '1'

    metodo.banco = banco
    metodo.moeda = moeda
    metodo.conta = conta
    metodo.nib = nib
    metodo.swift = swift
    metodo.iban = iban
    metodo.titular = titular
    metodo.ordem = ordem
    metodo.predefinido = predefinido
    metodo.activo = activo
    metodo.save()

    if predefinido:
        DadoBancario.objects.exclude(id=metodo.id).filter(predefinido=True).update(predefinido=False)

    return metodo