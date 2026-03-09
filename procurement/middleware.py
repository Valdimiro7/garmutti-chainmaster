# /home/garmutti/garmuttiRepo/procurement/middleware.py

import traceback
from pathlib import Path
from django.http import HttpResponse

LOG_FILE = Path("/home/garmutti/garmuttiRepo/request_trace.log")


class RequestTraceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n--- REQUEST START {request.method} {request.path} ---\n")
            response = self.get_response(request)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"--- REQUEST END {request.method} {request.path} status={response.status_code} ---\n")
            return response
        except Exception:
            tb = traceback.format_exc()
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write("\n*** EXCEPTION ***\n")
                f.write(tb)
                f.write("\n")
            return HttpResponse(
                "<h1>Django captured an exception</h1><pre>%s</pre>" % tb,
                status=500,
                content_type="text/html",
            )