#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integration_tests.fake_stack import FakeRuntime, workflow_as_json


def main() -> int:
    runtime = FakeRuntime()
    result = runtime.run_full_fixture_workflow()
    print(workflow_as_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
