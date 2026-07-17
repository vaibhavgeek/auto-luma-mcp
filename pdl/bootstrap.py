from __future__ import annotations

import os


def main() -> None:
    configured = bool(os.getenv("PEOPLE_DATA_LABS_API_KEY"))
    print("People Data Labs provider bootstrap")
    print(f"PEOPLE_DATA_LABS_API_KEY configured: {configured}")
    print("Default tests use fakes; live smoke tests should be opt-in.")


if __name__ == "__main__":
    main()

