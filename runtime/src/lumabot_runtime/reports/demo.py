from __future__ import annotations

import asyncio
import json
from pathlib import Path

from lumabot_runtime.reports.generator import generate_event_report
from lumabot_runtime.reports.renderers import render_html_report, render_text_email
from lumabot_runtime.reports.fixtures import demo_fixture


async def main() -> None:
    user_profile, event, attendees, enriched = demo_fixture(full=True)
    report = await generate_event_report(user_profile, event, attendees, enriched)
    artifact_dir = Path("artifacts")
    artifact_dir.mkdir(exist_ok=True)
    json_path = artifact_dir / "event-report.json"
    html_path = artifact_dir / "event-report.html"
    text_path = artifact_dir / "event-report.txt"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    html_path.write_text(render_html_report(report), encoding="utf-8")
    text_path.write_text(render_text_email(report), encoding="utf-8")

    print("Ranked attendee list")
    for person in report.top_people_to_meet:
        score = person.relevance_score.score if person.relevance_score else "pending"
        print(f"- {person.attendee.full_name}: score={score}, identity={person.identity_confidence:.2f}")
    print(f"JSON report: {json_path}")
    print(f"HTML report: {html_path}")
    print(f"Plain-text email body: {text_path}")
    print(json.dumps({"report_completeness": report.report_completeness}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

