"""Direct PostgreSQL persistence using asyncpg and DATABASE_URL."""
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")


async def _get_conn() -> asyncpg.Connection:
    return await asyncpg.connect(DATABASE_URL)


async def get_or_create_user(email: str) -> str:
    """Ensure app_users row exists; return user_id as string."""
    conn = await _get_conn()
    try:
        row = await conn.fetchrow("SELECT id FROM app_users WHERE email = $1", email)
        if row:
            return str(row["id"])
        row = await conn.fetchrow(
            "INSERT INTO app_users (email) VALUES ($1) ON CONFLICT (email) DO UPDATE SET email = $1 RETURNING id",
            email,
        )
        return str(row["id"])
    finally:
        await conn.close()


# ─── Session persistence ──────────────────────────────────────────────────────


async def save_session_to_db(email: str, session_data: dict[str, Any]) -> None:
    """Save session cookies to auth_sessions (encrypted_browser_session as JSON bytes)."""
    conn = await _get_conn()
    try:
        user_id = await get_or_create_user(email)
        session_bytes = json.dumps(session_data, default=str).encode("utf-8")
        # Upsert: delete old sessions for this user+provider, insert new
        await conn.execute(
            "DELETE FROM auth_sessions WHERE user_id = $1 AND provider = 'luma'",
            user_id,
        )
        await conn.execute(
            """INSERT INTO auth_sessions (user_id, provider, encrypted_browser_session)
               VALUES ($1, 'luma', $2)""",
            user_id,
            session_bytes,
        )
        logger.info("Session saved to DB for %s", email)
    except Exception as exc:
        logger.error("Failed to save session to DB: %s", exc)
    finally:
        await conn.close()


async def load_session_from_db(email: str) -> dict[str, Any] | None:
    """Load session from auth_sessions."""
    conn = await _get_conn()
    try:
        row = await conn.fetchrow(
            """SELECT s.encrypted_browser_session
               FROM auth_sessions s
               JOIN app_users u ON u.id = s.user_id
               WHERE u.email = $1 AND s.provider = 'luma' AND s.revoked_at IS NULL
               ORDER BY s.created_at DESC LIMIT 1""",
            email,
        )
        if row:
            return json.loads(row["encrypted_browser_session"].decode("utf-8"))
        return None
    except Exception as exc:
        logger.error("Failed to load session from DB: %s", exc)
        return None
    finally:
        await conn.close()


# ─── Event persistence ────────────────────────────────────────────────────────


async def save_events_to_db(events: list[dict[str, Any]]) -> None:
    """Save scraped events to the events table. URL is the unique key."""
    if not DATABASE_URL:
        logger.info("No DATABASE_URL configured, skipping DB save")
        return

    conn = await _get_conn()
    try:
        for event in events:
            try:
                url = event.get("url", "")
                if not url:
                    continue

                # Parse date string into a timestamp — fallback to now if unparseable
                starts_at = datetime.now(UTC)
                date_str = event.get("date")
                if date_str:
                    try:
                        from dateutil.parser import parse as parse_date
                        starts_at = parse_date(date_str)
                    except Exception:
                        pass

                await conn.execute(
                    """INSERT INTO events (url, title, starts_at, location_name, source, source_evidence)
                       VALUES ($1, $2, $3, $4, 'luma', $5)
                       ON CONFLICT (url) DO UPDATE SET
                         title = EXCLUDED.title,
                         location_name = EXCLUDED.location_name,
                         source_evidence = EXCLUDED.source_evidence,
                         updated_at = now()""",
                    url,
                    event.get("title", "Untitled"),
                    starts_at,
                    event.get("venue"),
                    json.dumps({
                        "organizer": event.get("organizer"),
                        "image_url": event.get("image_url"),
                        "description": event.get("description"),
                        "attendees": event.get("attendees"),
                        "interest_score": event.get("interest_score"),
                        "interest_reason": event.get("interest_reason"),
                        "scraped_at": datetime.now(UTC).isoformat(),
                    }),
                )
            except Exception as exc:
                logger.warning("Failed to save event %s: %s", event.get("url"), exc)

        logger.info("Saved %d events to DB", len(events))
    finally:
        await conn.close()


# ─── Profile persistence ──────────────────────────────────────────────────────


async def save_profile_to_db(email: str, profile: dict[str, Any]) -> None:
    """Save user profile to user_profiles table."""
    conn = await _get_conn()
    try:
        user_id = await get_or_create_user(email)
        await conn.execute(
            """INSERT INTO user_profiles (user_id, headline, location, goals, skills, source_evidence)
               VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (user_id) DO UPDATE SET
                 headline = EXCLUDED.headline,
                 location = EXCLUDED.location,
                 goals = EXCLUDED.goals,
                 skills = EXCLUDED.skills,
                 source_evidence = EXCLUDED.source_evidence,
                 updated_at = now()""",
            user_id,
            profile.get("profile_text", "")[:200],
            profile.get("location", ""),
            json.dumps(profile.get("interests", [])),
            json.dumps(profile.get("skills", [])),
            json.dumps({"profile_text": profile.get("profile_text", "")}),
        )
        logger.info("Profile saved to DB for %s", email)
    except Exception as exc:
        logger.error("Failed to save profile to DB: %s", exc)
    finally:
        await conn.close()


async def load_profile_from_db(email: str) -> dict[str, Any] | None:
    """Load user profile from user_profiles table."""
    conn = await _get_conn()
    try:
        row = await conn.fetchrow(
            """SELECT p.headline, p.location, p.goals, p.skills, p.source_evidence
               FROM user_profiles p
               JOIN app_users u ON u.id = p.user_id
               WHERE u.email = $1""",
            email,
        )
        if row:
            source = json.loads(row["source_evidence"]) if row["source_evidence"] else {}
            return {
                "profile_text": source.get("profile_text", row["headline"] or ""),
                "interests": json.loads(row["goals"]) if row["goals"] else [],
                "skills": json.loads(row["skills"]) if row["skills"] else [],
                "location": row["location"] or "",
            }
        return None
    except Exception as exc:
        logger.error("Failed to load profile from DB: %s", exc)
        return None
    finally:
        await conn.close()
