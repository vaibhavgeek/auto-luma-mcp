#!/usr/bin/env sh
set -eu

cd /app/runtime
if [ "${HEADLESS:-true}" = "false" ] && command -v xvfb-run >/dev/null 2>&1; then
  xvfb-run -a -s "-screen 0 1440x1200x24" uv run lumabot-runtime &
else
  uv run lumabot-runtime &
fi
runtime_pid="$!"

cleanup() {
  kill "$runtime_pid" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

for _ in $(seq 1 30); do
  if python - <<'PY'
import os
import urllib.request

host = os.environ.get("RUNTIME_HOST", "127.0.0.1")
port = os.environ.get("RUNTIME_PORT", "8080")
try:
    with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1) as response:
        raise SystemExit(0 if response.status == 200 else 1)
except Exception:
    raise SystemExit(1)
PY
  then
    break
  fi
  sleep 1
done

cd /app/mcp
exec uv run lumabot-mcp
