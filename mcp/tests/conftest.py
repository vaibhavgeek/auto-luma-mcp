from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from mcp.client.session import ClientSession
from mcp.shared.memory import create_connected_server_and_client_session

from lumabot_mcp.app import create_mcp_server
from lumabot_mcp.runtime_client import FakeRuntimeClient


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def fake_runtime() -> FakeRuntimeClient:
    return FakeRuntimeClient()


@pytest.fixture
async def client_session(fake_runtime: FakeRuntimeClient) -> AsyncGenerator[ClientSession]:
    server = create_mcp_server(fake_runtime)
    async with create_connected_server_and_client_session(
        server,
        raise_exceptions=True,
    ) as session:
        await session.initialize()
        yield session

