from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from procurement.models import Fornecedor, Moeda


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def fornecedores_view(request):
    fornecedores = Fornecedor.objects.select_related('moeda').all().order_by('nome')
    moedas = Moeda.objects.filter(estado=True).order_by('-predefinida', 'codigo')

    context = {
        'segment': 'fornecedores',
        'fornecedores': fornecedores,
        'moedas': moedas,
        'total': fornecedores.count(),
        'total_activos': fornecedores.filter(estado=True).count(),
        'total_inactivos': fornecedores.filter(estado=False).count(),
    }
    return render(request, 'fornecedores/fornecedores.html', context)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def fornecedor_detail_json_view(request, fornecedor_id):
    fornecedor = get_object_or_404(
        Fornecedor.objects.select_related('moeda'),
        id=fornecedor_id
    )

    data = {
        'id': fornecedor.id,
        'nome': fornecedor.nome,
        'tipo': fornecedor.tipo,
        'nuit': fornecedor.nuit or '',
        'bi_nid': fornecedor.bi_nid or '',
        'alvara': fornecedor.alvara or '',
        'sector_actividade': fornecedor.sector_actividade or '',
        'email': fornecedor.email or '',
        'telefone': fornecedor.telefone or '',
        'telemovel': fornecedor.telemovel or '',
        'website': fornecedor.website or '',
        'pessoa_contacto': fornecedor.pessoa_contacto or '',
        'provincia': fornecedor.provincia or '',
        'cidade_distrito': fornecedor.cidade_distrito or '',
        'bairro': fornecedor.bairro or '',
        'endereco': fornecedor.endereco or '',
        'codigo_postal': fornecedor.codigo_postal or '',
        'pais': fornecedor.pais or 'Moçambique',
        'moeda_id': fornecedor.moeda_id,
        'limite_credito': str(fornecedor.limite_credito),
        'prazo_pagamento_dias': fornecedor.prazo_pagamento_dias,
        'desconto_geral': str(fornecedor.desconto_geral),
        'conta_bancaria': fornecedor.conta_bancaria or '',
        'banco': fornecedor.banco or '',
        'categoria': fornecedor.categoria,
        'estado': fornecedor.estado,
        'observacoes': fornecedor.observacoes or '',
    }
    return JsonResponse(data)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def create_fornecedor_view(request):
    nuit = (request.POST.get('nuit') or '').strip()

    if nuit and Fornecedor.objects.filter(nuit=nuit).exists():
        messages.error(request, f'Já existe um fornecedor com o NUIT "{nuit}".')
        return redirect('procurement:fornecedores')

    fornecedor = _save_fornecedor(request, Fornecedor())
    messages.success(request, f'Fornecedor "{fornecedor.nome}" criado com sucesso.')
    return redirect('procurement:fornecedores')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def update_fornecedor_view(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
    nuit = (request.POST.get('nuit') or '').strip()

    if nuit and Fornecedor.objects.filter(nuit=nuit).exclude(id=fornecedor.id).exists():
        messages.error(request, f'Já existe outro fornecedor com o NUIT "{nuit}".')
        return redirect('procurement:fornecedores')

    fornecedor = _save_fornecedor(request, fornecedor)
    messages.success(request, f'Fornecedor "{fornecedor.nome}" actualizado com sucesso.')
    return redirect('procurement:fornecedores')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def toggle_fornecedor_status_view(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
    fornecedor.estado = not fornecedor.estado
    fornecedor.save(update_fields=['estado'])
    estado = 'activado' if fornecedor.estado else 'desactivado'
    messages.success(request, f'Fornecedor "{fornecedor.nome}" foi {estado} com sucesso.')
    return redirect('procurement:fornecedores')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def delete_fornecedor_view(request, fornecedor_id):
    fornecedor = get_object_or_404(Fornecedor, id=fornecedor_id)
    nome = fornecedor.nome
    fornecedor.delete()
    messages.success(request, f'Fornecedor "{nome}" removido com sucesso.')
    return redirect('procurement:fornecedores')


# ──────────────────────────────────────────────────────────────────────────────
def _save_fornecedor(request, fornecedor):
    moeda_id = request.POST.get('moeda_id') or None

    fornecedor.nome = (request.POST.get('nome') or '').strip()
    fornecedor.tipo = request.POST.get('tipo', 'Colectivo')
    fornecedor.nuit = (request.POST.get('nuit') or '').strip() or None
    fornecedor.bi_nid = (request.POST.get('bi_nid') or '').strip() or None
    fornecedor.alvara = (request.POST.get('alvara') or '').strip() or None
    fornecedor.sector_actividade = (request.POST.get('sector_actividade') or '').strip() or None
    fornecedor.email = (request.POST.get('email') or '').strip() or None
    fornecedor.telefone = (request.POST.get('telefone') or '').strip() or None
    fornecedor.telemovel = (request.POST.get('telemovel') or '').strip() or None
    fornecedor.website = (request.POST.get('website') or '').strip() or None
    fornecedor.pessoa_contacto = (request.POST.get('pessoa_contacto') or '').strip() or None
    fornecedor.provincia = (request.POST.get('provincia') or '').strip() or None
    fornecedor.cidade_distrito = (request.POST.get('cidade_distrito') or '').strip() or None
    fornecedor.bairro = (request.POST.get('bairro') or '').strip() or None
    fornecedor.endereco = (request.POST.get('endereco') or '').strip() or None
    fornecedor.codigo_postal = (request.POST.get('codigo_postal') or '').strip() or None
    fornecedor.pais = (request.POST.get('pais') or 'Moçambique').strip()
    fornecedor.moeda_id = int(moeda_id) if moeda_id else None
    fornecedor.limite_credito = request.POST.get('limite_credito') or 0
    fornecedor.prazo_pagamento_dias = int(request.POST.get('prazo_pagamento_dias') or 30)
    fornecedor.desconto_geral = request.POST.get('desconto_geral') or 0
    fornecedor.conta_bancaria = (request.POST.get('conta_bancaria') or '').strip() or None
    fornecedor.banco = (request.POST.get('banco') or '').strip() or None
    fornecedor.categoria = request.POST.get('categoria', 'B')
    fornecedor.estado = request.POST.get('estado', '1') == '1'
    fornecedor.observacoes = (request.POST.get('observacoes') or '').strip() or None

    if not fornecedor.pk:
        fornecedor.criado_por = request.user

    fornecedor.save()
    return fornecedor