# Enrichment Provider Testing

Default tests use fake provider clients and mocked HTTP responses through `respx`.
They must not contact People Data Labs, Hunter, or Clearbit.

Manual live smoke test plan:

1. Set `PEOPLE_DATA_LABS_API_KEY`.
2. Optionally set `HUNTER_API_KEY`.
2. Use one intentionally selected test person/company record.
3. Do not print the API key.
4. Do not snapshot full paid provider responses.
5. Confirm normalized evidence fields include `source=people-data-labs:*` and, when used, `source=hunter:*` or `source=clearbit:*`.
