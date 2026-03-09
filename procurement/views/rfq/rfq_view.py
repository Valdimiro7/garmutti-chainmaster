import os
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from procurement.models import Cliente, RFQ, RFQAnexo, RFQEstado, RFQItem, Unidade


def _get_upload_path(filename):
    base_dir = getattr(settings, 'MEDIA_ROOT', None)
    if not base_dir:
        raise ValueError('MEDIA_ROOT não está configurado no settings.py')

    today = timezone.now()
    folder = os.path.join(base_dir, 'rfq_anexos', str(today.year), f'{today.month:02d}')
    os.makedirs(folder, exist_ok=True)
    return folder


def _save_uploaded_file(uploaded_file):
    folder = _get_upload_path(uploaded_file.name)
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S%f')
    safe_name = f'{timestamp}_{uploaded_file.name}'
    full_path = os.path.join(folder, safe_name)

    with open(full_path, 'wb+') as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)

    relative_path = os.path.relpath(full_path, settings.MEDIA_ROOT).replace('\\', '/')
    return relative_path


def _generate_rfq_number():
    current_year = timezone.now().year
    prefix = f'RFQ-{current_year}-'

    ultimo = (
        RFQ.objects
        .filter(numero__startswith=prefix)
        .order_by('-id')
        .first()
    )

    sequencial = 1
    if ultimo and ultimo.numero:
        try:
            ultimo_seq = int(ultimo.numero.split('-')[-1])
            sequencial = ultimo_seq + 1
        except (ValueError, IndexError):
            sequencial = 1

    return f'{prefix}{sequencial:05d}'


def _parse_decimal(value, default='0'):
    try:
        return Decimal(str(value or default))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _get_estado_novo():
    estado_novo = RFQEstado.objects.filter(codigo='novo').first()
    if not estado_novo:
        raise ValueError('Estado "Novo" não encontrado na tabela rfq_estados.')
    return estado_novo


@login_required
@require_GET
def rfqs_view(request):
    rfqs = (
        RFQ.objects
        .select_related('cliente', 'estado', 'criado_por')
        .prefetch_related('itens', 'anexos')
        .all()
        .order_by('-id')
    )

    clientes = Cliente.objects.filter(estado=True).order_by('nome')
    unidades = Unidade.objects.filter(activo=True).order_by('ordem', 'nome')

    total = rfqs.count()
    total_novos = rfqs.filter(estado__codigo='novo').count()
    total_fechados = rfqs.filter(estado__codigo='fechado').count()
    total_cancelados = rfqs.filter(estado__codigo='cancelado').count()

    context = {
        'segment': 'rfqs',
        'rfqs': rfqs,
        'clientes': clientes,
        'unidades': unidades,
        'total': total,
        'total_novos': total_novos,
        'total_fechados': total_fechados,
        'total_cancelados': total_cancelados,
        'default_numero': _generate_rfq_number(),
        'today': date.today().isoformat(),
    }
    return render(request, 'rfq/rfqs.html', context)


@login_required
@require_GET
def rfq_detail_json_view(request, rfq_id):
    rfq = get_object_or_404(
        RFQ.objects.select_related('cliente', 'estado'),
        id=rfq_id
    )

    itens = list(
        rfq.itens.select_related('unidade').all().values(
            'id',
            'linha',
            'descricao',
            'quantidade',
            'unidade_id',
            'comentarios',
            'especificacoes',
        )
    )

    anexos = list(
        rfq.anexos.all().values(
            'id',
            'ficheiro',
            'nome_original',
            'tamanho',
            'content_type',
        )
    )

    data = {
        'id': rfq.id,
        'numero': rfq.numero,
        'cliente_id': rfq.cliente_id,
        'data_rfq': rfq.data_rfq.isoformat() if rfq.data_rfq else '',
        'prazo_entrega': rfq.prazo_entrega.isoformat() if rfq.prazo_entrega else '',
        'local_entrega': rfq.local_entrega or '',
        'email_cliente': rfq.email_cliente or '',
        'telefone_cliente': rfq.telefone_cliente or '',
        'pessoa_contacto': rfq.pessoa_contacto or '',
        'observacoes': rfq.observacoes or '',
        'itens': itens,
        'anexos': anexos,
    }
    return JsonResponse(data)


@login_required
@require_POST
@transaction.atomic
def create_rfq_view(request):
    try:
        rfq = _save_rfq(request, RFQ())
        messages.success(request, f'RFQ "{rfq.numero}" criado com sucesso.')
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Ocorreu um erro ao criar o RFQ: {str(e)}')

    return redirect('procurement:rfqs')


