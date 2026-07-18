"""Cron job: scrape luma.com/sf, score interest with LLM, register for relevant events."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from openai import AsyncOpenAI
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

LUMA_SF_URL = "https://lu.ma/sf"
SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sessions")
EVENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "events")
PROFILE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles")
TIMEOUT_MS = 30_000

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"


def load_session_cookies(email: str) -> list[dict[str, Any]] | None:
    filepath = os.path.join(SESSIONS_DIR, f"{email.replace('@', '_at_')}.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath) as f:
        data = json.load(f)
    return data.get("cookies", [])


def load_user_profile(email: str) -> dict[str, Any] | None:
    """Load profile from local file (sync helper for cron context)."""
    filepath = os.path.join(PROFILE_DIR, f"{email.replace('@', '_at_')}.json")
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    return None


async def load_user_profile_async(email: str) -> dict[str, Any] | None:
    """Load profile from local file, falling back to database."""
    local = load_user_profile(email)
    if local:
        return local
    from lumabot_runtime.db import load_profile_from_db
    return await load_profile_from_db(email)


def save_user_profile(email: str, profile: dict[str, Any]) -> None:
    os.makedirs(PROFILE_DIR, exist_ok=True)
    filepath = os.path.join(PROFILE_DIR, f"{email.replace('@', '_at_')}.json")
    with open(filepath, "w") as f:
        json.dump(profile, f, indent=2)


async def score_events_with_llm(
    events: list[dict[str, Any]], profile: dict[str, Any]
) -> list[dict[str, Any]]:
    """Use OpenAI to score each event's relevance to the user's profile."""
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, skipping interest scoring")
        for e in events:
            e["interest_score"] = 0.5
            e["interest_reason"] = "No LLM scoring available"
        return events

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    profile_text = profile.get("profile_text", "")

    events_summary = "\n".join(
        f"{i+1}. {e.get('title', 'Untitled')} — {e.get('date', 'No date')} — {e.get('venue', 'No venue')} — {e.get('description', '')[:200]}"
        for i, e in enumerate(events)
    )

    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an event recommendation engine. Given a user profile and a list of events, "
                    "score each event from 0.0 to 1.0 based on how likely the user would want to attend. "
                    "Return a JSON array of objects with 'index' (1-based), 'score' (float 0-1), and 'reason' (short string)."
                ),
            },
            {
                "role": "user",
                "content": f"User profile: {profile_text}\n\nEvents:\n{events_summary}\n\nReturn JSON array only.",
            },
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )

    try:
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
        scores = result.get("scores", result.get("events", []))
        if isinstance(scores, list):
            for item in scores:
                idx = item.get("index", 0) - 1
                if 0 <= idx < len(events):
                    events[idx]["interest_score"] = item.get("score", 0.5)
                    events[idx]["interest_reason"] = item.get("reason", "")
    except Exception as exc:
        logger.error("Failed to parse LLM scoring response: %s", exc)
        for e in events:
            e.setdefault("interest_score", 0.5)

    return events


async def fill_form_with_llm(
    form_fields: list[dict[str, Any]], profile: dict[str, Any], event_title: str
) -> dict[str, str]:
    """Use OpenAI to fill registration form fields based on user profile."""
    if not OPENAI_API_KEY:
        return {}

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    profile_text = profile.get("profile_text", "")

    fields_desc = "\n".join(
        f"- {f.get('name', f.get('label', 'unknown'))}: label=\"{f.get('label', '')}\", type={f.get('type', 'text')}, required={f.get('required', False)}, placeholder=\"{f.get('placeholder', '')}\""
        for f in form_fields
    )

    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are filling out an event registration form on behalf of a user. "
                    "Based on their profile, generate appropriate values for each form field. "
                    "Return a JSON object mapping field name to the value to fill in. "
                    "Be concise and professional. For fields you can't determine, leave empty string."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Event: {event_title}\n\n"
                    f"User profile: {profile_text}\n\n"
                    f"Form fields:\n{fields_desc}\n\n"
                    f"Return JSON object only mapping field names to values."
                ),
            },
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    try:
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception as exc:
        logger.error("Failed to parse LLM form fill response: %s", exc)
        return {}


async def scrape_luma_sf(email: str) -> dict[str, Any]:
    """Scrape luma.com/sf using saved session, store events, return results."""
    cookies = load_session_cookies(email)
    if not cookies:
        return {"error": "No session found. Please login first.", "events": []}

    headless = os.getenv("HEADLESS", "true").lower() != "false"
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(channel="chrome", headless=headless)
        except Exception:
            browser = await pw.chromium.launch(headless=headless)

        context = await browser.new_context()
        await context.add_cookies(cookies)
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        try:
            logger.info("Navigating to %s", LUMA_SF_URL)
            await page.goto(LUMA_SF_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)

            # Luma uses virtualized rendering — events leave the DOM as you scroll past.
            # We must collect events incrementally while scrolling.
            all_events_map: dict[str, dict[str, Any]] = {}

            extract_js = """() => {
                const events = [];
                const cards = document.querySelectorAll('a.event-link.content-link');
                for (const card of cards) {
                    const href = card.getAttribute('href') || '';
                    if (!href) continue;

                    const title = card.getAttribute('aria-label') || 'Untitled';
                    const cardWrapper = card.closest('.card-wrapper') || card.closest('[role="button"]') || card.parentElement;
                    const timeEl = cardWrapper ? cardWrapper.querySelector('.event-time') : null;
                    const img = cardWrapper ? cardWrapper.querySelector('img[alt*="Cover"]') : null;
                    const bottomBar = cardWrapper ? cardWrapper.querySelector('.event-bottom-bar') : null;

                    // Organizer
                    const orgEl = cardWrapper ? cardWrapper.querySelector('.attr .text-ellipses .text-ellipses') : null;
                    const organizer = orgEl ? orgEl.innerText.trim() : null;

                    // Location (identified by the map-pin SVG path)
                    const attrs = cardWrapper ? cardWrapper.querySelectorAll('.attr') : [];
                    let venue = null;
                    for (const attr of attrs) {
                        const svg = attr.querySelector('svg');
                        if (svg && svg.innerHTML.includes('M2 6.854')) {
                            const textEl = attr.querySelector('.text-ellipses');
                            if (textEl) venue = textEl.innerText.trim();
                        }
                    }

                    // Status pill
                    const pillEl = bottomBar ? bottomBar.querySelector('.pill-label') : null;
                    const status = pillEl ? pillEl.innerText.trim() : null;

                    // Attendee count
                    const remainingEl = bottomBar ? bottomBar.querySelector('.remaining-count') : null;
                    const attendees = remainingEl ? remainingEl.innerText.trim() : null;

                    // LIVE badge
                    const liveEl = cardWrapper ? cardWrapper.querySelector('.live-badge') : null;

                    events.push({
                        title: title,
                        url: href.startsWith('http') ? href : 'https://lu.ma' + href,
                        date: timeEl ? timeEl.innerText.trim().replace('LIVE', '').trim() : null,
                        venue: venue,
                        organizer: organizer,
                        image_url: img ? img.src : null,
                        status: status,
                        attendees: attendees,
                        is_live: !!liveEl,
                    });
                }
                return events;
            }"""

            # Collect initial events
            batch = await page.evaluate(extract_js)
            for e in batch:
                all_events_map[e["url"]] = e

            # Scroll incrementally and collect as we go
            stable_rounds = 0
            prev_total = len(all_events_map)
            for _ in range(30):
                await page.evaluate("window.scrollBy(0, 800)")
                await page.wait_for_timeout(1500)
                batch = await page.evaluate(extract_js)
                for e in batch:
                    all_events_map[e["url"]] = e

                if len(all_events_map) == prev_total:
                    stable_rounds += 1
                    if stable_rounds >= 5:
                        break
                else:
                    stable_rounds = 0
                prev_total = len(all_events_map)

            events = list(all_events_map.values())

            logger.info("Found %d events on %s", len(events), LUMA_SF_URL)

            # Score events against user profile
            profile = await load_user_profile_async(email)
            if profile:
                events = await score_events_with_llm(events, profile)

            # Save events locally
            os.makedirs(EVENTS_DIR, exist_ok=True)
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(EVENTS_DIR, f"sf_events_{timestamp}.json")
            payload = {
                "scraped_at": datetime.now(UTC).isoformat(),
                "source_url": LUMA_SF_URL,
                "event_count": len(events),
                "events": events,
            }
            with open(filepath, "w") as f:
                json.dump(payload, f, indent=2)

            latest_path = os.path.join(EVENTS_DIR, "sf_events_latest.json")
            with open(latest_path, "w") as f:
                json.dump(payload, f, indent=2)

            # Save events to database
            from lumabot_runtime.db import save_events_to_db
            await save_events_to_db(events)

            return payload

        finally:
            await context.close()
            await browser.close()


async def _get_page_state(page: Any) -> dict[str, Any]:
    """Extract current page state: visible buttons, inputs, and text context."""
    return await page.evaluate("""() => {
        const state = {};
        // Visible buttons
        state.buttons = [];
        document.querySelectorAll('button, a[role="button"]').forEach(el => {
            if (el.offsetParent !== null && el.innerText.trim()) {
                state.buttons.push({
                    text: el.innerText.trim().slice(0, 80),
                    type: el.type || '',
                    disabled: el.disabled,
                    classes: el.className.slice(0, 100),
                });
            }
        });
        // Visible inputs (including dropdowns, checkboxes, radio buttons)
        state.inputs = [];
        document.querySelectorAll('input, textarea, select').forEach(el => {
            if (el.offsetParent !== null || (el.type === 'hidden' && el.name)) {
                const label = el.closest('label') || document.querySelector('label[for="' + el.id + '"]');
                const parentText = el.parentElement ? el.parentElement.innerText.trim().slice(0, 100) : '';
                const entry = {
                    name: el.name || el.id || '',
                    type: el.tagName === 'SELECT' ? 'select' : (el.type || 'text'),
                    placeholder: el.placeholder || '',
                    label: label ? label.textContent.trim().slice(0, 100) : parentText,
                    value: el.value || '',
                    required: el.required,
                    checked: el.checked || false,
                };
                // For select elements, capture available options
                if (el.tagName === 'SELECT') {
                    entry.options = Array.from(el.options).map(o => ({value: o.value, text: o.text.trim()}));
                }
                state.inputs.push(entry);
            }
        });
        // Also capture custom dropdown-like elements (Luma uses custom selects)
        document.querySelectorAll('[role="listbox"], [role="combobox"], [class*="select"], [class*="dropdown"]').forEach(el => {
            if (el.offsetParent !== null && !el.matches('select')) {
                const label = el.getAttribute('aria-label') || el.closest('label')?.textContent?.trim() || '';
                state.inputs.push({
                    name: el.id || el.getAttribute('data-name') || 'custom-select',
                    type: 'custom-select',
                    label: label.slice(0, 100),
                    value: el.innerText.trim().slice(0, 50),
                    options_text: el.innerText.trim().slice(0, 200),
                });
            }
        });
        // Page context text (trimmed)
        const dialog = document.querySelector('[role="dialog"], [class*="modal"], [class*="drawer"]');
        const target = dialog || document.body;
        state.context_text = target.innerText.trim().slice(0, 1500);
        // Check for captcha
        state.has_captcha = !!document.querySelector('[data-captcha], .g-recaptcha, iframe[src*="captcha"]');
        // Check for success indicators (must be confirmation, not CTA)
        const text = document.body.innerText.toLowerCase();
        state.is_success = text.includes("you're registered") || text.includes('successfully registered') ||
                          text.includes("you're in") || text.includes('see you there') ||
                          text.includes('your spot is confirmed') || (text.includes('registered') && text.includes('going')) ||
                          text.includes('requested to join') || text.includes('your request has been') ||
                          text.includes('on waiting list') || text.includes('pending approval');
        // Also check URL for ticket token which confirms registration
        if (location.search.includes('tk=')) state.is_success = true;
        // Check for payment requirement
        const hasPayButton = !!document.querySelector('button:not([disabled])');
        const buttonTexts = Array.from(document.querySelectorAll('button')).map(b => b.innerText.toLowerCase());
        state.needs_payment = buttonTexts.some(t => t.includes('pay with card') || t.includes('pay now')) ||
                             (text.includes('ticket price') && text.includes('us$'));
        // Check for browser verification
        state.verifying_browser = text.includes('verifying your browser') || text.includes('checking your browser');
        state.url = location.href;
        return state;
    }""")


async def _llm_decide_action(page_state: dict[str, Any], profile: dict[str, Any], event_title: str, history: list[str]) -> dict[str, Any]:
    """Use LLM to decide next action based on current page state."""
    if not OPENAI_API_KEY:
        return {"action": "error", "reason": "No OpenAI API key"}

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    profile_text = json.dumps(profile, indent=2)

    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an automation agent registering for an event. Given the page state, "
                    "decide the SINGLE next action. Return JSON with:\n"
                    "- action: 'fill_and_submit' | 'click_button' | 'done' | 'error'\n"
                    "- For fill_and_submit: include 'values' dict mapping input name to value, "
                    "  'checkboxes' (list of input names to check), 'selects' (dict of name to option value), "
                    "  and 'submit_button' (text of button to click after filling)\n"
                    "- For click_button: include 'button_text' (exact text to match)\n"
                    "- For done: include 'success' (bool) and 'message'\n"
                    "- For error: include 'reason'\n\n"
                    "CRITICAL RULES:\n"
                    "- If you already filled fields in previous steps, you MUST now click submit. "
                    "  Look at 'Actions taken so far' — if it has 'filled:' entries, next action should be "
                    "  click_button with the submit/register/join button.\n"
                    "- If registration is already confirmed (is_success=true), return done+success\n"
                    "- If payment is required (needs_payment=true), return error 'payment_required'\n"
                    "- Fill forms with REALISTIC professional info based on user profile\n"
                    "- For phone: use +14155550199\n"
                    "- For LinkedIn: use the linkedin from profile\n"
                    "- For questions about interests/goals/what you're building, write 1-2 natural sentences\n"
                    "- For 'how did you hear about this': say 'Through the SF tech community on Luma'\n"
                    "- For company/role: infer from profile text\n"
                    "- Skip hidden inputs (name starting with _ or type hidden)\n"
                    "- For select/dropdown elements, pick the most appropriate option from available options\n"
                    "- For checkboxes related to terms/agreement, check them\n"
                    "- Never click 'Pay with Card' or payment buttons\n"
                    "- Prefer 'Join Waiting List', 'Register', 'Submit', 'RSVP' as submit buttons"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Event: {event_title}\n\n"
                    f"User Profile:\n{profile_text}\n\n"
                    f"Page State:\n{json.dumps(page_state, indent=2)}\n\n"
                    f"Actions taken so far: {history}\n\n"
                    f"What is the single next action?"
                ),
            },
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    try:
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception:
        return {"action": "error", "reason": "Failed to parse LLM response"}


async def inspect_event_registration(email: str, event_url: str) -> dict[str, Any]:
    """Navigate to event, adaptively find and inspect the registration form."""
    cookies = load_session_cookies(email)
    if not cookies:
        return {"error": "No session found. Please login first."}

    headless = os.getenv("HEADLESS", "true").lower() != "false"
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(channel="chrome", headless=headless)
        except Exception:
            browser = await pw.chromium.launch(headless=headless)

        context = await browser.new_context()
        await context.add_cookies(cookies)
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        try:
            await page.goto(event_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)

            # Click the primary registration button
            btn_selectors = [
                "button:has-text('Register')", "button:has-text('Join')",
                "button:has-text('RSVP')", "button:has-text('Get Ticket')",
                "button:has-text('Get Tickets')", "button:has-text('Attend')",
                "a:has-text('Register')", "a:has-text('Join')",
            ]
            clicked = False
            for sel in btn_selectors:
                try:
                    btn = page.locator(sel).first
                    if await btn.is_visible():
                        await btn.click(force=True)
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                return {"event_url": event_url, "error": "No registration button found"}

            await page.wait_for_timeout(4000)
            page_state = await _get_page_state(page)

            return {
                "event_url": event_url,
                "page_state": page_state,
                "form_fields": page_state.get("inputs", []),
                "has_captcha": page_state.get("has_captcha", False),
                "needs_payment": page_state.get("needs_payment", False),
                "buttons_available": [b["text"] for b in page_state.get("buttons", [])],
            }

        finally:
            await context.close()
            await browser.close()


async def submit_event_registration(
    email: str, event_url: str, form_data: dict[str, str] | None = None
) -> dict[str, Any]:
    """Agentic registration: adaptively navigate, fill forms, and submit."""
    cookies = load_session_cookies(email)
    if not cookies:
        return {"error": "No session found. Please login first."}

    profile = await load_user_profile_async(email) or {
        "profile_text": "Software engineer in San Francisco",
        "name": "User",
        "email": email,
    }

    headless = os.getenv("HEADLESS", "true").lower() != "false"
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(channel="chrome", headless=headless)
        except Exception:
            browser = await pw.chromium.launch(headless=headless)

        context = await browser.new_context()
        await context.add_cookies(cookies)
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        try:
            await page.goto(event_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)

            # Get event title from page
            event_title = await page.evaluate(
                "() => document.querySelector('h1, [class*=\"title\"]')?.innerText?.trim() || 'Event'"
            )

            history: list[str] = []
            max_steps = 8

            for step in range(max_steps):
                page_state = await _get_page_state(page)

                # Wait through browser verification (up to 15s)
                if page_state.get("verifying_browser"):
                    for _ in range(5):
                        await page.wait_for_timeout(3000)
                        page_state = await _get_page_state(page)
                        if not page_state.get("verifying_browser"):
                            break
                    if page_state.get("verifying_browser"):
                        return {
                            "event_url": event_url,
                            "submitted": False,
                            "error": "Browser verification did not complete",
                            "steps_taken": history,
                        }

                # Check if already done
                if page_state.get("is_success"):
                    return {
                        "event_url": event_url,
                        "submitted": True,
                        "success": True,
                        "current_url": page_state["url"],
                        "steps_taken": history,
                    }

                # If form_data was provided directly and we haven't used it yet
                if form_data and step == 0:
                    # Click primary button first
                    for sel in ["button:has-text('Register')", "button:has-text('Join')",
                                "button:has-text('RSVP')", "button:has-text('Get Ticket')",
                                "button:has-text('Get Tickets')"]:
                        try:
                            btn = page.locator(sel).first
                            if await btn.is_visible():
                                await btn.click(force=True)
                                history.append(f"clicked: {sel}")
                                await page.wait_for_timeout(3000)
                                break
                        except Exception:
                            continue
                    continue

                # Ask LLM what to do
                decision = await _llm_decide_action(page_state, profile, event_title, history)
                action = decision.get("action", "error")

                if action == "done":
                    return {
                        "event_url": event_url,
                        "submitted": True,
                        "success": decision.get("success", False),
                        "message": decision.get("message", ""),
                        "current_url": page_state["url"],
                        "steps_taken": history,
                    }

                if action == "error":
                    reason = decision.get("reason", "Unknown error")
                    if "payment" in reason.lower():
                        return {
                            "event_url": event_url,
                            "submitted": False,
                            "error": "Payment required — cannot auto-register for paid events",
                            "needs_payment": True,
                            "steps_taken": history,
                        }
                    return {
                        "event_url": event_url,
                        "submitted": False,
                        "error": reason,
                        "steps_taken": history,
                    }

                if action == "fill_and_submit":
                    values = decision.get("values", {})
                    checkboxes = decision.get("checkboxes", [])
                    selects = decision.get("selects", {})
                    submit_button = decision.get("submit_button", "")

                    # Fill text inputs
                    for field_key, value in values.items():
                        if not value or field_key.startswith("_"):
                            continue
                        try:
                            # Try by name
                            el = page.locator(f"input[name='{field_key}'], textarea[name='{field_key}']").first
                            if not await el.is_visible():
                                # Try by id
                                el = page.locator(f"#{field_key}").first
                            if not await el.is_visible():
                                el = page.locator(f"input[placeholder*='{field_key}'], textarea[placeholder*='{field_key}']").first
                            await el.fill(str(value))
                            history.append(f"filled: {field_key}={str(value)[:30]}")
                        except Exception:
                            logger.warning("Could not fill field: %s", field_key)
                    await page.wait_for_timeout(500)

                    # Handle Luma custom dropdowns (click to open, then click option)
                    for sel_name, sel_value in selects.items():
                        try:
                            # Luma uses a clickable wrapper with an input inside
                            dropdown_input = page.locator(f"input[name='{sel_name}'], input#{sel_name}").first
                            if not await dropdown_input.is_visible():
                                dropdown_input = page.locator(f"input[placeholder='Select an option']").first

                            # Click the dropdown wrapper to open it
                            wrapper = page.locator(f"input[name='{sel_name}'], input#{sel_name}").first.locator("..")
                            await dropdown_input.click()
                            await page.wait_for_timeout(1000)

                            # Click the option from the dropdown menu
                            option = page.locator(f"[role='option']:has-text('{sel_value}'), [class*='menu-item']:has-text('{sel_value}'), [class*='option']:has-text('{sel_value}')").first
                            if await option.is_visible():
                                await option.click()
                                history.append(f"selected: {sel_name}={sel_value}")
                            else:
                                # Try clicking any visible menu item that contains the text
                                option = page.get_by_text(sel_value, exact=False).first
                                await option.click()
                                history.append(f"selected: {sel_name}={sel_value}")
                            await page.wait_for_timeout(500)
                        except Exception as exc:
                            logger.warning("Could not select dropdown %s: %s", sel_name, exc)
                            history.append(f"select_failed: {sel_name}")

                    # Check checkboxes (Luma wraps them in label > span > input)
                    for cb_label_text in checkboxes:
                        try:
                            # Try clicking the label that contains the checkbox
                            label = page.locator(f"label:has-text('{cb_label_text}')").first
                            if await label.is_visible():
                                await label.click()
                                history.append(f"checked: {cb_label_text[:30]}")
                            else:
                                # Fallback: find checkbox input inside .lux-checkbox
                                cb = page.locator(".lux-checkbox input[type='checkbox']").first
                                await cb.check(force=True)
                                history.append(f"checked: checkbox (force)")
                        except Exception as exc:
                            # Last resort: click the checkbox-display span
                            try:
                                cb_display = page.locator(".checkbox-display, .checkbox-icon").first
                                await cb_display.click()
                                history.append(f"checked: via display click")
                            except Exception:
                                logger.warning("Could not check: %s", cb_label_text)
                                history.append(f"check_failed: {cb_label_text[:30]}")

                    await page.wait_for_timeout(1000)

                    # Click submit button — prefer the one inside the form/overlay
                    if submit_button:
                        try:
                            # First try type=submit inside the overlay form
                            form_submit = page.locator("form button[type='submit'], .lux-overlay button[type='submit'], .registration-overlay button[type='submit']").first
                            if await form_submit.is_visible():
                                await form_submit.click(force=True)
                                history.append(f"submitted: form submit")
                            else:
                                btn = page.locator(f"button:has-text('{submit_button}')").last
                                await btn.click(force=True)
                                history.append(f"submitted: {submit_button}")
                            await page.wait_for_timeout(5000)
                        except Exception as exc:
                            history.append(f"submit_failed: {submit_button} ({exc})")

                elif action == "fill_inputs":
                    values = decision.get("values", {})
                    for field_key, value in values.items():
                        if not value or field_key.startswith("_"):
                            continue
                        try:
                            el = page.locator(f"input[name='{field_key}'], textarea[name='{field_key}']").first
                            if not await el.is_visible():
                                el = page.locator(f"input[placeholder*='{field_key}'], textarea[placeholder*='{field_key}']").first
                            await el.fill(str(value))
                            history.append(f"filled: {field_key}={str(value)[:30]}")
                        except Exception:
                            logger.warning("Could not fill field: %s", field_key)
                    await page.wait_for_timeout(1000)

                elif action == "click_button":
                    button_text = decision.get("button_text", "")
                    try:
                        # If overlay is open, prefer the submit button inside it
                        overlay_open = await page.evaluate("() => !!document.querySelector('.lux-overlay, .registration-overlay')")
                        if overlay_open and button_text.lower() in ("request to join", "register", "join waiting list", "submit", "rsvp"):
                            form_btn = page.locator("form button[type='submit'], .lux-overlay button[type='submit']").first
                            if await form_btn.is_visible():
                                await form_btn.click(force=True)
                                history.append(f"clicked: form submit ({button_text})")
                                await page.wait_for_timeout(4000)
                                continue
                        btn = page.locator(f"button:has-text('{button_text}')").first
                        await btn.click(force=True)
                        history.append(f"clicked: {button_text}")
                        await page.wait_for_timeout(4000)
                    except Exception as exc:
                        history.append(f"failed_click: {button_text} ({exc})")

            # Exhausted steps
            final_state = await _get_page_state(page)
            return {
                "event_url": event_url,
                "submitted": False,
                "error": "Exhausted max steps without completing registration",
                "steps_taken": history,
                "final_state_summary": {
                    "url": final_state["url"],
                    "is_success": final_state.get("is_success", False),
                    "needs_payment": final_state.get("needs_payment", False),
                },
            }

        except Exception as exc:
            return {"event_url": event_url, "submitted": False, "error": str(exc)}
        finally:
            await context.close()
            await browser.close()


async def run_cron(email: str) -> dict[str, Any]:
    """Full cron: scrape events, score interest, return results."""
    logger.info("Cron job starting for %s", email)
    result = await scrape_luma_sf(email)
    logger.info("Cron job complete: %d events found", result.get("event_count", 0))
    return result


def main() -> None:
    """Run the cron job directly from CLI."""
    import sys
    email = sys.argv[1] if len(sys.argv) > 1 else "vaibhavblogger@gmail.com"
    logging.basicConfig(level="INFO")
    result = asyncio.run(run_cron(email))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
