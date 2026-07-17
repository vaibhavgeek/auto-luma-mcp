from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakePeopleDataLabsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/v5/person/enrich"):
            self._json(
                {
                    "full_name": "Maya Chen",
                    "linkedin_url": "https://linkedin.com/in/mayachen",
                    "job_title": "Founder",
                    "job_company_name": "VectorForge",
                }
            )
            return
        if self.path.startswith("/v5/company/enrich"):
            self._json(
                {
                    "display_name": "VectorForge",
                    "industry": "computer software",
                    "employee_count": 18,
                    "latest_funding_stage": "seed",
                    "website": "vectorforge.ai",
                }
            )
            return
        self._json({"error": "not found"}, status=404)

    def _json(self, payload: dict[str, object], status: int = 200) -> None:
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), FakePeopleDataLabsHandler)
    print("Fake People Data Labs server listening on http://127.0.0.1:8765")
    server.serve_forever()


if __name__ == "__main__":
    main()

