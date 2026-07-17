#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SERVICE_NAME = os.environ.get("SERVICE_NAME", "lumabot-fixture")
PORT = int(os.environ.get("PORT", "8080"))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in {"/", "/healthz", "/readyz"}:
            self._send(200, {"service": SERVICE_NAME, "status": "ok"})
            return
        if self.path.startswith("/internal/"):
            token = self.headers.get("Authorization", "")
            expected = os.environ.get("RUNTIME_INTERNAL_TOKEN", "fixture-internal-token")
            if token != f"Bearer {expected}":
                self._send(401, {"error": "missing or invalid runtime token"})
                return
            self._send(200, {"service": SERVICE_NAME, "internal": "ok"})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        self._send(202, {"service": SERVICE_NAME, "accepted": True})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{SERVICE_NAME}: {fmt % args}")

    def _send(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"{SERVICE_NAME} listening on :{PORT}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
