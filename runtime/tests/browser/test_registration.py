from __future__ import annotations

from pathlib import Path

from lumabot_runtime.browser import inspect_registration_form


def test_fixture_based_registration_form_inspection() -> None:
    html = (Path(__file__).parents[1] / "luma" / "fixtures" / "registration-form.html").read_text()
    form = inspect_registration_form(html)

    assert form.action == "/event/register"
    assert form.method == "post"
    assert form.captcha_present is True
    assert [(field.name, field.required) for field in form.fields] == [
        ("full_name", True),
        ("company", False),
        ("dietary_notes", False),
    ]

