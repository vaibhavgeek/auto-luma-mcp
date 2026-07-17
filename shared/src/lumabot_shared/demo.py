from lumabot_shared.fixtures import make_demo_event_report


def main() -> None:
    print(make_demo_event_report().model_dump_json(indent=2))


if __name__ == "__main__":
    main()
