"""Runtime HTTP server — wraps Playwright browser automation for the MCP server."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import httpx
from lumabot_runtime.enrichment.models import UserProfile
from lumabot_runtime.luma.enrichment import (
    VisibleGuestProvider,
    generate_report_from_luma_guest_html,
)
from lumabot_runtime.zero_provider import ZeroCapabilityClient
from playwright.async_api import Browser, Page, async_playwright
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

LUMA_SIGNIN_URL = "https://lu.ma/signin"
LUMA_HOME_URL = "https://lu.ma/home"
EMAIL_SELECTOR = "input[type='email'], input[name='email']"
CODE_SELECTOR = "input[autocomplete='one-time-code'], input[name='code'], input[inputmode='numeric']"
TIMEOUT_MS = 30_000
SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sessions")


@dataclass
class LoginAttempt:
    email: str
    page: Page


@dataclass
class RuntimeState:
    playwright: Any = None
    browser: Browser | None = None
    attempts: dict[str, LoginAttempt] = field(default_factory=dict)
    profile: dict[str, Any] | None = None
    reports: dict[str, dict[str, Any]] = field(default_factory=dict)
    report_jobs: dict[str, dict[str, Any]] = field(default_factory=dict)

    async def ensure_browser(self) -> Browser:
        if self.browser is None:
            self.playwright = await async_playwright().start()
            try:
                self.browser = await self.playwright.chromium.launch(
                    channel="chrome", headless=os.getenv("HEADLESS", "true").lower() != "false"
                )
            except Exception:
                self.browser = await self.playwright.chromium.launch(
                    headless=os.getenv("HEADLESS", "true").lower() != "false"
                )
        return self.browser

    async def shutdown(self) -> None:
        for attempt in self.attempts.values():
            try:
                await attempt.page.context.close()
            except Exception:
                pass
        self.attempts.clear()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


state = RuntimeState()


# ─── Session persistence ───────────────────────────────────────────────────────

async def save_session_to_db(email: str, session_data: dict[str, Any]) -> None:
    """Save session locally (and to Supabase if configured)."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    filepath = os.path.join(SESSIONS_DIR, f"{email.replace('@', '_at_')}.json")
    with open(filepath, "w") as f:
        json.dump(session_data, f, indent=2, default=str)
    logger.info("Session saved to %s", filepath)

    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{SUPABASE_URL}/rest/v1/luma_sessions",
                    headers={
                        "apikey": SUPABASE_SERVICE_ROLE_KEY,
                        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                        "Content-Type": "application/json",
                        "Prefer": "resolution=merge-duplicates",
                    },
                    json={
                        "email": email,
                        "session_data": json.dumps(session_data, default=str),
                        "authenticated": session_data.get("authenticated", False),
                    },
                )
                logger.info("Session also saved to Supabase for %s", email)
        except Exception as exc:
            logger.warning("Supabase save failed: %s", exc)


async def load_session_from_db(email: str) -> dict[str, Any] | None:
    """Load session from local file (or Supabase)."""
    filepath = os.path.join(SESSIONS_DIR, f"{email.replace('@', '_at_')}.json")
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)

    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{SUPABASE_URL}/rest/v1/luma_sessions",
                    headers={
                        "apikey": SUPABASE_SERVICE_ROLE_KEY,
                        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                    },
                    params={"email": f"eq.{email}", "select": "*", "limit": "1"},
                )
                if resp.status_code == 200:
                    rows = resp.json()
                    if rows:
                        return json.loads(rows[0]["session_data"])
        except Exception as exc:
            logger.warning("Supabase load failed: %s", exc)
    return None


# ─── Login handlers ────────────────────────────────────────────────────────────

def _redact_email(text: str, email: str) -> str:
    return text.replace(email, "[email]")


