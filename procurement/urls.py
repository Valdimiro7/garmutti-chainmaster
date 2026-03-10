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
    rfq_preview_html_view,
    rfq_download_pdf_view,
    create_rfq_view,
    update_rfq_view,
    cancel_rfq_view,
    public_create_rfq_api_view,
)
from procurement.views.quotacoes.quotacoes_views import(quotacoes_view, create_quotacao_view, update_quotacao_view, quotacao_detail_json_view, quotacao_preview_html_view, quotacao_download_pdf_view, change_estado_quotacao_view, rfq_itens_json_view)
from procurement.views.configuracoes.metodos_pagamento_view import (metodos_pagamento_view, metodo_pagamento_detail_json_view, create_metodo_pagamento_view, update_metodo_pagamento_view, toggle_metodo_pagamento_status_view, definir_metodo_pagamento_predefinido_view, delete_metodo_pagamento_view)
from procurement.views.configuracoes.moedas_view import (moedas_view, moeda_detail_json_view, create_moeda_view, update_moeda_view, toggle_moeda_status_view, definir_moeda_predefinida_view, delete_moeda_view)
from procurement.views.configuracoes.organizacao_view import (organizacao_view, organizacao_detail_json_view, create_organizacao_view, update_organizacao_view, toggle_organizacao_status_view, delete_organizacao_view)
from procurement.views.configuracoes.condicoes_pagamento_view import (condicoes_pagamento_view, condicao_pagamento_detail_json_view, create_condicao_pagamento_view, update_condicao_pagamento_view, toggle_condicao_pagamento_status_view, delete_condicao_pagamento_view)
from procurement.views.po.purchase_order_view import (download_purchase_order_anexo_view, purchase_orders_view, create_purchase_order_view, update_purchase_order_view, purchase_order_detail_json_view, change_estado_purchase_order_view)
from procurement.views.pagamentos.pagamento_view import (pagamentos_view, pagamento_detail_json_view, update_pagamento_view, download_pagamento_anexo_view)




