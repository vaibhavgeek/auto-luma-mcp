from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class RegistrationField:
    name: str
    label: str
    field_type: str
    required: bool


@dataclass(frozen=True)
class RegistrationFormInspection:
    action: str | None
    method: str
    fields: list[RegistrationField]
    captcha_present: bool


def inspect_registration_form(html: str) -> RegistrationFormInspection:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("form[data-luma-registration-form], form.registration-form, form")
    if form is None:
        return RegistrationFormInspection(action=None, method="get", fields=[], captcha_present=False)

    fields: list[RegistrationField] = []
    for element in form.select("input[name], textarea[name], select[name]"):
        name = element.get("name", "")
        label_node = form.select_one(f"label[for='{element.get('id', '')}']")
        label = label_node.get_text(" ", strip=True) if label_node else element.get("aria-label") or name
        fields.append(
            RegistrationField(
                name=name,
                label=label,
                field_type=element.name if element.name != "input" else element.get("type", "text"),
                required=element.has_attr("required"),
            )
        )

    captcha_present = bool(form.select_one("[data-captcha], .g-recaptcha, iframe[src*='captcha']"))
    return RegistrationFormInspection(
        action=form.get("action"),
        method=form.get("method", "get").lower(),
        fields=fields,
        captcha_present=captcha_present,
    )


async def submit_registration(*_: Any, **__: Any) -> None:
    raise NotImplementedError("Registration submission is a primitive and is not invoked autonomously")


async def verify_registration(*_: Any, **__: Any) -> None:
    raise NotImplementedError("Registration verification is a primitive and is not invoked autonomously")

