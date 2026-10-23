"""
Guard: the HTML deadline extractor must not latch a PAST "closed <date>" as the
application deadline.

Regression for the bug where the deadline trigger alternation included the
past-tense "closed" (close[sd]? matches close/closes/closed). Because re.search
returns the FIRST match, a grant page that reads

    "Applications closed January 15, 2024. Next deadline: March 1, 2027."

captured the expired 2024-01-15 ("closed ...") instead of the real upcoming
2027-03-01 ("deadline ..."). That past date then flows into both the human
report and the Claude scorer's AWARD/deadline context, making an OPEN grant
look expired and skewing ranking/alerts.

"closed" denotes a window that has already shut, so it must never be read as a
deadline. The present/future forms ("close"/"closes") stay valid. Standard
library unittest, no network -- HTML is passed to the extractor directly.
"""
import unittest
from datetime import date

from grant_agent.scraper import _extract_grants_from_html


def _one(html: str):
    grants = _extract_grants_from_html(html, "Test Source", "https://example.org/grant")
    assert len(grants) == 1, grants
    return grants[0]


class DeadlineExcludesClosedPast(unittest.TestCase):
    def test_closed_past_not_latched_before_real_deadline(self):
        g = _one(
            "<p>Applications closed January 15, 2024. "
            "Next deadline: March 1, 2027.</p>"
        )
        self.assertEqual(g.deadline, date(2027, 3, 1))

    def test_closed_alone_yields_no_deadline(self):
        # A page advertising only a shut window must not report it as a deadline.
        g = _one("<p>This cycle closed January 15, 2024.</p>")
        self.assertIsNone(g.deadline)

    def test_closes_future_still_captured(self):
        g = _one("<p>The application window closes March 1, 2027.</p>")
        self.assertEqual(g.deadline, date(2027, 3, 1))

    def test_close_base_form_still_captured(self):
        g = _one("<p>Applications close 2027-03-01 for this program.</p>")
        self.assertEqual(g.deadline, date(2027, 3, 1))

    def test_deadline_trigger_unchanged(self):
        g = _one("<p>Deadline: June 1, 2027.</p>")
        self.assertEqual(g.deadline, date(2027, 6, 1))

    def test_due_trigger_unchanged(self):
        g = _one("<p>Applications due 07/01/2027.</p>")
        self.assertEqual(g.deadline, date(2027, 7, 1))

    def test_apply_by_trigger_unchanged(self):
        g = _one("<p>Apply by August 1, 2027 to be considered.</p>")
        self.assertEqual(g.deadline, date(2027, 8, 1))


if __name__ == "__main__":
    unittest.main()
