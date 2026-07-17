#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration_tests.fake_stack import FakeRuntime


def main() -> int:
    runtime = FakeRuntime()
    result = runtime.run_full_fixture_workflow()
    output_dir = ROOT / ".tmp"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "fixture_seed.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"seeded fixture workflow at {output_dir / 'fixture_seed.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
