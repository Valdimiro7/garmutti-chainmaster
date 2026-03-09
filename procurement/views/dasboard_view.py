from django.shortcuts import render


def dashboard(request):
    """
    Procurement application dashboard
    """
    context = {
        "page_title": "Garmutti ChainMaster",
        "system_name": "Procurement Management System"
    }

    return render(request, "dashboard/dashboard.html", context)