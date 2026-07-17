#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration_tests.fake_stack import FakeAgentMail, FakeRuntime, FakeRuntimeConfig


SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\b(?:nexla|agentmail|zero)[_-]?(?:api)?[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_./+=-]{16,}['\"]", re.I),
]
POSTGRES_PASSWORD_URL = re.compile(r"postgres(?:ql)?://[^:\s]+:[^@\s]+@[^)\s'\"]+", re.I)


def main() -> int:
    failures: list[str] = []
    tracked = tracked_files()

    if any(Path(path).name == ".env" for path in tracked):
        failures.append(".env is tracked; remove it from git")

    for path in tracked:
        full_path = ROOT / path
        if not full_path.is_file() or full_path.stat().st_size > 1_000_000:
            continue
        text = full_path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"likely API key in {path}")
                break
        if POSTGRES_PASSWORD_URL.search(text):
            failures.append(f"PostgreSQL URL with password in {path}")
        if path.startswith(("fixtures/", "integration_tests/fixtures/")) and re.search(r"\b(?:Cookie|Set-Cookie):|sessionid=", text):
            failures.append(f"plaintext cookie fixture in {path}")
        if path.endswith((".log", ".snapshot", ".snap")) and re.search(r"(?:verification|login)\s+code\s*[:=]\s*\d{4,8}", text, re.I):
            failures.append(f"login code appears in log or snapshot {path}")
        if "snapshot" in path.lower() and re.search(r"agentmail.+(?:api[_-]?key|credential|secret)", text, re.I):
            failures.append(f"AgentMail credential appears in snapshot {path}")
        if path.startswith("infra/") and ":latest" in text:
            failures.append(f"unpinned latest image tag in {path}")

    runtime = FakeRuntime(config=FakeRuntimeConfig())
    if runtime.api.request_internal_route("/internal/jobs")["status"] != 401:
        failures.append("runtime internal route accepts unauthenticated calls")
    if runtime.config.auto_registration_enabled:
        failures.append("auto-registration defaults to enabled")
    if not runtime.config.physical_mail_requires_confirmation:
        failures.append("physical mail confirmation is not required")
    try:
        FakeAgentMail().send_physical_mail(confirmed=False)
        failures.append("physical mail bypasses confirmation")
    except PermissionError:
        pass

    if failures:
        for failure in failures:
            print(f"SECURITY CHECK FAILED: {failure}", file=sys.stderr)
        return 1
    print("security checks passed")
    return 0


def tracked_files() -> list[str]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        output = "\n".join(str(path.relative_to(ROOT)) for path in ROOT.rglob("*") if path.is_file())
    return [line.strip() for line in output.splitlines() if line.strip()]


if __name__ == "__main__":
    os.chdir(ROOT)
    raise SystemExit(main())
