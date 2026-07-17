import unittest

from integration_tests.fake_stack import FakeRuntime


class IdempotentReplayTest(unittest.TestCase):
    def test_repeated_execution_does_not_duplicate_side_effects(self) -> None:
        runtime = FakeRuntime()

        first = runtime.run_full_fixture_workflow()
        second = runtime.run_full_fixture_workflow()
        third = runtime.run_full_fixture_workflow()

        self.assertEqual(first["report"]["report_id"], second["report"]["report_id"])
        self.assertEqual(second["report"]["report_id"], third["report"]["report_id"])
        self.assertEqual(
            runtime.store.counts(),
            {
                "users": 1,
                "sessions": 1,
                "profiles": 1,
                "events": 2,
                "attendees": 3,
                "enrichments": 3,
                "scores": 3,
                "jobs": 1,
                "reports": 1,
                "email_sends": 1,
                "registrations": 1,
                "zero_pages": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()
