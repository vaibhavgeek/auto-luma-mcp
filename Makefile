.PHONY: demo test lint typecheck docker-build docker-build-runtime

demo:
	cd shared && uv run python -m lumabot_shared.demo

test:
	cd shared && uv run pytest
	cd runtime && uv run pytest
	cd mcp && uv run pytest

lint:
	cd shared && uv run ruff check .

typecheck:
	cd shared && uv run mypy src

docker-build:
	docker build -f deploy/Dockerfile -t auto-luma-mcp:local .

docker-build-runtime:
	cd runtime && docker build -t lumabot-runtime:local .