async def _collect_login_diagnostics(page: Page, *, email: str) -> dict[str, Any]:
    body_text = ""
    button_texts: list[str] = []
    inputs: list[dict[str, Any]] = []

    try:
        body_text = await page.locator("body").inner_text(timeout=3000)
    except Exception as exc:
        body_text = f"<failed to read body text: {exc}>"

    try:
        button_texts = [
            _redact_email(text.strip(), email)
            for text in await page.locator("button").all_text_contents()
            if text.strip()
        ]
    except Exception:
        button_texts = []

    try:
        inputs = await page.locator("input").evaluate_all(
            """nodes => nodes.map(input => ({
                type: input.getAttribute("type"),
                name: input.getAttribute("name"),
                autocomplete: input.getAttribute("autocomplete"),
                inputmode: input.getAttribute("inputmode"),
                placeholder: input.getAttribute("placeholder"),
                aria_label: input.getAttribute("aria-label"),
                visible: !!(input.offsetWidth || input.offsetHeight || input.getClientRects().length),
                has_value: !!input.value
            }))"""
        )
    except Exception:
        inputs = []

    normalized_text = body_text.lower()
    challenge_markers = [
        marker
        for marker in [
            "verifying your browser",
            "quick check of your browser",
            "keep luma safe",
            "captcha",
            "cloudflare",
            "turnstile",
            "challenge",
        ]
        if marker in normalized_text
    ]

    return {
        "url": page.url,
        "title": await page.title(),
        "button_texts": button_texts,
        "inputs": inputs,
        "challenge_markers": challenge_markers,
        "visible_text_excerpt": _redact_email(body_text, email)[:1200],
    }


