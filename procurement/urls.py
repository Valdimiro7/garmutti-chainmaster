from django.urls import path
from procurement.views.dasboard_view import dashboard
from procurement.views.auth.auth_views import ProcurementLoginView
from django.contrib.auth.views import LogoutView


app_name = "procurement"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("login/", ProcurementLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]