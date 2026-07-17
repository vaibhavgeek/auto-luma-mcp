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
 -> Zero provider capability
 -> normalized EvidenceField models
```

Runtime code does not call People Data Labs, Hunter, or Clearbit APIs directly.
It only invokes Zero capabilities, then normalizes the provider-shaped response
payloads into the shared evidence models.

People Data Labs response mapping:

The runtime maps PDL person/company payloads into evidence-bearing fields:

- `value`
- `source`
- `source_url`
- `retrieved_at`
- `confidence`

Default tests and demos use fakes and mocked runners; they never call live providers
or spend through Zero. Live provider usage should be opt-in and should never log
Zero wallet details, access keys, or raw paid provider response bodies. Email
verification data should be treated as contact intelligence only after explicit
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
