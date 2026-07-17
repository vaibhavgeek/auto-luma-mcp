FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml TESTING.md ./
COPY src ./src

RUN uv sync --no-dev

ENV LUMABOT_MCP_HOST=127.0.0.1
ENV LUMABOT_MCP_PORT=8000

EXPOSE 8000

CMD ["uv", "run", "lumabot-mcp"]

