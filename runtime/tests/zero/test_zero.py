from __future__ import annotations

import pytest

from lumabot_runtime.models import RuntimeState
from lumabot_runtime.zero.client import FakeZeroClient, ZeroArtifactService


async def test_capability_discovery_and_hosted_page_choice() -> None:
    state = RuntimeState()
    client = FakeZeroClient(["generated_image", "hosted_page"])
    result = await ZeroArtifactService(state, client).create_networking_bingo(
        user_id="u1",
        event_id="e1",
        report_url="https://reports/e1",
    )
    assert result["capability"] == "hosted_page"
    assert state.zero_invocations[0]["artifact_id"] == result["artifact_id"]


async def test_image_fallback_and_physical_mail_confirmation() -> None:
    image_service = ZeroArtifactService(RuntimeState(), FakeZeroClient(["generated_image"]))
    image_result = await image_service.create_networking_bingo(
        user_id="u1",
        event_id="e1",
        report_url="https://reports/e1",
    )
    assert image_result["capability"] == "generated_image"

    with pytest.raises(PermissionError):
        mail_service = ZeroArtifactService(RuntimeState(), FakeZeroClient(["physical_mail"]))
        await mail_service.create_networking_bingo(
            user_id="u1",
            event_id="e1",
            report_url="https://reports/e1",
        )
