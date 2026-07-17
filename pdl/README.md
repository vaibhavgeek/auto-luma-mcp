# Enrichment Providers

LumaBot uses People Data Labs as the primary person and company enrichment provider,
with optional Hunter and Clearbit lookups for the small pieces they are better at.

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

Default tests and demos use fakes; they never call live providers.
Live provider usage should be opt-in and should never log API keys or raw paid
provider response bodies. Hunter data should be treated as user-facing contact
intelligence only after explicit product review; it should not be used for
unsolicited attendee outreach.

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

Demo path:

1. Luma browser ingestion produces visible attendees.
2. `EnrichmentService` enriches each attendee through PDL, optional Hunter, and optional Clearbit.
3. The service emits normalized `EnrichedPerson` and `EnrichedCompany` records.
4. Identity resolution matches enriched records to visible attendees.
5. Scoring ranks attendees against the user's profile.
6. Report generation renders JSON, HTML, and plain-text report outputs.
