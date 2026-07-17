from __future__ import annotations

from pathlib import Path


def main() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    fixtures.mkdir(exist_ok=True)
    print("Nexla bootstrap placeholder: configure Express.dev flows from express-prompts.md")
    print(f"Fixture directory: {fixtures}")


if __name__ == "__main__":
    main()

