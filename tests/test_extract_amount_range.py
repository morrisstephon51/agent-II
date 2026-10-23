"""
Guard: _extract_grants_from_html must map an explicit "$X to $Y" award range to
award_min=X / award_max=Y.

Regression for the bug where amount extraction ran a single re.search for the
FIRST dollar figure on the page and stored it in award_max. A grant page stating
"$50,000 to $250,000" therefore kept the MINIMUM ($50,000) in award_max and left
award_min unset, so Grant.award_range_str() reported "Up to $50,000" -- the value
that then flows into both the human report and the Claude scorer prompt (the AWARD
line), understating the real ceiling 5x and skewing ranking.

Single-amount pages must keep their old behaviour (award_max only). Standard
library unittest, no network -- HTML is passed to the extractor directly.
"""
import unittest

from grant_agent.scraper import _extract_grants_from_html


def _one(html: str):
    grants = _extract_grants_from_html(html, "Test Source", "https://example.org/grant")
    assert len(grants) == 1, grants
    return grants[0]


class ExtractAmountRange(unittest.TestCase):
    def test_dollar_range_maps_min_and_max(self):
        g = _one("<p>Awards range from $50,000 to $250,000 per project.</p>")
        self.assertEqual(g.award_min, 50_000)
        self.assertEqual(g.award_max, 250_000)
        self.assertEqual(g.award_range_str(), "$50,000–$250,000")

    def test_en_dash_suffix_range(self):
        g = _one("<p>Grant size: $50K–$250K.</p>")
        self.assertEqual(g.award_min, 50_000)
        self.assertEqual(g.award_max, 250_000)

    def test_between_and_million_range(self):
        g = _one("<p>Funding is between $1.5 million and $3 million.</p>")
        self.assertEqual(g.award_min, 1_500_000)
        self.assertEqual(g.award_max, 3_000_000)

    def test_single_amount_unchanged(self):
        g = _one("<p>Award up to $100,000.</p>")
        self.assertIsNone(g.award_min)
        self.assertEqual(g.award_max, 100_000)
        self.assertEqual(g.award_range_str(), "Up to $100,000")

    def test_no_amount_is_none(self):
        g = _one("<p>Award amount not specified.</p>")
        self.assertIsNone(g.award_min)
        self.assertIsNone(g.award_max)


if __name__ == "__main__":
    unittest.main()