@login_required
@require_POST
@transaction.atomic
def update_rfq_view(request, rfq_id):
    rfq = get_object_or_404(RFQ, id=rfq_id)

    try:
        rfq = _save_rfq(request, rfq)
        messages.success(request, f'RFQ "{rfq.numero}" actualizado com sucesso.')
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Ocorreu um erro ao actualizar o RFQ: {str(e)}')

    return redirect('procurement:rfqs')


@login_required
@require_POST
def delete_rfq_view(request, rfq_id):
    rfq = get_object_or_404(RFQ, id=rfq_id)
    numero = rfq.numero
    rfq.delete()
    messages.success(request, f'RFQ "{numero}" removido com sucesso.')
    return redirect('procurement:rfqs')


def _save_rfq(request, rfq):
    cliente_id = request.POST.get('cliente_id')

    if not cliente_id:
        raise ValueError('Seleccione o cliente.')

    estado_novo = _get_estado_novo()

    descricoes = request.POST.getlist('item_descricao[]')
    quantidades = request.POST.getlist('item_quantidade[]')
    unidades = request.POST.getlist('item_unidade_id[]')
    comentarios = request.POST.getlist('item_comentarios[]')
    especificacoes = request.POST.getlist('item_especificacoes[]')

    itens_validos = []
    total_linhas = max(
        len(descricoes),
        len(quantidades),
        len(unidades),
        len(comentarios),
        len(especificacoes),
    )

    for i in range(total_linhas):
        descricao = (descricoes[i] if i < len(descricoes) else '').strip()
        quantidade = quantidades[i] if i < len(quantidades) else '1'
        unidade_id = unidades[i] if i < len(unidades) else ''
        comentario = (comentarios[i] if i < len(comentarios) else '').strip()
        especificacao = (especificacoes[i] if i < len(especificacoes) else '').strip()

        if not descricao:
            continue

        quantidade_decimal = _parse_decimal(quantidade, '1')
        if quantidade_decimal <= 0:
            raise ValueError(f'A quantidade do item "{descricao}" deve ser maior que zero.')

        itens_validos.append({
            'linha': len(itens_validos) + 1,
            'descricao': descricao,
            'quantidade': quantidade_decimal,
            'unidade_id': int(unidade_id) if unidade_id else None,
            'comentarios': comentario or None,
            'especificacoes': especificacao or None,
        })

    if not itens_validos:
        raise ValueError('Adicione pelo menos um item no RFQ.')

    now = timezone.now()
    is_new = not bool(rfq.pk)

    if is_new:
        rfq.numero = _generate_rfq_number()
        rfq.criado_por = request.user
        rfq.criado_em = now

    rfq.origem = 'manual'
    rfq.cliente_id = int(cliente_id)

    if is_new:
        rfq.estado_id = estado_novo.id
    elif not rfq.estado_id:
        rfq.estado_id = estado_novo.id

    rfq.data_rfq = request.POST.get('data_rfq') or date.today()
    rfq.prazo_entrega = request.POST.get('prazo_entrega') or None
    rfq.local_entrega = (request.POST.get('local_entrega') or '').strip() or None
    rfq.email_cliente = (request.POST.get('email_cliente') or '').strip() or None
    rfq.telefone_cliente = (request.POST.get('telefone_cliente') or '').strip() or None
    rfq.pessoa_contacto = (request.POST.get('pessoa_contacto') or '').strip() or None
    rfq.observacoes = (request.POST.get('observacoes') or '').strip() or None
    rfq.actualizado_em = now

    rfq.save()

    RFQItem.objects.filter(rfq_id=rfq.id).delete()

    for item in itens_validos:
        RFQItem.objects.create(
            rfq_id=rfq.id,
            linha=item['linha'],
            descricao=item['descricao'],
            quantidade=item['quantidade'],
            unidade_id=item['unidade_id'],
            comentarios=item['comentarios'],
            especificacoes=item['especificacoes'],
        )

    for ficheiro in request.FILES.getlist('anexos'):
        relative_path = _save_uploaded_file(ficheiro)

        RFQAnexo.objects.create(
            rfq_id=rfq.id,
            ficheiro=relative_path,
            nome_original=ficheiro.name,
            tamanho=ficheiro.size,
            content_type=getattr(ficheiro, 'content_type', None),
            carregado_por=request.user,
            carregado_em=now,
        )

    return rfq