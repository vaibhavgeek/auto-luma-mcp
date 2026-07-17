from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeNexlaHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self._json({"ok": True})
            return
        self._json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        identifier = body.get("person_id") or body.get("company_id") or body.get("id") or "fixture"
        self._json({"id": identifier, "accepted": True})

    def _json(self, payload: dict[str, object], status: int = 200) -> None:
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), FakeNexlaHandler)
    print("Fake Nexla server listening on http://127.0.0.1:8765")
    server.serve_forever()


if __name__ == "__main__":
    main()

