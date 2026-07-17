# Nexla Testing

Default tests use `FakeNexlaClient` and fixture data. They must not call Nexla.

Opt-in live validation should be added only after Express.dev flows, Nexsets, and an
external MCP ToolSet are configured with secrets supplied through environment variables.
Never commit API keys or service keys.

