from __future__ import annotations

from lumabot_runtime.actions.registration import RegistrationService
from lumabot_runtime.email.client import EmailNotificationService, FakeEmailClient
from lumabot_runtime.models import Event, RuntimeState, UserProfile, utc_now
from lumabot_runtime.profiles import parse_profile


def _state(enabled: bool = True) -> tuple[RuntimeState, RegistrationService, Event]:
    state = RuntimeState()
    profile = UserProfile(
        user_id="u1",
        notification_email="u1@example.com",
        original_text="SF AI founder",
        structured=parse_profile("SF AI founder auto-register free events"),
    )
    profile.structured.auto_registration.enabled = enabled
    state.profiles["u1"] = profile
    service = RegistrationService(state, EmailNotificationService(state, FakeEmailClient()))
    event = Event(id="e1", title="AI Mixer", starts_at=utc_now(), relevance_score=0.9)
    return state, service, event


async def test_auto_registration_enabled_success_and_duplicate() -> None:
    state, service, event = _state(enabled=True)
    decision = await service.auto_register_event(user_id="u1", event=event)
    assert decision.outcome == "registered"
    assert ("u1", "e1") in state.user_events
    duplicate = await service.auto_register_event(user_id="u1", event=event)
    assert duplicate.outcome == "confirmation_required"
    assert duplicate.reason == "user is already registered"


async def test_auto_registration_blockers_require_confirmation() -> None:
    _state_obj, service, event = _state(enabled=False)
    disabled = await service.auto_register_event(user_id="u1", event=event)
    assert disabled.outcome == "confirmation_required"

    _state_obj, service, event = _state(enabled=True)
    event.requires_payment = True
    paid = await service.auto_register_event(user_id="u1", event=event)
    assert paid.reason == "payment is required"

    _state_obj, service, event = _state(enabled=True)
    event.requires_custom_answers = True
    custom = await service.auto_register_event(user_id="u1", event=event)
    assert custom.reason == "custom written answers are required"


async def test_confirmation_flow() -> None:
    state, service, event = _state(enabled=False)
    decision = await service.auto_register_event(user_id="u1", event=event)
    assert decision.action is not None
    action = await service.confirm_action(action_id=decision.action.id, approved=True)
    assert action.status == "completed"
    assert ("u1", "e1") in state.user_events
