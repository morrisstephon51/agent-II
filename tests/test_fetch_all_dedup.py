"""
Guard: fetch_all() must not silently drop grants that have no URL.

Some Granted-API rows omit url/link/source_url, so Grant.url == "". The dedup
key in fetch_all() is derived from the URL; a URL-less grant yields an empty
key. The bug treated an empty key as a reason to DROP the grant entirely, so a
real grant (valid title/deadline/award) never reached scoring, the report, or
the deadline-alert email. These tests pin the correct behaviour: URL-less
grants are deduped on a source+title fallback and KEPT, while real duplicates
(by URL or by source+title) still collapse.
"""
import unittest

from grant_agent import scraper
from grant_agent.models import Grant


def _g(title, url, source="TestFunder"):
    # deadline=None keeps is_recent() True so the age filter never removes it.
    return Grant(title=title, url=url, source=source, description="d", deadline=None)


class FetchAllDedupTest(unittest.TestCase):
    def setUp(self):
        self._orig = (
            scraper.fetch_granted,
            scraper.fetch_nsf_sbir,
            scraper.fetch_scraped_sources,
        )

    def tearDown(self):
        (
            scraper.fetch_granted,
            scraper.fetch_nsf_sbir,
            scraper.fetch_scraped_sources,
        ) = self._orig

    def _patch(self, grants):
        scraper.fetch_granted = lambda: list(grants)
        scraper.fetch_nsf_sbir = lambda: []
        scraper.fetch_scraped_sources = lambda: []

    def test_url_less_grant_is_kept(self):
        self._patch([
            _g("Has URL", "https://example.org/a"),
            _g("Empty URL Grant", "", source="Woods Fund"),
        ])
        result = scraper.fetch_all()
        titles = {g.title for g in result}
        self.assertIn("Empty URL Grant", titles)  # dropped on buggy
        self.assertEqual(len(result), 2)

    def test_distinct_url_less_grants_both_kept(self):
        self._patch([
            _g("Empty A", "", source="Woods Fund"),
            _g("Empty B", "", source="NSF"),
        ])
        result = scraper.fetch_all()
        self.assertEqual(len(result), 2)  # buggy returns 0

    def test_identical_url_less_grants_collapse(self):
        self._patch([
            _g("Same", "", source="Woods Fund"),
            _g("Same", "", source="Woods Fund"),
        ])
        result = scraper.fetch_all()
        self.assertEqual(len(result), 1)  # fixed=1, buggy=0

    def test_url_dedup_still_works(self):
        # Regression guard: trailing-slash URL dup still collapses (green both ways).
        self._patch([
            _g("Dup", "https://example.org/a"),
            _g("Dup slash", "https://example.org/a/"),
        ])
        result = scraper.fetch_all()
        self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
