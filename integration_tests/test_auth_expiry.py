import unittest

from integration_tests.fake_stack import BrowserSessionExpired, FakeLumaBrowser, FakeRuntime


class AuthExpiryTest(unittest.TestCase):
    def test_browser_session_expired_requires_login_refresh(self) -> None:
        runtime = FakeRuntime(browser=FakeLumaBrowser(session_expired=True))

        with self.assertRaises(BrowserSessionExpired):
            runtime.run_full_fixture_workflow()

        runtime.browser.session_expired = False
        result = runtime.run_full_fixture_workflow()

        self.assertEqual(result["job"]["status"], "complete")
        self.assertEqual(result["report"]["status"], "complete")


if __name__ == "__main__":
    unittest.main()
