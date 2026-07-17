.PHONY: demo test lint typecheck

demo:
	cd shared && uv run python -m lumabot_shared.demo

test:
	cd shared && uv run pytest

lint:
	cd shared && uv run ruff check .

typecheck:
	cd shared && uv run mypy src
