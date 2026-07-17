from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


PROFILE_TEXT = (
    "I am looking for engineering roles at seed-stage AI or developer-tool "
    "companies with fewer than 50 employees. I want to meet founders, "
    "engineering leaders and hiring managers at Bay Area hackathons."
)


class ProviderUnavailable(RuntimeError):
    pass


class BrowserSessionExpired(RuntimeError):
    pass


@dataclass(frozen=True)
class FakeRuntimeConfig:
    auto_registration_enabled: bool = False
    physical_mail_requires_confirmation: bool = True
    internal_token: str = "fixture-internal-token"
    max_worker_concurrency: int = 2


@dataclass
class FakeStore:
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    sessions: dict[str, dict[str, Any]] = field(default_factory=dict)
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: dict[str, dict[str, Any]] = field(default_factory=dict)
    attendees: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    enrichments: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    scores: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    email_sends: dict[str, dict[str, Any]] = field(default_factory=dict)
    registrations: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    zero_pages: dict[str, dict[str, Any]] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        return {
            "users": len(self.users),
            "sessions": len(self.sessions),
            "profiles": len(self.profiles),
            "events": len(self.events),
            "attendees": len(self.attendees),
            "enrichments": len(self.enrichments),
            "scores": len(self.scores),
            "jobs": len(self.jobs),
            "reports": len(self.reports),
            "email_sends": len(self.email_sends),
            "registrations": len(self.registrations),
            "zero_pages": len(self.zero_pages),
        }


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


class FakeMCPServer:
    def __init__(self, runtime: "FakeRuntime") -> None:
        self.runtime = runtime

    def login(self, email: str) -> dict[str, str]:
        return self.runtime.start_login(email)

    def complete_fixture_login(self, login_id: str, verification_code: str) -> dict[str, str]:
        return self.runtime.complete_login(login_id, verification_code)

    def set_user_profile(self, session_id: str, profile_text: str) -> dict[str, Any]:
        return self.runtime.save_profile(session_id, profile_text)

    def recommend_events(self, session_id: str) -> list[dict[str, Any]]:
        return self.runtime.discover_events(session_id)

    def select_event(self, session_id: str, event_id: str) -> dict[str, Any]:
        return self.runtime.select_event(session_id, event_id)

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        return self.runtime.get_job_status(job_id)

    def get_event_report(self, session_id: str, event_id: str) -> dict[str, Any]:
        return self.runtime.get_event_report(session_id, event_id)


class FakeLumaBrowser:
    def __init__(self, session_expired: bool = False) -> None:
        self.session_expired = session_expired

    def complete_login(self, email: str, verification_code: str) -> dict[str, str]:
        if self.session_expired:
            raise BrowserSessionExpired("fixture browser session expired")
        if verification_code != "000000":
            raise ValueError("invalid fixture verification code")
        return {"luma_user_id": stable_id("luma_user", email), "email": email}

    def discover_events(self, profile_text: str) -> list[dict[str, Any]]:
        if self.session_expired:
            raise BrowserSessionExpired("fixture browser session expired")
        return [
            {
                "event_id": "evt_bay_area_ai_hacknight",
                "title": "Bay Area AI Hacknight",
                "url": "https://fixture.luma.local/bay-area-ai-hacknight",
                "location": "San Francisco, CA",
                "tags": ["AI", "developer tools", "seed-stage"],
                "starts_at": "2026-08-07T18:00:00-07:00",
            },
            {
                "event_id": "evt_devtools_founder_breakfast",
                "title": "DevTools Founder Breakfast",
                "url": "https://fixture.luma.local/devtools-founder-breakfast",
                "location": "Palo Alto, CA",
                "tags": ["founders", "developer tools"],
                "starts_at": "2026-08-12T09:00:00-07:00",
            },
        ]

    def scrape_guests(self, event_id: str) -> list[dict[str, Any]]:
        if self.session_expired:
            raise BrowserSessionExpired("fixture browser session expired")
        return [
            {
                "name": "Avery Chen",
                "email": "avery@example.test",
                "company": "VectorForge",
                "role": "Founder",
            },
            {
                "name": "Mina Patel",
                "email": "mina@example.test",
                "company": "CompileCloud",
                "role": "VP Engineering",
            },
            {
                "name": "Jordan Rivera",
                "email": "jordan@example.test",
                "company": "SeedStack",
                "role": "Hiring Manager",
            },
        ]

    def register_event(self, user_id: str, event_id: str) -> dict[str, str]:
        if self.session_expired:
            raise BrowserSessionExpired("fixture browser session expired")
        return {"registration_id": stable_id("registration", f"{user_id}:{event_id}")}


