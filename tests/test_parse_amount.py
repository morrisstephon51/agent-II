"""
Guard: _parse_amount must read a dollar amount, never inflate it.

Regression for the bug where _parse_amount stripped EVERY non-digit, so a
decimal point was deleted and the fractional digits merged into the dollar
figure. A formatted currency string "$50,000.00" read as 5000000 (100x) and a
JSON float 50000.0 read as 500000 (10x). Those inflated awards then flowed into
both the human report (award_range_str) and the Claude scorer prompt (the AWARD
line), corrupting ranking and the report. Standard-library unittest, no network.
"""
import unittest

from grant_agent.scraper import _parse_amount


class ParseAmount(unittest.TestCase):
    def test_currency_string_with_cents_is_not_inflated(self):
        self.assertEqual(_parse_amount("$50,000.00"), 50000)
        self.assertEqual(_parse_amount("$1,500,000.00"), 1500000)

    def test_numeric_float_is_not_inflated(self):
        # JSON amounts deserialize to float; stringify+digit-strip used to 10x them.
        self.assertEqual(_parse_amount(50000.0), 50000)
        self.assertEqual(_parse_amount(49999.99), 49999)  # whole dollars, truncated

    def test_plain_and_comma_formats_still_parse(self):
        self.assertEqual(_parse_amount("$50,000"), 50000)
        self.assertEqual(_parse_amount("50000"), 50000)
        self.assertEqual(_parse_amount(50000), 50000)
        self.assertEqual(_parse_amount("Up to $250,000"), 250000)

    def test_empty_and_garbage_return_none(self):
        for bad in ("", None, "N/A", "rolling"):
            self.assertIsNone(_parse_amount(bad))


if __name__ == "__main__":
    unittest.main()
