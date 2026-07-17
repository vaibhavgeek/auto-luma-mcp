# Nexla Express.dev Prompts

Build LumaBot enrichment flows that preserve provenance and never fabricate values.

Required pipelines:

- raw events
- raw people
- raw companies
- normalized people
- enriched people
- enriched companies

Every emitted field must include:

- `value`
- `source`
- `source_url`
- `retrieved_at`
- `confidence`

Normalize social profile URLs before matching. Preserve timestamps and source evidence.
If a provider does not return a fact, emit no field or an explicit null-valued evidence
record with low confidence; never invent missing facts.

Create Nexsets suitable for read-only MCP lookup tools:

- enriched people by normalized social URL
- enriched people by person ID
- enriched companies by company ID
- event attendee enrichment status