async def _do_browser_login(attempt_id: str, email: str) -> dict[str, Any]:
    """Navigate to lu.ma, enter email, submit, and wait for the code screen."""
    context = None
    try:
        browser = await state.ensure_browser()
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT_MS)

        await page.goto(LUMA_SIGNIN_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        email_input = page.locator(EMAIL_SELECTOR).first
        await email_input.wait_for(state="visible")
        await email_input.fill(email)

        submit = page.get_by_role("button", name=re.compile(r"continue.*email|continue", re.I))
        try:
            await submit.click(timeout=5000)
        except Exception:
            submit = page.locator("button[type='submit']").first
            try:
                await submit.click(timeout=5000)
            except Exception:
                await page.keyboard.press("Enter")

        await page.locator(CODE_SELECTOR).first.wait_for(state="visible", timeout=15_000)
        logger.info("Login code screen reached for %s (attempt=%s)", email, attempt_id)
        state.attempts[attempt_id] = LoginAttempt(email=email, page=page)
        return {
            "ok": True,
            "attempt_id": attempt_id,
            "delivery": "email",
            "expires_in_seconds": 600,
            "submitted": True,
            "current_url": page.url,
        }
    except Exception as exc:
        current_url = None
        title = None
        diagnostics: dict[str, Any] | None = None
        try:
            if context is not None and context.pages:
                page = context.pages[-1]
                current_url = page.url
                title = await page.title()
                diagnostics = await _collect_login_diagnostics(page, email=email)
        except Exception:
            pass
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass
        logger.error(
            "Login submission failed for %s: %s diagnostics=%s",
            email,
            exc,
            json.dumps(diagnostics, default=str),
        )
        return {
            "ok": False,
            "attempt_id": attempt_id,
            "delivery": "email",
            "submitted": False,
            "error": str(exc),
            "current_url": current_url,
            "page_title": title,
            "diagnostics": diagnostics,
        }


async def _do_verify_and_save(attempt_id: str, code: str) -> None:
    """Background: enter code, save session to DB, close browser."""
    attempt = state.attempts.get(attempt_id)
    if attempt is None:
        logger.error("Verify: attempt %s not found", attempt_id)
        return

    page = attempt.page
    try:
        # Enter code
        code_input = page.locator(CODE_SELECTOR).first
        try:
            await code_input.wait_for(state="visible", timeout=5000)
            await code_input.fill(code)
        except Exception:
            inputs = page.locator("input[maxlength='1']")
            count = await inputs.count()
            if count >= 6:
                for i, digit in enumerate(code[:count]):
                    await inputs.nth(i).fill(digit)
            else:
                await page.locator("input:visible").first.fill(code)

        # Submit code
        try:
            btn = page.locator("button[type='submit']").first
            await btn.click(timeout=3000)
        except Exception:
            await page.keyboard.press("Enter")

        # Wait for redirect
        await page.wait_for_load_state("networkidle", timeout=15_000)
        current_url = page.url
        cookies = await page.context.cookies()
        luma_cookies = [c for c in cookies if "lu.ma" in c.get("domain", "") or "luma" in c.get("domain", "")]

        authenticated = len(luma_cookies) > 0 or "signin" not in current_url
        logger.info("Verify done for %s: url=%s cookies=%d auth=%s", attempt.email, current_url, len(luma_cookies), authenticated)

        # Save session
        session_data = {
            "email": attempt.email,
            "cookies": cookies,
            "url_after_login": current_url,
            "authenticated": authenticated,
        }
        await save_session_to_db(attempt.email, session_data)

    except Exception as exc:
        logger.error("Verify failed for %s: %s", attempt.email, exc)
    finally:
        del state.attempts[attempt_id]
        try:
            await page.context.close()
        except Exception:
            pass


async def handle_login_start(request: Request) -> JSONResponse:
    body = await request.json()
    email = body.get("email")
    if not email:
        return JSONResponse({"error": "email required"}, status_code=400)

    attempt_id = f"attempt-{uuid4().hex[:8]}"
    result = await _do_browser_login(attempt_id, email)
    return JSONResponse(result)


async def handle_login_verify(request: Request) -> JSONResponse:
    body = await request.json()
    attempt_id = body.get("attempt_id")
    code = body.get("code")

    if not attempt_id or not code:
        return JSONResponse({"error": "attempt_id and code required"}, status_code=400)

    # Wait for the browser page to be ready (up to 20s)
    for _ in range(20):
        if attempt_id in state.attempts:
            break
        await asyncio.sleep(1)
    else:
        return JSONResponse({"error": "attempt not found or browser still loading"}, status_code=404)

    # Fire and forget — enter code, save session, close browser in background
    asyncio.create_task(_do_verify_and_save(attempt_id, code))

    return JSONResponse({
        "user_id": f"user-{state.attempts[attempt_id].email.split('@')[0]}",
        "email": state.attempts[attempt_id].email,
        "session_expires_in_seconds": 3600,
        "status": "verifying",
        "message": "Code submitted. Session will be saved once verified.",
    })


async def handle_check_login(request: Request) -> JSONResponse:
    """Check if a saved session exists and is still valid by loading it into a browser."""
    body = await request.json()
    email = body.get("email")
    if not email:
        return JSONResponse({"error": "email required"}, status_code=400)

    session_data = await load_session_from_db(email)
    if session_data is None:
        return JSONResponse({
            "authenticated": False,
            "session_exists": False,
            "message": "No saved session found. Please login first.",
        })

    cookies = session_data.get("cookies", [])
    if not cookies:
        return JSONResponse({
            "authenticated": False,
            "session_exists": True,
            "message": "Session exists but has no cookies. Please re-login.",
        })

    # Validate session by loading cookies into a browser and hitting lu.ma
    browser = await state.ensure_browser()
    context = await browser.new_context()
    try:
        await context.add_cookies(cookies)
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT_MS)
        await page.goto(LUMA_HOME_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        current_url = page.url
        # If we're still on a home/dashboard page (not redirected to signin), session is valid
        is_valid = "signin" not in current_url and "sign-in" not in current_url

        logger.info("check_login for %s: url=%s valid=%s", email, current_url, is_valid)

        return JSONResponse({
            "authenticated": is_valid,
            "session_exists": True,
            "current_url": current_url,
            "message": "Session is valid." if is_valid else "Session expired. Please re-login.",
        })
    except Exception as exc:
        logger.error("check_login failed: %s", exc)
        return JSONResponse({
            "authenticated": False,
            "session_exists": True,
            "message": f"Session check failed: {exc}",
        })
    finally:
        await context.close()


# ─── Other handlers (fixture data) ────────────────────────────────────────────

async def handle_set_profile(request: Request) -> JSONResponse:
    body = await request.json()
    profile_text = body.get("profile_text", "")
    words = [w.strip("., ").lower() for w in profile_text.split() if len(w.strip("., ")) > 4]
    state.profile = {
        "profile_text": profile_text,
        "interests": sorted(set(words[:5])),
        "location": "San Francisco, CA",
    }
    return JSONResponse({"profile": state.profile})


async def handle_recommend_events(request: Request) -> JSONResponse:
    body = await request.json()
    events = [
        {
            "event_id": "evt-luma-ai-builders",
            "title": "AI Builders Night",
            "date": "2026-07-24",
            "location": body.get("location_override") or "San Francisco, CA",
            "score": 0.94,
            "top_attendee_match": "Maya Chen, developer relations lead",
            "matched_query": body.get("query"),
            "date_range": body.get("date_range"),
        },
        {
            "event_id": "evt-founder-salon",
            "title": "Founder Salon",
            "date": "2026-07-26",
            "location": body.get("location_override") or "Oakland, CA",
            "score": 0.83,
            "top_attendee_match": "Arjun Patel, early-stage founder",
            "matched_query": body.get("query"),
            "date_range": body.get("date_range"),
        },
    ]
    min_score = body.get("minimum_score") or 0.0
    limit = body.get("limit") or 5
    filtered = [e for e in events if e["score"] >= min_score][:limit]
    return JSONResponse({"events": filtered, "source": "stored_recommendations", "refresh_job_id": None})


async def handle_get_user_events(request: Request) -> JSONResponse:
    scope = request.query_params.get("scope", "all")
    limit = int(request.query_params.get("limit", "10"))
    events = [
        {"event_id": "evt-luma-ai-builders", "title": "AI Builders Night", "date": "2026-07-24", "score": 0.94},
        {"event_id": "evt-founder-salon", "title": "Founder Salon", "date": "2026-07-26", "score": 0.83},
    ][:limit]
    return JSONResponse({"scope": scope, "events": events, "next_cursor": None})


async def handle_get_event_report(request: Request) -> JSONResponse:
    event_id = request.path_params["event_id"]
    refresh = request.query_params.get("refresh", "false") == "true"
    if refresh:
        return await handle_create_report_job(request)
    report = state.reports.get(event_id)
    if report is not None:
        return JSONResponse({"report": report})
    return JSONResponse(
        {
            "report": {
                "event_id": event_id,
                "summary": "Cached report.",
                "top_attendee_match": "Maya Chen",
            }
        }
    )


async def handle_create_report_job(request: Request) -> JSONResponse:
    event_id = request.path_params["event_id"]
    job_id = f"job-report-{event_id}"
    body = await _request_json(request)
    event_url = body.get("event_url") or f"https://lu.ma/{event_id}"
    event_html = body.get("event_html")
    guest_html = body.get("guest_html")

    if event_html is None and guest_html is None and body.get("scrape") is True:
        scraped_html = await _scrape_luma_page_html(str(event_url), email=body.get("email"))
        event_html = scraped_html
        guest_html = scraped_html

    if isinstance(event_html, str) and isinstance(guest_html, str):
        result = await generate_report_from_luma_guest_html(
            user_profile=_user_profile_from_body(body),
            event_url=str(event_url),
            event_html=event_html,
            guest_html=guest_html,
            provider=_enrichment_provider(),
        )
        report = result.report.model_dump(mode="json")
        state.reports[event_id] = report
        state.report_jobs[job_id] = {
            "job_id": job_id,
            "status": "completed",
            "progress": 1.0,
            "result": {
                "event_id": event_id,
                "report": report,
                "visible_guest_count": result.visible_guest_count,
                "enriched_guest_count": result.enriched_guest_count,
                "warnings": result.warnings,
            },
            "error": None,
        }
        return JSONResponse({"job_id": job_id, "status": "queued"})

    state.report_jobs[job_id] = {
        "job_id": job_id, "status": "completed", "progress": 1.0,
        "result": {"event_id": event_id, "summary": "Report generated."},
        "error": None,
    }
    return JSONResponse({"job_id": job_id, "status": "queued"})


async def handle_get_job(request: Request) -> JSONResponse:
    job_id = request.path_params["job_id"]
    job = state.report_jobs.get(job_id, {"job_id": job_id, "status": "pending", "progress": 0.2, "result": None, "error": None})
    return JSONResponse({"job": job})


async def handle_confirm_action(request: Request) -> JSONResponse:
    action_id = request.path_params["action_id"]
    body = await request.json()
    return JSONResponse({"action_id": action_id, "status": "confirmed", "confirmation_token_used": bool(body.get("confirmation_token"))})


async def _request_json(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def _user_profile_from_body(body: dict[str, Any]) -> UserProfile:
    candidate = body.get("user_profile")
    if isinstance(candidate, dict):
        return UserProfile.model_validate(candidate)
    profile_text = body.get("profile_text")
    if not isinstance(profile_text, str) and state.profile is not None:
        profile_text = str(state.profile.get("profile_text", ""))
    words = [
        word.strip("., ").lower()
        for word in str(profile_text or "").split()
        if len(word.strip("., ")) > 4
    ]
    return UserProfile(
        goals=[str(profile_text)] if profile_text else [],
        target_roles=["founder", "engineering leader", "hiring manager"],
        industries=["ai", "developer tools"],
        company_stages=["seed"],
        company_sizes=["fewer than 50 employees"],
        event_types=["hackathon", "meetup"],
        region=state.profile.get("location") if state.profile else None,
        keywords=sorted(set(words[:10])),
    )


def _enrichment_provider() -> Any:
    if os.getenv("LUMABOT_ENRICHMENT_PROVIDER", "visible").lower() == "zero":
        return ZeroCapabilityClient(
            zero_bin=os.getenv("ZERO_BIN", "zero"),
            max_pay_usdc=os.getenv("ZERO_MAX_PAY_USDC", "0.25"),
            timeout_seconds=int(os.getenv("ZERO_TIMEOUT_SECONDS", "60")),
            pdl_min_likelihood=int(os.getenv("PDL_MIN_LIKELIHOOD", "1")),
        )
    return VisibleGuestProvider()


async def _scrape_luma_page_html(event_url: str, *, email: Any = None) -> str:
    browser = await state.ensure_browser()
    context = await browser.new_context()
    try:
        if isinstance(email, str):
            session_data = await load_session_from_db(email)
            cookies = session_data.get("cookies", []) if session_data else []
            if cookies:
                await context.add_cookies(cookies)
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT_MS)
        await page.goto(event_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        for selector in [
            "button:has-text('Guests')",
            "a:has-text('Guests')",
            "button:has-text('others')",
            "button:has-text('Going')",
            "[href*='guests']",
        ]:
            try:
                await page.locator(selector).first.click(timeout=1500)
                await page.wait_for_timeout(1500)
                break
            except Exception:
                continue
        for _ in range(5):
            await page.mouse.wheel(0, 1200)
            await page.wait_for_timeout(300)
        return await page.content()
    finally:
        await context.close()


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True, "status": "healthy"})


@asynccontextmanager
async def lifespan(app: Starlette):  # type: ignore[no-untyped-def]
    yield
    await state.shutdown()


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/login/start", handle_login_start, methods=["POST"]),
        Route("/login/verify", handle_login_verify, methods=["POST"]),
        Route("/login/check", handle_check_login, methods=["POST"]),
        Route("/profile", handle_set_profile, methods=["PUT"]),
        Route("/events/recommendations", handle_recommend_events, methods=["POST"]),
        Route("/users/events", handle_get_user_events, methods=["GET"]),
        Route("/events/{event_id}/report", handle_get_event_report, methods=["GET"]),
        Route("/events/{event_id}/report/jobs", handle_create_report_job, methods=["POST"]),
        Route("/jobs/{job_id}", handle_get_job, methods=["GET"]),
        Route("/actions/{action_id}/confirm", handle_confirm_action, methods=["POST"]),
    ],
    lifespan=lifespan,
)


def main() -> None:
    import uvicorn
    port = int(os.getenv("RUNTIME_PORT", "8080"))
    host = os.getenv("RUNTIME_HOST", "127.0.0.1")
    logger.info("Starting runtime server on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
