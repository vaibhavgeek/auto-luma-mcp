from __future__ import annotations

import os
from uuid import uuid4

import pytest

from lumabot_runtime.browser import LumaAuthenticator, SessionCrypto
from lumabot_runtime.luma.repository import InMemoryLumaRepository


@pytest.mark.live_luma
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_LUMA_TESTS") != "1" or not os.getenv("LUMA_TEST_EMAIL"),
    reason="set RUN_LIVE_LUMA_TESTS=1 and LUMA_TEST_EMAIL to opt into live Luma smoke tests",
)
@pytest.mark.asyncio
async def test_live_luma_login_start_only() -> None:
    auth = LumaAuthenticator(repository=InMemoryLumaRepository(), crypto=SessionCrypto.generate())
    result = await auth.start_login(uuid4(), os.environ["LUMA_TEST_EMAIL"])

    assert result.email == os.environ["LUMA_TEST_EMAIL"]

