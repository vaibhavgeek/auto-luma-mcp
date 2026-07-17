from __future__ import annotations

import httpx
import pytest
import respx

from lumabot_runtime.clearbit import ClearbitAutocompleteClient, CompanyHint, FakeCompanyHintClient
from lumabot_runtime.enrichment.models import EvidenceField


@pytest.mark.asyncio
async def test_clearbit_autocomplete_maps_company_hints() -> None:
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://autocomplete.clearbit.com/v1/companies/suggest").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "name": "VectorForge",
                        "domain": "vectorforge.ai",
                        "logo": "https://logo.clearbit.com/vectorforge.ai",
                    }
                ],
            )
        )
        client = ClearbitAutocompleteClient()
        hints = await client.suggest_companies("VectorForge")

    assert route.calls[0].request.url.params["query"] == "VectorForge"
    assert hints[0].name.value == "VectorForge"
    assert hints[0].domain.value == "vectorforge.ai"
    assert hints[0].logo_url.value == "https://logo.clearbit.com/vectorforge.ai"


@pytest.mark.asyncio
async def test_fake_company_hint_client() -> None:
    client = FakeCompanyHintClient(
        hints=[
            CompanyHint(
                name=EvidenceField(value="VectorForge", source="fixture", confidence=0.5),
                domain=EvidenceField(value="vectorforge.ai", source="fixture", confidence=0.5),
            )
        ]
    )

    assert (await client.suggest_companies("VectorForge"))[0].domain.value == "vectorforge.ai"

