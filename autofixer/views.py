from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from autofixer.monitor import get_monitor


@require_GET
def active_transitions(request):
    status = get_monitor().get_status()
    return JsonResponse(status)

