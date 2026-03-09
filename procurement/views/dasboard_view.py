from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def dashboard(request):
    """
    Procurement application dashboard
    """
    context = {
        "page_title": "Garmutti ChainMaster",
        "system_name": "Procurement Management System"
    }

    return render(request, "dashboard/dashboard.html", context)