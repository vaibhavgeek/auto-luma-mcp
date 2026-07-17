from __future__ import annotations

from typing import Any
from uuid import UUID, uuid5

from bs4 import BeautifulSoup, Tag

from .models import DiscoveredEvent, LumaEvent, LumaPerson
from .urls import canonicalize_luma_url

LUMA_NAMESPACE = UUID("0c112d52-a5c7-4ee3-9826-a7f1de7fd0cb")

SELECTORS = {
    "login_email": "input[name='email'], input[type='email']",
    "login_code": "input[name='code'], input[autocomplete='one-time-code']",
    "dashboard": "[data-testid='dashboard'], main",
    "event_card": "[data-luma-event-card], article.event-card",
    "event_title": "[data-luma-event-title], h1, h2.event-title",
    "event_date": "time[datetime], [data-luma-event-date]",
    "event_venue": "[data-luma-event-venue], .venue",
    "event_description": "[data-luma-event-description], .description",
    "event_image": "img[data-luma-event-image], meta[property='og:image']",
    "event_organizer": "[data-luma-organizer], .organizer",
    "registration_state": "[data-luma-registration-state], [data-registration-state]",
    "guest": "[data-luma-guest], .guest-card",
    "guest_name": "[data-luma-guest-name], .guest-name",
    "guest_profile": "a[data-luma-profile], a.profile-link",
    "guest_social": "a[data-social], a[href*='twitter.com'], a[href*='linkedin.com'], a[href*='github.com']",
    "guest_image": "img[data-luma-guest-image], img.avatar",
    "guest_title": "[data-luma-guest-title], .guest-title",
    "guest_company": "[data-luma-guest-company], .guest-company",
    "guest_location": "[data-luma-guest-location], .guest-location",
    "guest_bio": "[data-luma-guest-bio], .guest-bio",
}


def _text(node: Tag | None) -> str | None:
    if node is None:
        return None
    value = node.get_text(" ", strip=True)
    return value or None


def _attr(node: Tag | None, name: str) -> str | None:
    if node is None:
        return None
    value = node.get(name)
    if isinstance(value, str) and value:
        return value
    return None


def event_id_for_url(url: str) -> UUID:
    return uuid5(LUMA_NAMESPACE, f"event:{canonicalize_luma_url(url)}")


def person_id_for_visible_identity(full_name: str, profile_url: str | None) -> UUID:
    key = profile_url or full_name.strip().lower()
    return uuid5(LUMA_NAMESPACE, f"person:{key}")


def extract_discovered_events(html: str, source_url: str) -> list[DiscoveredEvent]:
    soup = BeautifulSoup(html, "html.parser")
    events: list[DiscoveredEvent] = []
    for card in soup.select(SELECTORS["event_card"]):
        href = _attr(card if card.name == "a" else card.select_one("a[href]"), "href")
        if not href:
            continue
        url = canonicalize_luma_url(href, source_url)
        title = _text(card.select_one(SELECTORS["event_title"])) or _attr(card, "aria-label") or "Untitled Luma event"
        date_node = card.select_one(SELECTORS["event_date"])
        starts_at = _attr(date_node, "datetime") or _text(date_node)
        venue = _text(card.select_one(SELECTORS["event_venue"]))
        events.append(
            DiscoveredEvent(
                url=url,
                title=title,
                starts_at=starts_at,
                venue=venue,
                evidence={"source_url": source_url, "selector": SELECTORS["event_card"], "text": card.get_text(" ", strip=True)},
            )
        )
    return events


def extract_event_details(html: str, event_url: str) -> LumaEvent:
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup.select_one(SELECTORS["event_title"])) or "Untitled Luma event"
    date_node = soup.select_one(SELECTORS["event_date"])
    image_node = soup.select_one(SELECTORS["event_image"])
    registration_node = soup.select_one(SELECTORS["registration_state"])
    registration_state = (
        _attr(registration_node, "data-registration-state")
        or _attr(registration_node, "data-luma-registration-state")
        or _text(registration_node)
    )
    return LumaEvent(
        event_id=event_id_for_url(event_url),
        url=canonicalize_luma_url(event_url),
        title=title,
        description=_text(soup.select_one(SELECTORS["event_description"])),
        starts_at=_attr(date_node, "datetime") or _text(date_node),
        ends_at=_attr(date_node, "data-ends-at"),
        venue=_text(soup.select_one(SELECTORS["event_venue"])),
        image_url=_attr(image_node, "src") or _attr(image_node, "content"),
        organizer=_text(soup.select_one(SELECTORS["event_organizer"])),
        registration_state=registration_state,
        metadata={"source_selector": SELECTORS["event_title"]},
    )


def extract_visible_guests(html: str) -> list[tuple[LumaPerson, dict[str, Any]]]:
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("[data-luma-guests-inaccessible]"):
        return []

    guests: list[tuple[LumaPerson, dict[str, Any]]] = []
    for card in soup.select(SELECTORS["guest"]):
        full_name = _text(card.select_one(SELECTORS["guest_name"]))
        if not full_name:
            continue
        profile_node = card.select_one(SELECTORS["guest_profile"])
        profile_url = _attr(profile_node, "href")
        social_links = [href for link in card.select(SELECTORS["guest_social"]) if (href := _attr(link, "href"))]
        image_url = _attr(card.select_one(SELECTORS["guest_image"]), "src")
        person = LumaPerson(
            person_id=person_id_for_visible_identity(full_name, profile_url),
            full_name=full_name,
            profile_url=profile_url,
            image_url=image_url,
            social_links=sorted(set(social_links)),
            identity_confidence=0.75 if profile_url else 0.55,
            title=_text(card.select_one(SELECTORS["guest_title"])),
            company=_text(card.select_one(SELECTORS["guest_company"])),
            location=_text(card.select_one(SELECTORS["guest_location"])),
            bio=_text(card.select_one(SELECTORS["guest_bio"])),
        )
        guests.append(
            (
                person,
                {
                    "attendee_status": card.get("data-attendee-status", "visible"),
                    "organizer_status": card.get("data-organizer-status", "attendee"),
                    "source_selector": SELECTORS["guest"],
                },
            )
        )
    return guests
