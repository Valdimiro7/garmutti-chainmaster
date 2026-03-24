from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST


#=========================================================================================
# Helpers
def user_is_permissions_admin(user):
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name='Administrador').exists()

#=========================================================================================
def permissions_admin_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('procurement:login')

        if not user_is_permissions_admin(request.user):
            return HttpResponseForbidden("Não tem permissão para aceder a esta página.")

        return view_func(request, *args, **kwargs)
    return _wrapped_view

#=========================================================================================
@login_required
@permissions_admin_required
@require_GET
def permissions_view(request):
    users = (
        User.objects
        .prefetch_related('groups')
        .filter(is_superuser=False)
        .order_by('username')
    )

    groups = (
        Group.objects
        .prefetch_related('user_set')
        .all()
        .order_by('name')
    )

    context = {
        'segment': 'permissoes',
        'users': users,
        'groups': groups,
    }
    return render(request, 'permissions/permissions.html', context)

#=========================================================================================
@login_required
@permissions_admin_required
@require_POST
@transaction.atomic
def create_user_view(request):
    username = (request.POST.get('username') or '').strip()
    email = (request.POST.get('email') or '').strip()
    first_name = (request.POST.get('first_name') or '').strip()
    last_name = (request.POST.get('last_name') or '').strip()
    password = request.POST.get('password') or ''
    password_confirm = request.POST.get('password_confirm') or ''
    is_active = request.POST.get('is_active', '1')
    group_ids = request.POST.getlist('groups')

    if not username:
        messages.error(request, 'O nome de utilizador é obrigatório.')
        return redirect('procurement:permissions')

    if User.objects.filter(username__iexact=username).exists():
        messages.error(request, f'Já existe um funcionário com o utilizador "{username}".')
        return redirect('procurement:permissions')

    if email and User.objects.filter(email__iexact=email).exists():
        messages.error(request, f'Já existe um funcionário com o email "{email}".')
        return redirect('procurement:permissions')

    if not password:
        messages.error(request, 'A palavra-passe é obrigatória.')
        return redirect('procurement:permissions')

    if password != password_confirm:
        messages.error(request, 'A confirmação da palavra-passe não confere.')
        return redirect('procurement:permissions')

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
    )
    user.is_active = str(is_active) == '1'
    user.save()

    if group_ids:
        groups = Group.objects.filter(id__in=group_ids)
        user.groups.set(groups)

    messages.success(request, f'Funcionário "{user.username}" criado com sucesso.')
    return redirect('procurement:permissions')

#=========================================================================================
@login_required
@permissions_admin_required
@require_POST
@transaction.atomic
def update_user_view(request, user_id):
    user = get_object_or_404(User, id=user_id)

    username = (request.POST.get('username') or '').strip()
    email = (request.POST.get('email') or '').strip()
    first_name = (request.POST.get('first_name') or '').strip()
    last_name = (request.POST.get('last_name') or '').strip()
    password = request.POST.get('password') or ''
    password_confirm = request.POST.get('password_confirm') or ''
    is_active = request.POST.get('is_active', '1')
    group_ids = request.POST.getlist('groups')

    if not username:
        messages.error(request, 'O nome de utilizador é obrigatório.')
        return redirect('procurement:permissions')

    username_exists = User.objects.filter(username__iexact=username).exclude(id=user.id).exists()
    if username_exists:
        messages.error(request, f'Já existe outro funcionário com o utilizador "{username}".')
        return redirect('procurement:permissions')

    if email:
        email_exists = User.objects.filter(email__iexact=email).exclude(id=user.id).exists()
        if email_exists:
            messages.error(request, f'Já existe outro funcionário com o email "{email}".')
            return redirect('procurement:permissions')

    user.username = username
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.is_active = str(is_active) == '1'

    if password or password_confirm:
        if password != password_confirm:
            messages.error(request, 'A confirmação da palavra-passe não confere.')
            return redirect('procurement:permissions')
        user.set_password(password)

    user.save()

    groups = Group.objects.filter(id__in=group_ids) if group_ids else Group.objects.none()
    user.groups.set(groups)

    messages.success(request, f'Funcionário "{user.username}" actualizado com sucesso.')
    return redirect('procurement:permissions')

