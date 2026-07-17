FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv \
    && npm install -g @zeroxyz/cli

COPY pyproject.toml uv.lock ./
COPY src ./src

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN uv sync --frozen --no-dev \
    && uv run playwright install --with-deps chromium

ENV RUNTIME_HOST=0.0.0.0
ENV RUNTIME_PORT=8080
ENV HEADLESS=true

VOLUME ["/app/sessions"]
EXPOSE 8080

CMD ["uv", "run", "lumabot-runtime"]