app_name = "procurement"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("login/", ProcurementLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    
    # ── RFQs ───────────────────────────────────────────────────────────────────────
    path('rfqs/', rfqs_view, name='rfqs'),
    path('rfqs/create/', create_rfq_view, name='rfqs_create'),
    path('rfqs/<int:rfq_id>/json/', rfq_detail_json_view, name='rfqs_detail_json'),
    path('rfqs/<int:rfq_id>/preview/', rfq_preview_html_view, name='rfqs_preview'),
    path('rfqs/<int:rfq_id>/download-pdf/', rfq_download_pdf_view, name='rfqs_download_pdf'),
    path('rfqs/<int:rfq_id>/update/', update_rfq_view, name='rfqs_update'),
    path('rfqs/<int:rfq_id>/cancel/', cancel_rfq_view, name='rfqs_cancel'),
    
    path('api/public/rfqs/create/', public_create_rfq_api_view, name='public_create_rfq_api'),
    
    
    
    # Adicionar ao procurement/urls.py (dentro do urlpatterns existente):

    # ── Quotações ──────────────────────────────────────────────────────────────────
    path('quotacoes/',                              quotacoes_view,               name='quotacoes'),
    path('quotacoes/create/',                       create_quotacao_view,         name='quotacoes_create'),
    path('quotacoes/<int:quotacao_id>/update/',     update_quotacao_view,         name='quotacoes_update'),
    path('quotacoes/<int:quotacao_id>/json/',       quotacao_detail_json_view,    name='quotacoes_detail_json'),
    path('quotacoes/<int:quotacao_id>/preview/',    quotacao_preview_html_view,   name='quotacoes_preview'),
    path('quotacoes/<int:quotacao_id>/download-pdf/', quotacao_download_pdf_view, name='quotacoes_download_pdf'),
    path('quotacoes/<int:quotacao_id>/estado/',     change_estado_quotacao_view,  name='quotacoes_change_estado'),
    path('rfqs/<int:rfq_id>/itens-json/',           rfq_itens_json_view,          name='rfq_itens_json'),
    
    
    
    #======================Gestão de POs - Purchase Orders==========================================
    path('purchase-orders/', purchase_orders_view, name='purchase_orders'),
    path('purchase-orders/create/', create_purchase_order_view, name='purchase_orders_create'),
    path('purchase-orders/<int:po_id>/update/', update_purchase_order_view, name='purchase_orders_update'),
    path('purchase-orders/<int:po_id>/json/', purchase_order_detail_json_view, name='purchase_orders_json'),
    path('purchase-orders/<int:po_id>/estado/', change_estado_purchase_order_view, name='purchase_orders_estado'),
    path('purchase-orders/anexos/<int:anexo_id>/download/', download_purchase_order_anexo_view, name='purchase_orders_anexo_download'),
    
    
    
    #======================Pagamentos==========================================
    path('pagamentos/', pagamentos_view, name='pagamentos'),
    path('pagamentos/<int:pagamento_id>/json/', pagamento_detail_json_view, name='pagamentos_json'),
    path('pagamentos/<int:pagamento_id>/update/', update_pagamento_view, name='pagamentos_update'),
    path('pagamentos/anexos/<int:anexo_id>/download/', download_pagamento_anexo_view, name='pagamentos_anexo_download'),
    
    
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
    
    #======================configurações - condições de pagamento======================================================
    path('condicoes-pagamento/', condicoes_pagamento_view, name='condicoes_pagamento'),
    path('condicoes-pagamento/<int:condicao_id>/json/', condicao_pagamento_detail_json_view, name='condicoes_pagamento_detail_json'),
    path('condicoes-pagamento/create/', create_condicao_pagamento_view, name='condicoes_pagamento_create'),
    path('condicoes-pagamento/<int:condicao_id>/update/', update_condicao_pagamento_view, name='condicoes_pagamento_update'),
    path('condicoes-pagamento/<int:condicao_id>/toggle-status/', toggle_condicao_pagamento_status_view, name='condicoes_pagamento_toggle_status'),
    path('condicoes-pagamento/<int:condicao_id>/delete/', delete_condicao_pagamento_view, name='condicoes_pagamento_delete'),
    
    
    #======================configurações - organização======================================================
    path('organizacao/', organizacao_view, name='organizacao'),
    path('organizacao/<int:organizacao_id>/json/', organizacao_detail_json_view, name='organizacao_detail_json'),
    path('organizacao/create/', create_organizacao_view, name='organizacao_create'),
    path('organizacao/<int:organizacao_id>/update/', update_organizacao_view, name='organizacao_update'),
    path('organizacao/<int:organizacao_id>/toggle-status/', toggle_organizacao_status_view, name='organizacao_toggle_status'),
    path('organizacao/<int:organizacao_id>/delete/', delete_organizacao_view, name='organizacao_delete'),
    
    #======================configurações - moedas======================================================
    path('moedas/', moedas_view, name='moedas'),
    path('moedas/<int:moeda_id>/json/', moeda_detail_json_view, name='moedas_detail_json'),
    path('moedas/create/', create_moeda_view, name='moedas_create'),
    path('moedas/<int:moeda_id>/update/', update_moeda_view, name='moedas_update'),
    path('moedas/<int:moeda_id>/toggle-status/', toggle_moeda_status_view, name='moedas_toggle_status'),
    path('moedas/<int:moeda_id>/definir-predefinida/', definir_moeda_predefinida_view, name='moedas_definir_predefinida'),
    path('moedas/<int:moeda_id>/delete/', delete_moeda_view, name='moedas_delete'),
    
    #=====================configurações - métodos de pagamento==========================================
    path('metodos-pagamento/', metodos_pagamento_view, name='metodos_pagamento'),
    path('metodos-pagamento/<int:metodo_id>/json/', metodo_pagamento_detail_json_view, name='metodos_pagamento_detail_json'),
    path('metodos-pagamento/create/', create_metodo_pagamento_view, name='metodos_pagamento_create'),
    path('metodos-pagamento/<int:metodo_id>/update/', update_metodo_pagamento_view, name='metodos_pagamento_update'),
    path('metodos-pagamento/<int:metodo_id>/toggle-status/', toggle_metodo_pagamento_status_view, name='metodos_pagamento_toggle_status'),
    path('metodos-pagamento/<int:metodo_id>/definir-predefinido/', definir_metodo_pagamento_predefinido_view, name='metodos_pagamento_definir_predefinido'),
    path('metodos-pagamento/<int:metodo_id>/delete/', delete_metodo_pagamento_view, name='metodos_pagamento_delete'),
]