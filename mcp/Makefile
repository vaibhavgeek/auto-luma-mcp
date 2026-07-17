.PHONY: demo test lint typecheck

demo:
	@set -a && [ -f ../.env ] && . ../.env; set +a; uv run lumabot-mcp-demo

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run mypy src
