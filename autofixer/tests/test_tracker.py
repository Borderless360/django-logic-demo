from datetime import datetime, timedelta, timezone

from autofixer.events import EventType, TransitionEvent
from autofixer.tracker import ActiveTransitionTracker


def test_tracker_tracks_and_completes_transition(fake_redis):
    tracker = ActiveTransitionTracker(key_prefix="autofixer-test", redis=fake_redis)
    started_at = datetime.now(tz=timezone.utc)

    tracker.apply(
        TransitionEvent(
            tr_id="tr-1",
            event_type=EventType.START,
            timestamp=started_at,
            process_class="BasicProcess",
            action_name="go_to_B",
            instance_key="abstract-a-status-1",
            root_id="root-1",
            parent_id="root-1",
            raw_message="",
        )
    )

    tracker.apply(
        TransitionEvent(
            tr_id="tr-1",
            event_type=EventType.SIDE_EFFECT,
            timestamp=started_at + timedelta(seconds=1),
            name="send_notification",
            raw_message="",
        )
    )

    completion = tracker.apply(
        TransitionEvent(
            tr_id="tr-1",
            event_type=EventType.UNLOCK,
            timestamp=started_at + timedelta(seconds=4),
            raw_message="",
        )
    )

    assert completion is not None
    assert completion.duration_seconds == 4
    assert completion.side_effect_durations == [("send_notification", 3.0)]
    assert tracker.get_active() == []


def test_tracker_restores_from_redis(fake_redis):
    tracker_1 = ActiveTransitionTracker(key_prefix="autofixer-test", redis=fake_redis)
    started_at = datetime.now(tz=timezone.utc)
    tracker_1.apply(
        TransitionEvent(
            tr_id="tr-2",
            event_type=EventType.START,
            timestamp=started_at,
            process_class="BasicProcess",
            action_name="go_to_B",
            instance_key="abstract-a-status-2",
            root_id="root-2",
            parent_id="root-2",
            raw_message="",
        )
    )

    tracker_2 = ActiveTransitionTracker(key_prefix="autofixer-test", redis=fake_redis)
    active = tracker_2.get_active()
    assert len(active) == 1
    assert active[0]["tr_id"] == "tr-2"

