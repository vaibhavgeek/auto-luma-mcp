#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AKASH_DIR = ROOT / "infra" / "akash"
REQUIRED_SECRETS = {
    "LUMABOT_RUNTIME_URL",
    "LUMABOT_RUNTIME_INTERNAL_TOKEN",
    "LUMABOT_DATABASE_URL",
    "LUMABOT_SESSION_ENCRYPTION_KEY",
    "AGENTMAIL_INBOX_ID",
    "AGENTMAIL_API_KEY",
    "AGENTMAIL_WEBHOOK_SECRET",
    "NEXLA_MCP_ENDPOINT",
    "NEXLA_TOOLSET_ID",
    "ZERO_API_KEY",
    "LUMABOT_WORKER_CONCURRENCY",
}


def main() -> int:
    failures: list[str] = []
    manifest_text = ""

    for path in sorted(AKASH_DIR.glob("*.deploy.yaml")):
        text = path.read_text(encoding="utf-8")
        manifest_text += text
        if ":latest" in text:
            failures.append(f"{path.relative_to(ROOT)} uses latest image tag")
        for image in re.findall(r"image:\s*(\S+)", text):
            if ":" not in image or image.endswith(":"):
                failures.append(f"{path.relative_to(ROOT)} image is not pinned: {image}")
        if "AUTO_REGISTRATION_ENABLED=true" in text:
            failures.append(f"{path.relative_to(ROOT)} enables auto-registration")
        if "expose: []" in text and "runtime-worker" in path.name:
            continue

    missing = sorted(secret for secret in REQUIRED_SECRETS if f"${secret}" not in manifest_text)
    failures.extend(f"missing Akash secret reference {secret}" for secret in missing)

    if failures:
        for failure in failures:
            print(f"INFRA CHECK FAILED: {failure}", file=sys.stderr)
        return 1
    print("infra checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
