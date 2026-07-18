from __future__ import annotations

import contextlib
import logging
from typing import Annotated

import uvicorn
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from lumabot_mcp.context import configure_logging, log_tool_call
from lumabot_mcp.models import ToolResponse
from lumabot_mcp.runtime_client import FakeRuntimeClient, HttpRuntimeClient, RuntimeClient
from lumabot_mcp.settings import Settings
from lumabot_mcp.tools.actions import handle_confirm_action
from lumabot_mcp.tools.check_login import handle_check_login
from lumabot_mcp.tools.events import handle_get_user_events, handle_recommend_events
from lumabot_mcp.tools.jobs import handle_get_job_status
from lumabot_mcp.tools.login import handle_login
from lumabot_mcp.tools.profile import handle_set_user_profile
from lumabot_mcp.tools.reports import handle_get_event_report

logger = logging.getLogger(__name__)


def create_runtime_client(settings: Settings) -> RuntimeClient:
    return HttpRuntimeClient(
        settings.runtime_url,
        bearer_token=settings.runtime_bearer_token,
        timeout_seconds=settings.request_timeout_seconds,
    )


def create_mcp_server(runtime: RuntimeClient | None = None) -> FastMCP:
    settings = Settings.from_env()
    runtime_client = runtime or create_runtime_client(settings)
    mcp = FastMCP(
        "LumaBot",
        json_response=True,
        stateless_http=True,
        transport_security=settings.transport_security_settings(),
    )

    @mcp.tool()
    async def login(
        email: Annotated[
            str | None,
            Field(description="Email address for the Luma account."),
        ] = None,
        attempt_id: Annotated[
            str | None,
            Field(description="Login attempt identifier returned after starting login."),
        ] = None,
        code: Annotated[
            str | None,
            Field(description="One-time login code. This value is never logged."),
        ] = None,
    ) -> ToolResponse:
        """Start or verify passwordless Luma login."""
        log_tool_call(
            logger,
            "login",
            {"email": email, "attempt_id": attempt_id, "code": code},
        )
        return await handle_login(
            runtime_client,
            email=email,
            attempt_id=attempt_id,
            code=code,
        )

    @mcp.tool()
    async def check_login(
        email: Annotated[
            str,
            Field(description="Email address to check for an existing valid Luma session."),
        ],
    ) -> ToolResponse:
        """Check if a saved Luma session exists and is still valid."""
        log_tool_call(logger, "check_login", {"email": email})
        return await handle_check_login(runtime_client, email=email)

    @mcp.tool()
    async def set_user_profile(
        profile_text: Annotated[
            str,
            Field(description="Free-form user description to parse into a profile."),
        ],
    ) -> ToolResponse:
        """Save and parse the user's event preference profile."""
        log_tool_call(logger, "set_user_profile", {"profile_text": profile_text})
        return await handle_set_user_profile(runtime_client, profile_text=profile_text)

    @mcp.tool()
    async def recommend_events(
        query: Annotated[
            str | None,
            Field(description="Natural-language event recommendation query."),
        ] = None,
        date_range: Annotated[
            str | None,
            Field(description="Natural-language or ISO date range filter."),
        ] = None,
        minimum_score: Annotated[
            float | None,
            Field(description="Minimum stored recommendation score."),
        ] = None,
        limit: Annotated[
            int,
            Field(description="Maximum number of events to return", ge=1, le=50),
        ] = 5,
        location_override: Annotated[
            str | None,
            Field(description="Override location for runtime-side recommendation lookup."),
        ] = None,
    ) -> ToolResponse:
        """Return stored recommendations or enqueue runtime refresh work."""
        log_tool_call(
            logger,
            "recommend_events",
            {
                "query": query,
                "date_range": date_range,
                "minimum_score": minimum_score,
                "limit": limit,
                "location_override": location_override,
            },
        )
        return await handle_recommend_events(
            runtime_client,
            query=query,
            date_range=date_range,
            minimum_score=minimum_score,
            limit=limit,
            location_override=location_override,
        )

    @mcp.tool()
    async def get_user_events(
        scope: Annotated[
            str,
            Field(description="Event scope: all, attended, registered, or recommended."),
        ] = "all",
        query: Annotated[str | None, Field(description="Optional text filter.")] = None,
        limit: Annotated[
            int,
            Field(description="Maximum number of events to return", ge=1, le=50),
        ] = 10,
        cursor: Annotated[
            str | None,
            Field(description="Pagination cursor from prior call."),
        ] = None,
    ) -> ToolResponse:
        """Return stored user events delegated by scope."""
        log_tool_call(
            logger,
            "get_user_events",
            {"scope": scope, "query": query, "limit": limit, "cursor": cursor},
        )
        return await handle_get_user_events(
            runtime_client,
            scope=scope,
            query=query,
            limit=limit,
            cursor=cursor,
        )

    @mcp.tool()
    async def get_event_report(
        event_id: Annotated[str, Field(description="Runtime event identifier.")],
        refresh: Annotated[
            bool,
            Field(description="Queue a fresh runtime report instead of using existing report."),
        ] = False,
        event_url: Annotated[
            str | None,
            Field(description="Luma event URL to scrape when refreshing the report."),
        ] = None,
        event_html: Annotated[
            str | None,
            Field(description="Rendered Luma event HTML for deterministic report refresh."),
        ] = None,
        guest_html: Annotated[
            str | None,
            Field(description="Rendered Luma guest-list HTML for deterministic report refresh."),
        ] = None,
        profile_text: Annotated[
            str | None,
            Field(description="Optional user profile text for attendee scoring."),
        ] = None,
        scrape: Annotated[
            bool,
            Field(description="Scrape event_url with the runtime browser before refreshing."),
        ] = False,
        email: Annotated[
            str | None,
            Field(description="Luma account email whose saved session should be used for scraping."),
        ] = None,
    ) -> ToolResponse:
        """Return an existing event report or a queued report job identifier."""
        log_tool_call(
            logger,
            "get_event_report",
            {
                "event_id": event_id,
                "refresh": refresh,
                "event_url": event_url,
                "event_html": bool(event_html),
                "guest_html": bool(guest_html),
                "profile_text": profile_text,
                "scrape": scrape,
                "email": email,
            },
        )
        return await handle_get_event_report(
            runtime_client,
            event_id=event_id,
            refresh=refresh,
            event_url=event_url,
            event_html=event_html,
            guest_html=guest_html,
            profile_text=profile_text,
            scrape=scrape,
            email=email,
        )

    @mcp.tool()
    async def get_job_status(
        job_id: Annotated[str, Field(description="Runtime job identifier.")],
    ) -> ToolResponse:
        """Return current runtime job status, progress, result, and safe error."""
        log_tool_call(logger, "get_job_status", {"job_id": job_id})
        return await handle_get_job_status(runtime_client, job_id=job_id)

    @mcp.tool()
    async def confirm_action(
        action_id: Annotated[
            str,
            Field(description="Pending runtime action identifier to confirm."),
        ],
        confirmation_token: Annotated[
            str | None,
            Field(description="Optional confirmation token. This value is never logged."),
        ] = None,
    ) -> ToolResponse:
        """Confirm an existing pending sensitive action."""
        log_tool_call(
            logger,
            "confirm_action",
            {"action_id": action_id, "confirmation_token": confirmation_token},
        )
        return await handle_confirm_action(
            runtime_client,
            action_id=action_id,
            confirmation_token=confirmation_token,
        )

    return mcp


async def health(request: Request) -> Response:
    return JSONResponse({"ok": True, "status": "healthy"})


async def ready(request: Request) -> Response:
    return JSONResponse({"ok": True, "status": "ready"})


def create_asgi_app(
    runtime: RuntimeClient | None = None,
    *,
    mcp_server: FastMCP | None = None,
) -> Starlette:
    mcp = mcp_server or create_mcp_server(runtime)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):  # type: ignore[no-untyped-def]
        async with mcp.session_manager.run():
            yield

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/ready", ready, methods=["GET"]),
            Mount("/", app=mcp.streamable_http_app()),
        ],
        lifespan=lifespan,
    )


def main() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    app = create_asgi_app()
    uvicorn.run(app, host=settings.host, port=settings.port)


def main_stdio() -> None:
    """Run the MCP server over stdio transport (for Claude Desktop integration)."""
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    mcp = create_mcp_server(create_runtime_client(settings))
    mcp.run(transport="stdio")


def fake_demo_app() -> Starlette:
    return create_asgi_app(FakeRuntimeClient())


if __name__ == "__main__":
    main()
