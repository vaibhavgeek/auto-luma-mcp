from __future__ import annotations

from pathlib import Path
from typing import Iterable

from playwright.async_api import Browser, Error, async_playwright


async def load_local_pages_with_chromium(paths: Iterable[Path], timeout_ms: int = 10_000) -> list[str]:
    """Load local fixture pages in separate Chromium contexts and return rendered HTML."""
    rendered: list[str] = []
    async with async_playwright() as playwright:
        browser: Browser | None = None
        try:
            try:
                browser = await playwright.chromium.launch(channel="chrome", headless=True)
            except Error:
                browser = await playwright.chromium.launch(headless=True)

            for path in paths:
                context = await browser.new_context()
                try:
                    page = await context.new_page()
                    page.set_default_timeout(timeout_ms)
                    await page.goto(path.resolve().as_uri())
                    rendered.append(await page.content())
                finally:
                    await context.close()
        finally:
            if browser is not None:
                await browser.close()
    return rendered

