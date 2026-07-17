from __future__ import annotations

import html

from lumabot_runtime.reports.models import EventReport


def render_html_report(report: EventReport) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(person.attendee.full_name)}</td>"
        f"<td>{html.escape(person.company or '')}</td>"
        f"<td>{person.relevance_score.score if person.relevance_score else 'pending'}</td>"
        f"<td>{person.identity_confidence:.2f}</td>"
        f"<td>{html.escape(person.why_the_person_matters)}</td>"
        "</tr>"
        for person in report.attendees
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>"
        f"{html.escape(report.event.title)} report</title></head><body>"
        f"<h1>{html.escape(report.event.title)}</h1>"
        f"<p>{html.escape(report.event_summary)}</p>"
        "<table><thead><tr><th>Name</th><th>Company</th><th>Score</th>"
        "<th>Identity</th><th>Why</th></tr></thead><tbody>"
        f"{rows}</tbody></table></body></html>"
    )


def render_text_email(report: EventReport) -> str:
    lines = [
        f"LumaBot report: {report.event.title}",
        report.event_summary,
        "",
        "Top people:",
    ]
    for person in report.top_people_to_meet:
        score = person.relevance_score.score if person.relevance_score else "pending"
        lines.append(
            f"- {person.attendee.full_name}: score={score}, "
            f"identity={person.identity_confidence:.2f}, {person.conversation_opener}"
        )
    return "\n".join(lines)

