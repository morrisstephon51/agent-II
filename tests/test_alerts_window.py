"""
Guard: alerts.py user-facing deadline-window text must reflect ALERT_DAYS, not a
hard-coded "30". The filter (ScoredGrant.is_urgent(ALERT_DAYS)) already honors the
config knob; the stdout header, no-grants message, email subject, and email body
must say the same window or the alert lies about what it selected.

Stdlib unittest, no network: _send_composio_email is replaced with a capturing
stub and ALERT_EMAIL is patched so the email-build path runs without sending.
"""
import io
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from grant_agent import alerts
from grant_agent.models import Grant, ScoredGrant


def _urgent_grant(days_out: int) -> ScoredGrant:
    return ScoredGrant(
        grant=Grant(
            title="Test Grant",
            url="https://example.org/grant",
            source="UnitTest",
            description="desc",
            deadline=date.today() + timedelta(days=days_out),
            award_min=1000,
            award_max=5000,
        ),
        fit_score=8,
        qualification_summary="Matches mission.",
    )


class AlertWindowFollowsAlertDays(unittest.TestCase):
    def test_stdout_subject_body_use_configured_window(self):
        """With ALERT_DAYS=14 and an urgent grant, every window string says 14, not 30."""
        captured = {}

        def fake_send(subject, body):
            captured["subject"] = subject
            captured["body"] = body
            return True

        grant = _urgent_grant(10)  # urgent under both 14 and 30, so only the TEXT differs
        buf = io.StringIO()
        with mock.patch.object(alerts, "ALERT_DAYS", 14), \
             mock.patch.object(alerts, "ALERT_EMAIL", "t@example.com"), \
             mock.patch.object(alerts, "_send_composio_email", side_effect=fake_send):
            with redirect_stdout(buf):
                alerts.check_and_alert([grant], Path("/tmp/report.md"))

        out = buf.getvalue()
        # stdout header (line 54)
        self.assertIn("within 14 days", out)
        self.assertNotIn("within 30 days", out)
        # email subject (line 71)
        self.assertIn("within 14 days", captured["subject"])
        self.assertNotIn("within 30 days", captured["subject"])
        # email body (line 75)
        self.assertIn("within the next 14 days", captured["body"])
        self.assertNotIn("within the next 30 days", captured["body"])

    def test_no_grants_message_uses_configured_window(self):
        """With ALERT_DAYS=14 and nothing urgent, the no-grants line says 14-day."""
        buf = io.StringIO()
        with mock.patch.object(alerts, "ALERT_DAYS", 14):
            with redirect_stdout(buf):
                alerts.check_and_alert([], Path("/tmp/report.md"))
        out = buf.getvalue()
        self.assertIn("14-day deadline window", out)
        self.assertNotIn("30-day deadline window", out)

    def test_default_window_still_reads_30(self):
        """Regression: at the real default (ALERT_DAYS=30) the text still reads 30.

        Green on both buggy and fixed code — proves the fix is a faithful
        interpolation, not a hard-flip to another constant.
        """
        buf = io.StringIO()
        with mock.patch.object(alerts, "ALERT_DAYS", 30):
            with redirect_stdout(buf):
                alerts.check_and_alert([_urgent_grant(5)], Path("/tmp/report.md"))
        self.assertIn("within 30 days", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
