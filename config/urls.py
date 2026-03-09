# from django.contrib import admin
from django.urls import include, path
from django.http import HttpResponse


def live_test(request):
    return HttpResponse("LIVE TEST OK")

# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path("live-test/", live_test),
#     path("", include("procurement.urls")),
# ]

urlpatterns = [
    path("", live_test),
    path("live-test/", live_test),
]