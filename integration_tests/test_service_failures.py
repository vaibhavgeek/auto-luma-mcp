import unittest

from integration_tests.fake_stack import FakeAgentMail, FakeNexla, FakeRuntime, FakeZero


class ServiceFailureTest(unittest.TestCase):
    def test_nexla_unavailable_keeps_partial_report_available(self) -> None:
        runtime = FakeRuntime(nexla=FakeNexla(unavailable=True))
        result = runtime.run_full_fixture_workflow()

        self.assertEqual(result["report"]["status"], "partial")
        self.assertIn("Nexla unavailable", result["report"]["warnings"])
        self.assertEqual(len(result["report"]["top_people"]), 3)
        self.assertEqual(runtime.store.counts()["enrichments"], 0)

    def test_agentmail_unavailable_keeps_partial_report_available(self) -> None:
        runtime = FakeRuntime(agentmail=FakeAgentMail(unavailable=True))
        result = runtime.run_full_fixture_workflow()

        self.assertEqual(result["report"]["status"], "partial")
        self.assertIn("AgentMail unavailable", result["report"]["warnings"])
        self.assertIsNone(result["email_send"])
        self.assertEqual(len(result["report"]["top_people"]), 3)

    def test_zero_unavailable_keeps_partial_report_available(self) -> None:
        runtime = FakeRuntime(zero=FakeZero(unavailable=True))
        result = runtime.run_full_fixture_workflow()

        self.assertEqual(result["report"]["status"], "partial")
        self.assertIn("Zero unavailable", result["report"]["warnings"])
        self.assertIsNone(result["zero_page"])

    def test_malformed_enrichment_record_is_skipped(self) -> None:
        runtime = FakeRuntime(nexla=FakeNexla(malformed_one=True))
        result = runtime.run_full_fixture_workflow()

        self.assertEqual(result["report"]["status"], "partial")
        self.assertIn("one enrichment record malformed", result["report"]["warnings"])
        self.assertEqual(len(result["report"]["top_people"]), 3)
        self.assertEqual(runtime.store.counts()["enrichments"], 2)

    def test_report_partially_generated_then_completed_on_replay(self) -> None:
        runtime = FakeRuntime()
        login = runtime.start_login("demo@lumabot.local")
        session = runtime.complete_login(login["login_id"], login["verification_code"])
        runtime.save_profile(session["session_id"], "seed-stage AI developer-tool roles")
        event = runtime.discover_events(session["session_id"])[0]
        job = runtime.queue_event_job(session["session_id"], event["event_id"])

        partial = runtime.run_report_job(job["job_id"], stop_after_partial=True)
        saved_partial = runtime.get_event_report(session["session_id"], event["event_id"])
        completed = runtime.run_report_job(job["job_id"])

        self.assertEqual(partial["status"], "partial")
        self.assertEqual(saved_partial["status"], "partial")
        self.assertEqual(completed["status"], "complete")
        self.assertEqual(runtime.store.counts()["reports"], 1)
        self.assertEqual(runtime.store.counts()["email_sends"], 1)

    def test_worker_restart_during_job_is_idempotent(self) -> None:
        runtime = FakeRuntime()
        login = runtime.start_login("demo@lumabot.local")
        session = runtime.complete_login(login["login_id"], login["verification_code"])
        runtime.save_profile(session["session_id"], "seed-stage AI developer-tool roles")
        event = runtime.discover_events(session["session_id"])[0]
        job_id = runtime.queue_event_job(session["session_id"], event["event_id"])["job_id"]

        interrupted = runtime.run_report_job(job_id, stop_after_partial=True)
        resumed = runtime.run_report_job(job_id)

        self.assertEqual(interrupted["report_id"], resumed["report_id"])
        self.assertEqual(resumed["status"], "complete")
        self.assertEqual(runtime.store.counts()["reports"], 1)
        self.assertEqual(runtime.store.counts()["email_sends"], 1)


if __name__ == "__main__":
    unittest.main()
