from django.urls import path
from procurement.views.dasboard_view import dashboard
from procurement.views.auth.auth_views import ProcurementLoginView
from django.contrib.auth.views import LogoutView
from procurement.views.permissions.permissions_view import (
    permissions_view,
    create_user_view,
    update_user_view,
    toggle_user_status_view,
    user_detail_json_view,
    create_group_view,
    update_group_view,
    delete_group_view,
    group_detail_json_view,
    assign_user_to_group_view,
    remove_user_from_group_view,
)

from procurement.views.clientes.clientes_views import (
    clientes_view,
    cliente_detail_json_view,
    create_cliente_view,
    update_cliente_view,
    toggle_cliente_status_view,
    delete_cliente_view,
)

from procurement.views.fornecedores.fornecedores_view import (
    fornecedores_view,
    fornecedor_detail_json_view,
    create_fornecedor_view,
    update_fornecedor_view,
    toggle_fornecedor_status_view,
    delete_fornecedor_view,
)

from procurement.views.rfq.rfq_view import (
    rfqs_view,
    rfq_detail_json_view,
    create_rfq_view,
    update_rfq_view,
    delete_rfq_view,
)




app_name = "procurement"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("login/", ProcurementLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    
    # ── RFQs ───────────────────────────────────────────────────────────────────────
    path('rfqs/', rfqs_view, name='rfqs'),
    path('rfqs/create/', create_rfq_view, name='rfqs_create'),
    path('rfqs/<int:rfq_id>/json/', rfq_detail_json_view, name='rfqs_detail_json'),
    path('rfqs/<int:rfq_id>/update/', update_rfq_view, name='rfqs_update'),
    path('rfqs/<int:rfq_id>/delete/', delete_rfq_view, name='rfqs_delete'),
    
    
    #Fornecesores
    path('fornecedores/', fornecedores_view, name='fornecedores'),
    path('fornecedores/create/', create_fornecedor_view, name='fornecedores_create'),
    path('fornecedores/<int:fornecedor_id>/json/', fornecedor_detail_json_view, name='fornecedores_detail_json'),
    path('fornecedores/<int:fornecedor_id>/update/', update_fornecedor_view, name='fornecedores_update'),
    path('fornecedores/<int:fornecedor_id>/toggle-status/', toggle_fornecedor_status_view, name='fornecedores_toggle_status'),
    path('fornecedores/<int:fornecedor_id>/delete/', delete_fornecedor_view, name='fornecedores_delete'),
    
    

    # ── Clientes ──────────────────────────────────────────────────────────────────
    path('clientes/',                                  clientes_view,               name='clientes'),
    path('clientes/create/',                           create_cliente_view,         name='clientes_create'),
    path('clientes/<int:cliente_id>/update/',          update_cliente_view,         name='clientes_update'),
    path('clientes/<int:cliente_id>/toggle-status/',   toggle_cliente_status_view,  name='clientes_toggle_status'),
    path('clientes/<int:cliente_id>/delete/',          delete_cliente_view,         name='clientes_delete'),
    path('clientes/<int:cliente_id>/json/',            cliente_detail_json_view,    name='clientes_detail_json'),
    
    
    #===============Administração de Permissões==========================================
    path('permissions/', permissions_view, name='permissions'),

    path('permissions/users/create/', create_user_view, name='permissions_create_user'),
    path('permissions/users/<int:user_id>/update/', update_user_view, name='permissions_update_user'),
    path('permissions/users/<int:user_id>/toggle-status/', toggle_user_status_view, name='permissions_toggle_user_status'),
    path('permissions/users/<int:user_id>/json/', user_detail_json_view, name='permissions_user_detail_json'),

    path('permissions/groups/create/', create_group_view, name='permissions_create_group'),
    path('permissions/groups/<int:group_id>/update/', update_group_view, name='permissions_update_group'),
    path('permissions/groups/<int:group_id>/delete/', delete_group_view, name='permissions_delete_group'),
    path('permissions/groups/<int:group_id>/json/', group_detail_json_view, name='permissions_group_detail_json'),

    path('permissions/assign-user-group/', assign_user_to_group_view, name='permissions_assign_user_group'),
    path('permissions/remove-user-group/', remove_user_from_group_view, name='permissions_remove_user_group'),
]