class FakeNexla:
    def __init__(self, unavailable: bool = False, malformed_one: bool = False) -> None:
        self.unavailable = unavailable
        self.malformed_one = malformed_one

    def enrich_attendees(self, attendees: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.unavailable:
            raise ProviderUnavailable("Nexla unavailable")
        records: list[dict[str, Any]] = []
        for index, attendee in enumerate(attendees):
            if self.malformed_one and index == 0:
                records.append({"email": attendee["email"], "malformed": True})
                continue
            stage = "seed" if attendee["company"] != "CompileCloud" else "series-a"
            records.append(
                {
                    "email": attendee["email"],
                    "company": attendee["company"],
                    "company_stage": stage,
                    "headcount": 28 if stage == "seed" else 75,
                    "identity_confidence": 0.96 if stage == "seed" else 0.82,
                    "source": "fake-nexla-mcp",
                }
            )
        return records


class FakeAgentMail:
    def __init__(self, unavailable: bool = False) -> None:
        self.unavailable = unavailable
        self.physical_mail_confirmed = False

    def queue_report(self, report_id: str, recipient: str, subject: str) -> dict[str, str]:
        if self.unavailable:
            raise ProviderUnavailable("AgentMail unavailable")
        return {
            "message_id": stable_id("msg", f"{report_id}:{recipient}"),
            "thread_id": stable_id("thread", report_id),
            "recipient": recipient,
            "subject": subject,
        }

    def send_physical_mail(self, confirmed: bool) -> dict[str, str]:
        if not confirmed:
            raise PermissionError("physical mail requires explicit confirmation")
        return {"status": "queued"}


class FakeZero:
    def __init__(self, unavailable: bool = False) -> None:
        self.unavailable = unavailable

    def create_bingo_page(self, report_id: str, people: list[dict[str, Any]]) -> dict[str, str]:
        if self.unavailable:
            raise ProviderUnavailable("Zero unavailable")
        return {
            "zero_page_id": stable_id("zero", report_id),
            "url": f"https://zero.fixture.local/bingo/{report_id}",
            "title": "Networking Bingo",
        }


class FakeRuntimeAPI:
    def __init__(self, config: FakeRuntimeConfig) -> None:
        self.config = config

    def request_internal_route(self, path: str, token: str | None = None) -> dict[str, Any]:
        if not path.startswith("/internal/"):
            return {"status": 404}
        if token != self.config.internal_token:
            return {"status": 401, "body": "missing or invalid runtime token"}
        return {"status": 200, "body": "ok"}


class FakeRuntime:
    def __init__(
        self,
        *,
        store: FakeStore | None = None,
        browser: FakeLumaBrowser | None = None,
        nexla: FakeNexla | None = None,
        agentmail: FakeAgentMail | None = None,
        zero: FakeZero | None = None,
        config: FakeRuntimeConfig | None = None,
        partial_report_seed: bool = False,
    ) -> None:
        self.store = store or FakeStore()
        self.browser = browser or FakeLumaBrowser()
        self.nexla = nexla or FakeNexla()
        self.agentmail = agentmail or FakeAgentMail()
        self.zero = zero or FakeZero()
        self.config = config or FakeRuntimeConfig()
        self.api = FakeRuntimeAPI(self.config)
        self.partial_report_seed = partial_report_seed
        self.warnings: list[str] = []

    def start_login(self, email: str) -> dict[str, str]:
        user_id = stable_id("user", email)
        self.store.users.setdefault(user_id, {"user_id": user_id, "email": email})
        login_id = stable_id("login", email)
        return {"login_id": login_id, "verification_code": "000000"}

    def complete_login(self, login_id: str, verification_code: str) -> dict[str, str]:
        email = "demo@lumabot.local"
        user_id = stable_id("user", email)
        self.browser.complete_login(email, verification_code)
        session_id = stable_id("session", user_id)
        self.store.users.setdefault(user_id, {"user_id": user_id, "email": email})
        self.store.sessions.setdefault(session_id, {"session_id": session_id, "user_id": user_id})
        return {"session_id": session_id, "user_id": user_id}

    def save_profile(self, session_id: str, profile_text: str) -> dict[str, Any]:
        user_id = self._user_id(session_id)
        profile_id = stable_id("profile", f"{user_id}:{profile_text}")
        profile = {"profile_id": profile_id, "user_id": user_id, "text": profile_text}
        self.store.profiles[user_id] = profile
        return profile

    def discover_events(self, session_id: str) -> list[dict[str, Any]]:
        self._user_id(session_id)
        profile_text = next(iter(self.store.profiles.values()), {"text": PROFILE_TEXT})["text"]
        events = self.browser.discover_events(profile_text)
        for event in events:
            self.store.events.setdefault(event["event_id"], event)
        return events

    def select_event(self, session_id: str, event_id: str) -> dict[str, Any]:
        job = self.queue_event_job(session_id, event_id)
        self.run_report_job(job["job_id"])
        return self.store.jobs[job["job_id"]]

    def queue_event_job(self, session_id: str, event_id: str) -> dict[str, Any]:
        user_id = self._user_id(session_id)
        if event_id not in self.store.events:
            raise KeyError(f"unknown fixture event {event_id}")
        if self.config.auto_registration_enabled:
            raise AssertionError("auto-registration must not default to enabled")
        registration = self.browser.register_event(user_id, event_id)
        self.store.registrations.setdefault((user_id, event_id), registration)
        job_id = stable_id("job", f"{user_id}:{event_id}")
        self.store.jobs.setdefault(
            job_id,
            {
                "job_id": job_id,
                "event_id": event_id,
                "user_id": user_id,
                "status": "queued",
                "attempts": 0,
            },
        )
        return self.store.jobs[job_id]

    def run_report_job(self, job_id: str, *, stop_after_partial: bool = False) -> dict[str, Any]:
        job = self.store.jobs[job_id]
        job["attempts"] += 1
        job["status"] = "running"
        self.warnings = []
        report_id = stable_id("report", f"{job['user_id']}:{job['event_id']}")
        if self.partial_report_seed or stop_after_partial:
            self.store.reports.setdefault(
                report_id,
                {
                    "report_id": report_id,
                    "event_id": job["event_id"],
                    "status": "partial",
                    "people": [],
                    "warnings": ["report partially generated before worker restart"],
                    "created_at": now_iso(),
                },
            )
            self.partial_report_seed = False
            if stop_after_partial:
                job["status"] = "interrupted"
                return self.store.reports[report_id]

        attendees = self._scrape_attendees(job["event_id"])
        enrichment_by_email = self._enrich(attendees)
        people = [self._score(attendee, enrichment_by_email.get(attendee["email"])) for attendee in attendees]
        people.sort(key=lambda person: person["relevance_score"], reverse=True)
        report = {
            "report_id": report_id,
            "event_id": job["event_id"],
            "status": "partial" if self.warnings else "complete",
            "top_people": people,
            "company_stages": sorted({person["company_stage"] for person in people}),
            "warnings": list(dict.fromkeys(self.warnings)),
            "created_at": self.store.reports.get(report_id, {}).get("created_at", now_iso()),
        }
        self.store.reports[report_id] = report
        self._queue_email(report)
        self._create_zero_page(report)
        job["status"] = "complete" if report["status"] == "complete" else "partial"
        job["report_id"] = report_id
        return report

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        return self.store.jobs[job_id]

    def get_event_report(self, session_id: str, event_id: str) -> dict[str, Any]:
        user_id = self._user_id(session_id)
        report_id = stable_id("report", f"{user_id}:{event_id}")
        return self.store.reports[report_id]

    def run_full_fixture_workflow(self) -> dict[str, Any]:
        login = self.start_login("demo@lumabot.local")
        session = self.complete_login(login["login_id"], login["verification_code"])
        profile = self.save_profile(session["session_id"], PROFILE_TEXT)
        events = self.discover_events(session["session_id"])
        selected = events[0]
        job = self.select_event(session["session_id"], selected["event_id"])
        report = self.get_event_report(session["session_id"], selected["event_id"])
        return {
            "login": {"login_id": login["login_id"]},
            "session": session,
            "profile": profile,
            "events": events,
            "selected_event": selected,
            "job": job,
            "report": report,
            "email_send": self.store.email_sends.get(report["report_id"]),
            "zero_page": self.store.zero_pages.get(report["report_id"]),
            "counts": self.store.counts(),
        }

    def _scrape_attendees(self, event_id: str) -> list[dict[str, Any]]:
        attendees = self.browser.scrape_guests(event_id)
        for attendee in attendees:
            self.store.attendees.setdefault((event_id, attendee["email"]), attendee)
        return list(self.store.attendees[key] for key in self.store.attendees if key[0] == event_id)

    def _enrich(self, attendees: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        try:
            records = self.nexla.enrich_attendees(attendees)
        except ProviderUnavailable as exc:
            self.warnings.append(str(exc))
            return {}
        enrichment_by_email: dict[str, dict[str, Any]] = {}
        for record in records:
            email = record.get("email")
            if not email or "identity_confidence" not in record:
                self.warnings.append("one enrichment record malformed")
                continue
            self.store.enrichments.setdefault((record["company"], email), record)
            enrichment_by_email[email] = record
        return enrichment_by_email

    def _score(self, attendee: dict[str, Any], enrichment: dict[str, Any] | None) -> dict[str, Any]:
        company_stage = (enrichment or {}).get("company_stage", "unknown")
        identity_confidence = float((enrichment or {}).get("identity_confidence", 0.4))
        role = attendee["role"].lower()
        relevance = 60
        if "founder" in role:
            relevance += 25
        if "engineering" in role or "hiring" in role:
            relevance += 20
        if company_stage == "seed":
            relevance += 10
        if company_stage == "unknown":
            relevance -= 15
        score = {
            "name": attendee["name"],
            "email": attendee["email"],
            "company": attendee["company"],
            "role": attendee["role"],
            "company_stage": company_stage,
            "relevance_score": min(relevance, 100),
            "identity_confidence": identity_confidence,
        }
        self.store.scores[(attendee["company"], attendee["email"])] = score
        return score

    def _queue_email(self, report: dict[str, Any]) -> None:
        if report["report_id"] in self.store.email_sends:
            return
        try:
            send = self.agentmail.queue_report(
                report["report_id"],
                "demo@lumabot.local",
                "Your LumaBot event report",
            )
        except ProviderUnavailable as exc:
            self.warnings.append(str(exc))
            report["status"] = "partial"
            report["warnings"] = list(dict.fromkeys(self.warnings))
            return
        self.store.email_sends[report["report_id"]] = send

    def _create_zero_page(self, report: dict[str, Any]) -> None:
        if report["report_id"] in self.store.zero_pages:
            return
        try:
            page = self.zero.create_bingo_page(report["report_id"], report["top_people"])
        except ProviderUnavailable as exc:
            self.warnings.append(str(exc))
            report["status"] = "partial"
            report["warnings"] = list(dict.fromkeys(self.warnings))
            return
        self.store.zero_pages[report["report_id"]] = page

    def _user_id(self, session_id: str) -> str:
        if session_id not in self.store.sessions:
            raise PermissionError("session required")
        return self.store.sessions[session_id]["user_id"]


def now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def workflow_as_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, sort_keys=True)