#=========================================================================================
@login_required
@permissions_admin_required
@require_POST
def toggle_user_status_view(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if user == request.user:
        messages.error(request, 'Não pode desactivar a sua própria conta.')
        return redirect('procurement:permissions')

    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])

    estado = 'activado' if user.is_active else 'desactivado'
    messages.success(request, f'Funcionário "{user.username}" foi {estado} com sucesso.')
    return redirect('procurement:permissions')

#=========================================================================================
@login_required
@permissions_admin_required
@require_GET
def user_detail_json_view(request, user_id):
    user = get_object_or_404(User.objects.prefetch_related('groups'), id=user_id)

    data = {
        'id': user.id,
        'username': user.username,
        'email': user.email or '',
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'is_active': user.is_active,
        'groups': list(user.groups.values_list('id', flat=True)),
    }
    return JsonResponse(data)

#=========================================================================================
@login_required
@permissions_admin_required
@require_POST
@transaction.atomic
def create_group_view(request):
    group_name = (request.POST.get('group_name') or '').strip()
    member_ids = request.POST.getlist('group_members')

    if not group_name:
        messages.error(request, 'O nome da função é obrigatório.')
        return redirect('procurement:permissions')

    if Group.objects.filter(name__iexact=group_name).exists():
        messages.error(request, f'Já existe uma função com o nome "{group_name}".')
        return redirect('procurement:permissions')

    group = Group.objects.create(name=group_name)

    if member_ids:
        users = User.objects.filter(id__in=member_ids)
        group.user_set.set(users)

    messages.success(request, f'Função "{group.name}" criada com sucesso.')
    return redirect('procurement:permissions')

#=========================================================================================
@login_required
@permissions_admin_required
@require_POST
@transaction.atomic
def update_group_view(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    group_name = (request.POST.get('group_name') or '').strip()
    member_ids = request.POST.getlist('group_members')

    if not group_name:
        messages.error(request, 'O nome da função é obrigatório.')
        return redirect('procurement:permissions')

    exists = Group.objects.filter(name__iexact=group_name).exclude(id=group.id).exists()
    if exists:
        messages.error(request, f'Já existe outra função com o nome "{group_name}".')
        return redirect('procurement:permissions')

    group.name = group_name
    group.save()

    users = User.objects.filter(id__in=member_ids) if member_ids else User.objects.none()
    group.user_set.set(users)

    messages.success(request, f'Função "{group.name}" actualizada com sucesso.')
    return redirect('procurement:permissions')

#=========================================================================================
@login_required
@permissions_admin_required
@require_POST
def delete_group_view(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    if group.name.lower() == 'administrador':
        messages.error(request, 'A função "Administrador" não pode ser removida.')
        return redirect('procurement:permissions')

    group_name = group.name
    group.delete()

    messages.success(request, f'Função "{group_name}" removida com sucesso.')
    return redirect('procurement:permissions')

#=========================================================================================
@login_required
@permissions_admin_required
@require_GET
def group_detail_json_view(request, group_id):
    group = get_object_or_404(Group.objects.prefetch_related('user_set'), id=group_id)

    data = {
        'id': group.id,
        'name': group.name,
        'members': list(group.user_set.values_list('id', flat=True)),
    }
    return JsonResponse(data)

#=========================================================================================
@login_required
@permissions_admin_required
@require_POST
def assign_user_to_group_view(request):
    user_id = request.POST.get('user_id')
    group_id = request.POST.get('group_id')

    user = get_object_or_404(User, id=user_id)
    group = get_object_or_404(Group, id=group_id)

    user.groups.add(group)

    messages.success(request, f'O funcionário "{user.username}" foi alocado à função "{group.name}".')
    return redirect('procurement:permissions')

#=========================================================================================
@login_required
@permissions_admin_required
@require_POST
def remove_user_from_group_view(request):
    user_id = request.POST.get('user_id')
    group_id = request.POST.get('group_id')

    user = get_object_or_404(User, id=user_id)
    group = get_object_or_404(Group, id=group_id)

    if group.name.lower() == 'administrador' and user == request.user:
        messages.error(request, 'Não pode remover a si próprio da função Administrador.')
        return redirect('procurement:permissions')

    user.groups.remove(group)

    messages.success(request, f'O funcionário "{user.username}" foi desalocado da função "{group.name}".')
    return redirect('procurement:permissions')