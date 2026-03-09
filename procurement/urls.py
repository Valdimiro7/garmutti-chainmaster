from django.urls import path
from procurement.views.dasboard_view import dashboard


app_name = "procurement"

urlpatterns = [
    path("", dashboard, name="dashboard"),
]