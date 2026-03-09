from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from django.db import transaction
from procurement.models import Cliente, Moeda




# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def clientes_view(request):
    clientes = Cliente.objects.select_related('moeda').all().order_by('nome')
    moedas   = Moeda.objects.filter(estado=True).order_by('-predefinida', 'codigo')

    context = {
        'segment':         'clientes',
        'clientes':        clientes,
        'moedas':          moedas,
        'total':           clientes.count(),
        'total_activos':   clientes.filter(estado=True).count(),
        'total_inactivos': clientes.filter(estado=False).count(),
    }
    return render(request, 'clientes/clientes.html', context)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def cliente_detail_json_view(request, cliente_id):
    cliente = get_object_or_404(
        Cliente.objects.select_related('moeda'), id=cliente_id
    )
    data = {
        'id':                   cliente.id,
        'nome':                 cliente.nome,
        'tipo':                 cliente.tipo,
        'nuit':                 cliente.nuit or '',
        'bi_nid':               cliente.bi_nid or '',
        'alvara':               cliente.alvara or '',
        'sector_actividade':    cliente.sector_actividade or '',
        'email':                cliente.email or '',
        'telefone':             cliente.telefone or '',
        'telemovel':            cliente.telemovel or '',
        'website':              cliente.website or '',
        'pessoa_contacto':      cliente.pessoa_contacto or '',
        'provincia':            cliente.provincia or '',
        'cidade_distrito':      cliente.cidade_distrito or '',
        'bairro':               cliente.bairro or '',
        'endereco':             cliente.endereco or '',
        'codigo_postal':        cliente.codigo_postal or '',
        'pais':                 cliente.pais or 'Moçambique',
        'moeda_id':             cliente.moeda_id,
        'limite_credito':       str(cliente.limite_credito),
        'prazo_pagamento_dias': cliente.prazo_pagamento_dias,
        'desconto_geral':       str(cliente.desconto_geral),
        'conta_bancaria':       cliente.conta_bancaria or '',
        'banco':                cliente.banco or '',
        'categoria':            cliente.categoria,
        'estado':               cliente.estado,
        'observacoes':          cliente.observacoes or '',
    }
    return JsonResponse(data)


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def create_cliente_view(request):
    nuit = (request.POST.get('nuit') or '').strip()

    if nuit and Cliente.objects.filter(nuit=nuit).exists():
        messages.error(request, f'Já existe um cliente com o NUIT "{nuit}".')
        return redirect('procurement:clientes')

    cliente = _save_cliente(request, Cliente())
    messages.success(request, f'Cliente "{cliente.nome}" criado com sucesso.')
    return redirect('procurement:clientes')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
@transaction.atomic
def update_cliente_view(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    nuit    = (request.POST.get('nuit') or '').strip()

    if nuit and Cliente.objects.filter(nuit=nuit).exclude(id=cliente.id).exists():
        messages.error(request, f'Já existe outro cliente com o NUIT "{nuit}".')
        return redirect('procurement:clientes')

    cliente = _save_cliente(request, cliente)
    messages.success(request, f'Cliente "{cliente.nome}" actualizado com sucesso.')
    return redirect('procurement:clientes')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def toggle_cliente_status_view(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    cliente.estado = not cliente.estado
    cliente.save(update_fields=['estado'])
    estado = 'activado' if cliente.estado else 'desactivado'
    messages.success(request, f'Cliente "{cliente.nome}" foi {estado} com sucesso.')
    return redirect('procurement:clientes')


# ──────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def delete_cliente_view(request, cliente_id):
    cliente = get_object_or_404(Cliente, id=cliente_id)
    nome = cliente.nome
    cliente.delete()
    messages.success(request, f'Cliente "{nome}" removido com sucesso.')
    return redirect('procurement:clientes')


# ──────────────────────────────────────────────────────────────────────────────
# Helper interno
def _save_cliente(request, cliente):
    moeda_id = request.POST.get('moeda_id') or None

    cliente.nome               = (request.POST.get('nome') or '').strip()
    cliente.tipo               = request.POST.get('tipo', 'Colectivo')
    cliente.nuit               = (request.POST.get('nuit') or '').strip() or None
    cliente.bi_nid             = (request.POST.get('bi_nid') or '').strip() or None
    cliente.alvara             = (request.POST.get('alvara') or '').strip() or None
    cliente.sector_actividade  = (request.POST.get('sector_actividade') or '').strip() or None
    cliente.email              = (request.POST.get('email') or '').strip() or None
    cliente.telefone           = (request.POST.get('telefone') or '').strip() or None
    cliente.telemovel          = (request.POST.get('telemovel') or '').strip() or None
    cliente.website            = (request.POST.get('website') or '').strip() or None
    cliente.pessoa_contacto    = (request.POST.get('pessoa_contacto') or '').strip() or None
    cliente.provincia          = (request.POST.get('provincia') or '').strip() or None
    cliente.cidade_distrito    = (request.POST.get('cidade_distrito') or '').strip() or None
    cliente.bairro             = (request.POST.get('bairro') or '').strip() or None
    cliente.endereco           = (request.POST.get('endereco') or '').strip() or None
    cliente.codigo_postal      = (request.POST.get('codigo_postal') or '').strip() or None
    cliente.pais               = (request.POST.get('pais') or 'Moçambique').strip()
    cliente.moeda_id           = int(moeda_id) if moeda_id else None
    cliente.limite_credito     = request.POST.get('limite_credito') or 0
    cliente.prazo_pagamento_dias = int(request.POST.get('prazo_pagamento_dias') or 30)
    cliente.desconto_geral     = request.POST.get('desconto_geral') or 0
    cliente.conta_bancaria     = (request.POST.get('conta_bancaria') or '').strip() or None
    cliente.banco              = (request.POST.get('banco') or '').strip() or None
    cliente.categoria          = request.POST.get('categoria', 'B')
    cliente.estado             = request.POST.get('estado', '1') == '1'
    cliente.observacoes        = (request.POST.get('observacoes') or '').strip() or None

    if not cliente.pk:
        cliente.criado_por = request.user

    cliente.save()
    return cliente