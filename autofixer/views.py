"""API view for active transitions (UA-1)."""

from django.http import JsonResponse

from autofixer.tracker import TransitionTracker


def active_transitions(request):
    """Return active transitions as JSON (UA-1)."""
    tracker = TransitionTracker()
    active = tracker.get_active()
    data = [
        {
            "tr_id": t.tr_id,
            "root_id": t.root_id,
            "parent_id": t.parent_id,
            "process_class": t.process_class,
            "action_name": t.action_name,
            "instance_key": t.instance_key,
            "started_at": t.started_at,
        }
        for t in active
    ]
    return JsonResponse({"active_transitions": data, "count": len(data)})
