# Zero-Proxied Enrichment Provider Testing

Default tests use fake provider clients, mocked HTTP responses through `respx`,
and fake Zero runners. They must not contact Zero, People Data Labs, Hunter, or
Clearbit, and they must not spend USDC.

Manual live smoke test plan:

1. Run `zero auth` / `zero init` as needed for the local environment.
2. Confirm `zero search --json "People Data Labs person enrichment"` returns a healthy capability.
3. Use one intentionally selected test person/company record.
4. Set a low `--max-pay` or `ZeroCapabilityClient.max_pay_usdc`.
5. Do not print wallet secrets, access keys, or full paid provider responses.
6. Confirm normalized evidence fields include `source=people-data-labs:*` and, when used, `source=zero:hunter-email-verifier`.
