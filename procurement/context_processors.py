def user_group_flags(request):
    is_administrador = False

    if request.user.is_authenticated:
        is_administrador = request.user.groups.filter(name='Administrador').exists()

    return {
        'is_administrador': is_administrador,
    }