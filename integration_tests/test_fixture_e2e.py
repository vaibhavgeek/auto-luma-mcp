import unittest

from integration_tests.fake_stack import FakeMCPServer, FakeRuntime, PROFILE_TEXT


class FixtureE2ETest(unittest.TestCase):
    def test_complete_fixture_workflow_returns_report_through_mcp(self) -> None:
        runtime = FakeRuntime()
        mcp = FakeMCPServer(runtime)

        login = mcp.login("demo@lumabot.local")
        session = mcp.complete_fixture_login(login["login_id"], "000000")
        profile = mcp.set_user_profile(session["session_id"], PROFILE_TEXT)
        events = mcp.recommend_events(session["session_id"])
        selected_event = events[0]
        job = mcp.select_event(session["session_id"], selected_event["event_id"])
        report = mcp.get_event_report(session["session_id"], selected_event["event_id"])

        self.assertEqual(profile["text"], PROFILE_TEXT)
        self.assertEqual(job["status"], "complete")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["event_id"], "evt_bay_area_ai_hacknight")
        self.assertEqual(len(report["top_people"]), 3)
        self.assertIn("seed", report["company_stages"])
        self.assertTrue(all("relevance_score" in person for person in report["top_people"]))
        self.assertTrue(all("identity_confidence" in person for person in report["top_people"]))
        self.assertEqual(runtime.store.email_sends[report["report_id"]]["thread_id"][:7], "thread_")
        self.assertEqual(runtime.store.zero_pages[report["report_id"]]["title"], "Networking Bingo")

        before = runtime.store.counts()
        replay = runtime.run_full_fixture_workflow()
        self.assertEqual(replay["report"]["report_id"], report["report_id"])
        self.assertEqual(runtime.store.counts(), before)


if __name__ == "__main__":
    unittest.main()
