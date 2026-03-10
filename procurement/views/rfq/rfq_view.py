import json
import os
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth.models import Group

from weasyprint import HTML

from procurement.models import (
    Cliente,
    Organizacao,
    RFQ,
    RFQAnexo,
    RFQEstado,
    RFQItem,
    Unidade,
)


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


def _get_organizacao():
    return Organizacao.objects.filter(activo=True).order_by('id').first()


def _get_allowed_origins():
    return getattr(settings, 'WEBSITE_RFQ_ALLOWED_ORIGINS', [])


def _add_cors_headers(response, request):
    origin = request.headers.get('Origin')
    allowed_origins = _get_allowed_origins()

    if origin and origin in allowed_origins:
        response['Access-Control-Allow-Origin'] = origin
        response['Vary'] = 'Origin'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, X-Requested-With'
        response['Access-Control-Allow-Credentials'] = 'false'

    return response


def _json_response(data, request, status=200):
    response = JsonResponse(data, status=status)
    return _add_cors_headers(response, request)


def _get_default_website_cliente():
    """
    Define no settings.py:
    WEBSITE_RFQ_CLIENTE_ID = 1
    """
    cliente_id = getattr(settings, 'WEBSITE_RFQ_CLIENTE_ID', None)
    if not cliente_id:
        raise ValueError(
            'WEBSITE_RFQ_CLIENTE_ID não está configurado no settings.py. '
            'Crie um cliente genérico para RFQs do website e defina o ID.'
        )

    cliente = Cliente.objects.filter(id=cliente_id).first()
    if not cliente:
        raise ValueError(
            f'Cliente padrão do website com ID {cliente_id} não foi encontrado.'
        )
    return cliente


def _build_observacoes_website(payload):
    linhas = []

    subject = (payload.get('assunto') or '').strip()
    description = (payload.get('descricao') or '').strip()
    contact_date = (payload.get('data_contacto') or '').strip()
    contact_time = (payload.get('hora_contacto') or '').strip()
    company = (payload.get('empresa') or '').strip()
    source_page = (payload.get('source_page') or '').strip()

    if company:
        linhas.append(f'Empresa: {company}')

    if subject:
        linhas.append(f'Assunto: {subject}')

    if description:
        linhas.append(f'Descrição: {description}')

    if contact_date or contact_time:
        linhas.append(
            f'Melhor hora para contactar: {contact_date or "—"} {contact_time or ""}'.strip()
        )

    if source_page:
        linhas.append(f'Origem website: {source_page}')

    return '\n'.join(linhas) if linhas else None


def _parse_items_from_api(payload):
    """
    Espera:
    payload["items"] = [
        {
            "descricao": "Laptop Dell",
            "quantidade": 2,
            "unidade_id": 1,
            "comentarios": "Core i7",
            "especificacoes": "16GB RAM"
        }
    ]

    ou
    payload["items_json"] = '[...]'
    """
    items = payload.get('items')

    if items is None:
        items_json = payload.get('items_json')
        if items_json:
            try:
                items = json.loads(items_json)
            except json.JSONDecodeError:
                raise ValueError('O campo items_json contém JSON inválido.')

    if not items:
        raise ValueError('Adicione pelo menos um item no RFQ.')

    if not isinstance(items, list):
        raise ValueError('O campo items deve ser uma lista.')

    itens_validos = []

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue

        descricao = (item.get('descricao') or '').strip()
        quantidade = item.get('quantidade', 1)
        unidade_id = item.get('unidade_id')
        comentarios = (item.get('comentarios') or '').strip()
        especificacoes = (item.get('especificacoes') or '').strip()

        if not descricao:
            continue

        quantidade_decimal = _parse_decimal(quantidade, '1')
        if quantidade_decimal <= 0:
            raise ValueError(f'A quantidade do item "{descricao}" deve ser maior que zero.')

        try:
            unidade_id = int(unidade_id) if unidade_id not in (None, '', 'null') else None
        except (ValueError, TypeError):
            unidade_id = None

        itens_validos.append({
            'linha': len(itens_validos) + 1,
            'descricao': descricao,
            'quantidade': quantidade_decimal,
            'unidade_id': unidade_id,
            'comentarios': comentarios or None,
            'especificacoes': especificacoes or None,
        })

    if not itens_validos:
        raise ValueError('Adicione pelo menos um item válido no RFQ.')

    return itens_validos


def _parse_api_payload(request):
    content_type = request.content_type or ''

    if 'application/json' in content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            raise ValueError('JSON inválido.')
    return request.POST


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
@require_GET
def rfq_preview_html_view(request, rfq_id):
    rfq = get_object_or_404(
        RFQ.objects.select_related('cliente', 'estado', 'criado_por').prefetch_related('itens__unidade'),
        id=rfq_id
    )
    organizacao = _get_organizacao()

    html = render_to_string(
        'rfq/includes/rfq_document_inner.html',
        {
            'rfq': rfq,
            'organizacao': organizacao,
            'preview_mode': True,
        },
        request=request
    )
    return HttpResponse(html)


