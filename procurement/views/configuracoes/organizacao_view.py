from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from procurement.models import Organizacao


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def organizacao_view(request):
    organizacoes = Organizacao.objects.all().order_by('nome')

    context = {
        'segment': 'organizacao',
        'organizacoes': organizacoes,
        'total': organizacoes.count(),
        'total_activas': organizacoes.filter(activo=True).count(),
        'total_inactivas': organizacoes.filter(activo=False).count(),
    }
    return render(request, 'configuracoes/organizacao.html', context)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def organizacao_detail_json_view(request, organizacao_id):
    organizacao = get_object_or_404(Organizacao, id=organizacao_id)

    data = {
        'id': organizacao.id,
        'nome': organizacao.nome,
        'slogan': organizacao.slogan or '',
        'nuit': organizacao.nuit or '',
        'email': organizacao.email or '',
        'telefone_1': organizacao.telefone_1 or '',
        'telefone_2': organizacao.telefone_2 or '',
        'website': organizacao.website or '',
        'endereco': organizacao.endereco or '',
        'cidade': organizacao.cidade or '',
        'pais': organizacao.pais or 'Moçambique',
        'logo': organizacao.logo or '',
        'observacoes': organizacao.observacoes or '',
        'activo': organizacao.activo,
    }
    return JsonResponse(data)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def create_organizacao_view(request):
    nome = (request.POST.get('nome') or '').strip()

    if not nome:
        messages.error(request, 'O campo Nome da organização é obrigatório.')
        return redirect('procurement:organizacao')

    if Organizacao.objects.filter(nome=nome).exists():
        messages.error(request, f'Já existe uma organização com o nome "{nome}".')
        return redirect('procurement:organizacao')

    organizacao = _save_organizacao(request, Organizacao())
    messages.success(request, f'Organização "{organizacao.nome}" criada com sucesso.')
    return redirect('procurement:organizacao')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def update_organizacao_view(request, organizacao_id):
    organizacao = get_object_or_404(Organizacao, id=organizacao_id)
    nome = (request.POST.get('nome') or '').strip()

    if not nome:
        messages.error(request, 'O campo Nome da organização é obrigatório.')
        return redirect('procurement:organizacao')

    if Organizacao.objects.filter(nome=nome).exclude(id=organizacao.id).exists():
        messages.error(request, f'Já existe outra organização com o nome "{nome}".')
        return redirect('procurement:organizacao')

    organizacao = _save_organizacao(request, organizacao)
    messages.success(request, f'Organização "{organizacao.nome}" actualizada com sucesso.')
    return redirect('procurement:organizacao')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def toggle_organizacao_status_view(request, organizacao_id):
    organizacao = get_object_or_404(Organizacao, id=organizacao_id)
    organizacao.activo = not organizacao.activo
    organizacao.save(update_fields=['activo'])

    estado_txt = 'activada' if organizacao.activo else 'desactivada'
    messages.success(request, f'Organização "{organizacao.nome}" foi {estado_txt} com sucesso.')
    return redirect('procurement:organizacao')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def delete_organizacao_view(request, organizacao_id):
    organizacao = get_object_or_404(Organizacao, id=organizacao_id)
    nome = organizacao.nome
    organizacao.delete()

    messages.success(request, f'Organização "{nome}" removida com sucesso.')
    return redirect('procurement:organizacao')


# ──────────────────────────────────────────────────────────────────────────────
def _save_organizacao(request, organizacao):
    organizacao.nome = (request.POST.get('nome') or '').strip()
    organizacao.slogan = (request.POST.get('slogan') or '').strip() or None
    organizacao.nuit = (request.POST.get('nuit') or '').strip() or None
    organizacao.email = (request.POST.get('email') or '').strip() or None
    organizacao.telefone_1 = (request.POST.get('telefone_1') or '').strip() or None
    organizacao.telefone_2 = (request.POST.get('telefone_2') or '').strip() or None
    organizacao.website = (request.POST.get('website') or '').strip() or None
    organizacao.endereco = (request.POST.get('endereco') or '').strip() or None
    organizacao.cidade = (request.POST.get('cidade') or '').strip() or None
    organizacao.pais = (request.POST.get('pais') or 'Moçambique').strip()
    organizacao.logo = (request.POST.get('logo') or '').strip() or None
    organizacao.observacoes = (request.POST.get('observacoes') or '').strip() or None
    organizacao.activo = request.POST.get('activo', '1') == '1'
    organizacao.save()

    return organizacao