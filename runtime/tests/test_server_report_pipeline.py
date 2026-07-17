from __future__ import annotations

from pathlib import Path

from starlette.testclient import TestClient

from lumabot_runtime.server import app, state

FIXTURES = Path(__file__).parent / "luma" / "fixtures"


def test_report_job_uses_luma_guest_html_pipeline() -> None:
    state.reports.clear()
    state.report_jobs.clear()

    with TestClient(app) as client:
        response = client.post(
            "/events/sf-ai-build-night/report/jobs",
            json={
                "event_url": "https://lu.ma/sf-ai-build-night",
                "event_html": (FIXTURES / "event.html").read_text(),
                "guest_html": (FIXTURES / "guest-list.html").read_text(),
                "profile_text": "I want to meet AI developer tools founders.",
            },
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        job = client.get(f"/jobs/{job_id}").json()["job"]
        assert job["status"] == "completed"
        assert job["result"]["visible_guest_count"] == 2
        assert job["result"]["report"]["event"]["title"] == "SF AI Build Night"
        assert job["result"]["report"]["attendees"][0]["attendee"]["full_name"] in {
            "Ava Chen",
            "Noah Patel",
        }

        cached = client.get("/events/sf-ai-build-night/report").json()["report"]
        assert cached["event"]["title"] == "SF AI Build Night"