@login_required
@require_GET
def rfq_download_pdf_view(request, rfq_id):
    rfq = get_object_or_404(
        RFQ.objects.select_related('cliente', 'estado', 'criado_por').prefetch_related('itens__unidade'),
        id=rfq_id
    )
    organizacao = _get_organizacao()

    html_string = render_to_string(
        'rfq/rfq_pdf.html',
        {
            'rfq': rfq,
            'organizacao': organizacao,
            'preview_mode': False,
        },
        request=request
    )

    pdf_file = HTML(
        string=html_string,
        base_url=request.build_absolute_uri('/')
    ).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{rfq.numero}.pdf"'
    return response


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


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@transaction.atomic
def public_create_rfq_api_view(request):
    """
    Endpoint público para o WordPress/Elementor enviar RFQs.

    Aceita:
    - application/json
    - multipart/form-data

    Campos esperados:
    - nome
    - telefone
    - email
    - assunto
    - descricao
    - data_contacto
    - hora_contacto
    - local_entrega (opcional)
    - prazo_entrega (opcional)
    - referencia_externa (opcional)
    - items_json ou items
    - anexos (opcional, múltiplos)
    """
    if request.method == 'OPTIONS':
        response = HttpResponse(status=204)
        return _add_cors_headers(response, request)

    try:
        payload = _parse_api_payload(request)

        # Honeypot opcional
        website_field = (payload.get('website') or '').strip()
        if website_field:
            return _json_response(
                {'success': False, 'message': 'Submissão inválida.'},
                request,
                status=400
            )

        nome = (payload.get('nome') or '').strip()
        telefone = (payload.get('telefone') or '').strip()
        email = (payload.get('email') or '').strip()
        local_entrega = (payload.get('local_entrega') or '').strip()
        referencia_externa = (payload.get('referencia_externa') or '').strip()
        prazo_entrega_raw = (payload.get('prazo_entrega') or '').strip()

        if not nome:
            raise ValueError('O nome é obrigatório.')

        if not email:
            raise ValueError('O email é obrigatório.')

        estado_novo = _get_estado_novo()
        cliente = _get_default_website_cliente()
        itens_validos = _parse_items_from_api(payload)

        prazo_entrega = parse_date(prazo_entrega_raw) if prazo_entrega_raw else None
        observacoes = _build_observacoes_website(payload)

        now = timezone.now()

        rfq = RFQ()
        rfq.numero = _generate_rfq_number()
        rfq.origem = 'api'
        rfq.cliente_id = cliente.id
        rfq.estado_id = estado_novo.id
        rfq.data_rfq = timezone.localdate()
        rfq.prazo_entrega = prazo_entrega
        rfq.local_entrega = local_entrega or None
        rfq.email_cliente = email or None
        rfq.telefone_cliente = telefone or None
        rfq.pessoa_contacto = nome or None
        rfq.referencia_externa = referencia_externa or 'Website'
        rfq.observacoes = observacoes
        rfq.criado_por = None
        rfq.criado_em = now
        rfq.actualizado_em = now
        rfq.save()
        
        # Enviar emails
        try:
            _send_rfq_emails(rfq, nome, email, telefone, payload, itens_validos)
        except Exception as e:
            print("Erro ao enviar email RFQ:", str(e))

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
                carregado_por=None,
                carregado_em=now,
            )

        return _json_response(
            {
                'success': True,
                'message': 'RFQ submetida com sucesso.',
                'rfq_id': rfq.id,
                'numero': rfq.numero,
            },
            request,
            status=201
        )

    except ValueError as e:
        return _json_response(
            {'success': False, 'message': str(e)},
            request,
            status=400
        )
    except Exception as e:
        return _json_response(
            {'success': False, 'message': f'Ocorreu um erro ao processar a RFQ: {str(e)}'},
            request,
            status=500
        )
        
        

#============================================================

def _send_rfq_emails(rfq, nome, email, telefone, payload, itens_validos):
    assunto = (payload.get('assunto') or '').strip()
    descricao = (payload.get('descricao') or '').strip()
    data_contacto = (payload.get('data_contacto') or '').strip()
    hora_contacto = (payload.get('hora_contacto') or '').strip()
    source_page = (payload.get('source_page') or '').strip()

    # ---------------------------------------------------
    # EMAIL PARA O CLIENTE
    # ---------------------------------------------------
    subject_cliente = f"RFQ {rfq.numero} submetida com sucesso"

    html_cliente = render_to_string(
        "emails/rfq_submitted.html",
        {
            "tipo_email": "cliente",
            "titulo_email": "Solicitação de Cotação Submetida",
            "rfq": rfq,
            "nome": nome,
            "email": email,
            "telefone": telefone,
            "assunto": assunto,
            "descricao": descricao,
            "data_contacto": data_contacto,
            "hora_contacto": hora_contacto,
            "source_page": source_page,
            "itens": itens_validos,
        },
    )

    msg_cliente = EmailMultiAlternatives(
        subject_cliente,
        "",
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )
    msg_cliente.attach_alternative(html_cliente, "text/html")
    msg_cliente.send()

    # ---------------------------------------------------
    # EMAIL PARA O GRUPO PROCUREMENT OFFICER (ID = 2)
    # ---------------------------------------------------
    group = Group.objects.filter(id=2).first()
    if not group:
        return

    emails_procurement = [u.email for u in group.user_set.all() if u.email]
    if not emails_procurement:
        return

    subject_internal = f"Nova RFQ submetida pelo website - {rfq.numero}"

    html_internal = render_to_string(
        "emails/rfq_submitted.html",
        {
            "tipo_email": "interno",
            "titulo_email": "Nova Solicitação de Cotação Recebida",
            "rfq": rfq,
            "nome": nome,
            "email": email,
            "telefone": telefone,
            "assunto": assunto,
            "descricao": descricao,
            "data_contacto": data_contacto,
            "hora_contacto": hora_contacto,
            "source_page": source_page,
            "itens": itens_validos,
        },
    )

    msg_internal = EmailMultiAlternatives(
        subject_internal,
        "",
        settings.DEFAULT_FROM_EMAIL,
        emails_procurement,
    )
    msg_internal.attach_alternative(html_internal, "text/html")
    msg_internal.send()
#============================================================

#============================================================


#============================================================


#============================================================


#============================================================


#============================================================


#============================================================