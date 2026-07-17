.PHONY: demo test lint typecheck

demo:
	uv run python -m lumabot_shared.demo

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run mypy src
