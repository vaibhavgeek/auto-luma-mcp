# Zero-Proxied Enrichment Providers

LumaBot proxies paid provider calls through Zero capabilities instead of calling
provider APIs directly in the runtime request path.

Default Zero capabilities:

- PDL person enrichment: `pdl-person-enrich-e8ccbe47`
- PDL company enrichment: `pdl-company-enrich-0f2efa9c`
- Hunter email verifier: `hunter-email-verifier-1d1a2575`

Runtime path:

```text
EnrichmentService
 -> ZeroCapabilityClient
 -> zero fetch --capability ... --json
 -> PDL/Hunter capability provider
 -> normalized EvidenceField models
```

The direct provider-specific code in this workstream is retained for response
normalization, fakes, and tests. Production configuration should prefer
`ZeroCapabilityClient` so Zero handles capability discovery, payment, and provider
access.

People Data Labs endpoints:

- `GET https://api.peopledatalabs.com/v5/person/enrich`
- `GET https://api.peopledatalabs.com/v5/company/enrich`

People Data Labs authentication:

- `X-Api-Key: $PEOPLE_DATA_LABS_API_KEY`

Hunter endpoints:

- `GET https://api.hunter.io/v2/email-finder`
- `GET https://api.hunter.io/v2/email-verifier`
- `GET https://api.hunter.io/v2/domain-search`

Hunter authentication:

- `api_key=$HUNTER_API_KEY`

Clearbit Autocomplete endpoint:

- `GET https://autocomplete.clearbit.com/v1/companies/suggest?query=...`

The runtime maps PDL responses into evidence-bearing fields:

- `value`
- `source`
- `source_url`
- `retrieved_at`
- `confidence`

Default tests and demos use fakes/mocked runners; they never call live providers
or spend through Zero. Live provider usage should be opt-in and should never log
Zero wallet details, access keys, or raw paid provider response bodies. Hunter
data should be treated as user-facing contact intelligence only after explicit
product review; it should not be used for unsolicited attendee outreach.

Useful request inputs from Luma:

- person full name
- visible social/profile URL
- visible company name
- visible title
- visible location
- visible or inferred company domain
- company name
- company website/domain when known

Known gaps:

- Funding stage quality depends on the PDL plan/field bundle.
- Some company data is inferred from professional profiles and may be incomplete.
- Person enrichment should be used for attendee prioritization, not unsolicited outreach.

Overall demo path:

1. Luma browser ingestion produces visible attendees.
2. `EnrichmentService` enriches each attendee through Zero capabilities.
3. The service emits normalized `EnrichedPerson` and `EnrichedCompany` records.
4. Identity resolution matches enriched records to visible attendees.
5. Scoring ranks attendees against the user's profile.
6. Report generation renders JSON, HTML, and plain-text report outputs.
