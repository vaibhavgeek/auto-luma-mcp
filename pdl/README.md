# People Data Labs Provider

LumaBot uses People Data Labs directly for person and company enrichment.

Official endpoints:

- `GET https://api.peopledatalabs.com/v5/person/enrich`
- `GET https://api.peopledatalabs.com/v5/company/enrich`

Authentication:

- `X-Api-Key: $PEOPLE_DATA_LABS_API_KEY`

The runtime maps PDL responses into evidence-bearing fields:

- `value`
- `source`
- `source_url`
- `retrieved_at`
- `confidence`

Default tests and demos use `FakePeopleDataLabsClient`; they never call PDL.
Live PDL usage should be opt-in and should never log the API key or raw paid
provider response bodies.

Useful request inputs from Luma:

- person full name
- visible social/profile URL
- visible company name
- visible title
- visible location
- company name
- company website/domain when known

Known gaps:

- Funding stage quality depends on the PDL plan/field bundle.
- Some company data is inferred from professional profiles and may be incomplete.
- Person enrichment should be used for attendee prioritization, not unsolicited outreach.
