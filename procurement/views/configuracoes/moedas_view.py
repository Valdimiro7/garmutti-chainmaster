from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from procurement.models import Moeda


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def moedas_view(request):
    moedas = Moeda.objects.all().order_by('-predefinida', 'codigo')

    context = {
        'segment': 'moedas',
        'moedas': moedas,
        'total': moedas.count(),
        'total_activas': moedas.filter(estado=True).count(),
        'total_inactivas': moedas.filter(estado=False).count(),
        'total_predefinidas': moedas.filter(predefinida=True).count(),
    }
    return render(request, 'configuracoes/moedas.html', context)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def moeda_detail_json_view(request, moeda_id):
    moeda = get_object_or_404(Moeda, id=moeda_id)

    data = {
        'id': moeda.id,
        'codigo': moeda.codigo,
        'nome': moeda.nome,
        'simbolo': moeda.simbolo,
        'pais': moeda.pais or '',
        'estado': moeda.estado,
        'predefinida': moeda.predefinida,
    }
    return JsonResponse(data)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def create_moeda_view(request):
    codigo = (request.POST.get('codigo') or '').strip().upper()

    if not codigo:
        messages.error(request, 'O campo Código é obrigatório.')
        return redirect('procurement:moedas')

    if Moeda.objects.filter(codigo=codigo).exists():
        messages.error(request, f'Já existe uma moeda com o código "{codigo}".')
        return redirect('procurement:moedas')

    moeda = _save_moeda(request, Moeda())
    messages.success(request, f'Moeda "{moeda.codigo}" criada com sucesso.')
    return redirect('procurement:moedas')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def update_moeda_view(request, moeda_id):
    moeda = get_object_or_404(Moeda, id=moeda_id)
    codigo = (request.POST.get('codigo') or '').strip().upper()

    if not codigo:
        messages.error(request, 'O campo Código é obrigatório.')
        return redirect('procurement:moedas')

    if Moeda.objects.filter(codigo=codigo).exclude(id=moeda.id).exists():
        messages.error(request, f'Já existe outra moeda com o código "{codigo}".')
        return redirect('procurement:moedas')

    moeda = _save_moeda(request, moeda)
    messages.success(request, f'Moeda "{moeda.codigo}" actualizada com sucesso.')
    return redirect('procurement:moedas')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def toggle_moeda_status_view(request, moeda_id):
    moeda = get_object_or_404(Moeda, id=moeda_id)
    moeda.estado = not moeda.estado
    moeda.save(update_fields=['estado'])

    estado_txt = 'activada' if moeda.estado else 'desactivada'
    messages.success(request, f'Moeda "{moeda.codigo}" foi {estado_txt} com sucesso.')
    return redirect('procurement:moedas')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def definir_moeda_predefinida_view(request, moeda_id):
    moeda = get_object_or_404(Moeda, id=moeda_id)

    Moeda.objects.filter(predefinida=True).update(predefinida=False)
    moeda.predefinida = True
    moeda.save(update_fields=['predefinida'])

    messages.success(request, f'A moeda "{moeda.codigo}" foi definida como predefinida.')
    return redirect('procurement:moedas')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def delete_moeda_view(request, moeda_id):
    moeda = get_object_or_404(Moeda, id=moeda_id)
    codigo = moeda.codigo
    moeda.delete()

    messages.success(request, f'Moeda "{codigo}" removida com sucesso.')
    return redirect('procurement:moedas')


# ──────────────────────────────────────────────────────────────────────────────
def _save_moeda(request, moeda):
    codigo = (request.POST.get('codigo') or '').strip().upper()
    nome = (request.POST.get('nome') or '').strip()
    simbolo = (request.POST.get('simbolo') or '').strip()
    pais = (request.POST.get('pais') or '').strip() or None
    estado = request.POST.get('estado', '1') == '1'
    predefinida = request.POST.get('predefinida', '0') == '1'

    moeda.codigo = codigo
    moeda.nome = nome
    moeda.simbolo = simbolo
    moeda.pais = pais
    moeda.estado = estado
    moeda.predefinida = predefinida
    moeda.save()

    if predefinida:
        Moeda.objects.exclude(id=moeda.id).filter(predefinida=True).update(predefinida=False)

    return moeda