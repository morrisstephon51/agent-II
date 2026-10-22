"""
Guard: the deadline parser must accept every date shape the extraction regex
can capture — including comma-less month names ("January 5 2026").

Regression for the bug where `_DATE_PATTERNS` only had the comma variants
("%B %d, %Y") while `_extract_grants_from_html`'s regex makes the comma
optional (`\\d{1,2},?\\s+\\d{4}`). A comma-less capture then parsed to None,
so the grant got `deadline=None` and silently dropped out of the urgent
deadline alert / email. Standard-library unittest, no network.
"""
import unittest
from datetime import date

from grant_agent.scraper import _parse_date, _extract_grants_from_html


class ParseDateCommaless(unittest.TestCase):
    def test_commaless_month_dates_parse(self):
        # The exact shapes the extraction regex emits without a comma.
        self.assertEqual(_parse_date("January 5 2026"), date(2026, 1, 5))
        self.assertEqual(_parse_date("Jan 5 2026"), date(2026, 1, 5))
        self.assertEqual(_parse_date("December 15 2025"), date(2025, 12, 15))

    def test_existing_formats_still_parse(self):
        # Must not regress the formats that already worked.
        self.assertEqual(_parse_date("January 5, 2026"), date(2026, 1, 5))
        self.assertEqual(_parse_date("Jan 5, 2026"), date(2026, 1, 5))
        self.assertEqual(_parse_date("2026-01-05"), date(2026, 1, 5))
        self.assertEqual(_parse_date("01/05/2026"), date(2026, 1, 5))
        self.assertEqual(_parse_date("5 January 2026"), date(2026, 1, 5))

    def test_garbage_still_rejected(self):
        for bad in ("", "not a date", "Someday soon"):
            self.assertIsNone(_parse_date(bad))

    def test_end_to_end_commaless_deadline_is_extracted(self):
        # The real failure path: comma-less deadline on a page must survive
        # extraction as a real date, not None.
        html = (
            "<html><body><p>Program details here. "
            "Applications due January 5 2026. Award up to $50,000.</p></body></html>"
        )
        grants = _extract_grants_from_html(html, "Test Source", "https://example.org/grant")
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0].deadline, date(2026, 1, 5))


if __name__ == "__main__":
    unittest.main()
