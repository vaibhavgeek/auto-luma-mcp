FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv \
    && npm install -g @zeroxyz/cli

WORKDIR /app/runtime
COPY runtime/pyproject.toml runtime/uv.lock ./
COPY runtime/src ./src
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN uv sync --frozen --no-dev \
    && uv run playwright install --with-deps chromium

WORKDIR /app/mcp
COPY mcp/pyproject.toml mcp/uv.lock mcp/TESTING.md ./
COPY mcp/src ./src
RUN uv sync --frozen --no-dev

COPY deploy/start-all.sh /usr/local/bin/lumabot-start
RUN chmod +x /usr/local/bin/lumabot-start

ENV RUNTIME_HOST=127.0.0.1
ENV RUNTIME_PORT=8080
ENV LUMABOT_RUNTIME_URL=http://127.0.0.1:8080
ENV LUMABOT_MCP_HOST=0.0.0.0
ENV LUMABOT_MCP_PORT=8000
ENV HEADLESS=true

VOLUME ["/app/runtime/sessions"]
EXPOSE 8000

CMD ["lumabot-start"]
