from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from lumabot_runtime.email.client import EmailNotificationService
from lumabot_runtime.models import ActionRecord, Event, RuntimeState, UserProfile, utc_now


@dataclass(frozen=True)
class AutoRegistrationDecision:
    outcome: Literal["registered", "confirmation_required", "skipped"]
    reason: str
    action: ActionRecord | None = None


class RegistrationService:
    def __init__(self, state: RuntimeState, email_service: EmailNotificationService) -> None:
        self._state = state
        self._email_service = email_service

    async def auto_register_event(self, *, user_id: str, event: Event) -> AutoRegistrationDecision:
        profile = self._state.profiles[user_id]
        blocking_reason = self._blocking_reason(profile, event)
        if blocking_reason:
            action = self._create_confirmation_action(
                user_id=user_id,
                event=event,
                reason=blocking_reason,
            )
            return AutoRegistrationDecision("confirmation_required", blocking_reason, action)
        if (user_id, event.id) in self._state.user_events:
            return AutoRegistrationDecision("skipped", "user is already registered")
        self._state.user_events.add((user_id, event.id))
        event.registered = True
        self._state.audit_records.append(
            {
                "type": "AUTO_REGISTER_EVENT",
                "user_id": user_id,
                "event_id": event.id,
                "verified": True,
                "created_at": utc_now().isoformat(),
            }
        )
        await self._email_service.send_registration_confirmation(user_id=user_id, event_id=event.id)
        return AutoRegistrationDecision("registered", "registration verified")

    async def confirm_action(self, *, action_id: str, approved: bool) -> ActionRecord:
        action = self._state.actions[action_id]
        action.status = "approved" if approved else "rejected"
        action.completed_at = utc_now()
        if approved and action.type == "AUTO_REGISTER_EVENT":
            self._state.user_events.add((action.user_id, str(action.payload["event_id"])))
            self._state.audit_records.append(
                {
                    "type": "CONFIRMED_REGISTER_EVENT",
                    "user_id": action.user_id,
                    "event_id": action.payload["event_id"],
                    "created_at": utc_now().isoformat(),
                }
            )
            await self._email_service.send_registration_confirmation(
                user_id=action.user_id,
                event_id=str(action.payload["event_id"]),
            )
            action.status = "completed"
        return action

    def _blocking_reason(self, profile: UserProfile, event: Event) -> str | None:
        settings = profile.structured.auto_registration
        if not settings.enabled:
            return "auto-registration is disabled"
        if event.relevance_score < settings.relevance_threshold:
            return "event relevance is below threshold"
        if event.price_usd > settings.max_price_usd or event.requires_payment:
            return "payment is required"
        if event.calendar_conflict:
            return "calendar conflict exists"
        if event.requires_custom_answers:
            return "custom written answers are required"
        if event.requires_unusual_consent:
            return "unusual consent is required"
        if (profile.user_id, event.id) in self._state.user_events or event.registered:
            return "user is already registered"
        return None

    def _create_confirmation_action(
        self,
        *,
        user_id: str,
        event: Event,
        reason: str,
    ) -> ActionRecord:
        existing = next(
            (
                action
                for action in self._state.actions.values()
                if action.user_id == user_id
                and action.type == "AUTO_REGISTER_EVENT"
                and action.payload.get("event_id") == event.id
                and action.status == "pending"
            ),
            None,
        )
        if existing:
            return existing
        action = ActionRecord(
            user_id=user_id,
            type="AUTO_REGISTER_EVENT",
            payload={"event_id": event.id, "reason": reason},
        )
        self._state.actions[action.id] = action
        return action
