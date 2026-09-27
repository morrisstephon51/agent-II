"""
Guard: a source that answers with an HTTP error must not manufacture a grant.

Regression under test
---------------------
``_html_scrape`` used to ``return r.text`` without inspecting ``r.status_code``.
Because servers answer 403/404 with a full HTML error page, the caller's
``if not html:`` check could never be true for an errored source. Two things
followed:

  1. ``fallback_url`` was unreachable config -- measured live 2026-09-27, it
     fired for 0 of the 4 HTML targets in ``SCRAPE_TARGETS``.
  2. ``_extract_grants_from_html`` fabricated one Grant per dead source from the
     error page's own text, which then reached the Claude scorer, the ranked
     report table (with a dead link), and potentially a deadline-alert email.
     Live bodies observed: "Error 404 - Woods Fund Chicago ... Page not found"
     and "Enable JavaScript and cookies to continue".

Run standalone (no pytest needed):
    python -m unittest discover -s tests -v
"""
import unittest
from unittest import mock

from grant_agent import scraper

# A non-empty error-page body: the whole point is that length alone is no signal.
ERROR_PAGE = (
    "<html><body><h1>404 ERROR</h1><p>Page not found. The page you are looking "
    "for doesn't exist. Applications are due January 15, 2027 for $500,000."
    "</p></body></html>"
)
GRANT_PAGE = (
    "<html><body><h1>Apply for funding</h1><p>Community technology grants. "
    "Deadline: March 3, 2027. Awards up to $250,000.</p></body></html>"
)


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


def _responder(mapping, default=(404, ERROR_PAGE)):
    """httpx.get stub driven by a {url: (status, text)} mapping."""
    def _get(url, *args, **kwargs):
        status, text = mapping.get(url, default)
        return FakeResponse(status, text)
    return _get


class HtmlScrapeStatusGuard(unittest.TestCase):
    def test_non_200_with_nonempty_body_returns_empty(self):
        """An error page is not content, however long its body is."""
        with mock.patch.object(
            scraper.httpx, "get", _responder({"http://dead/": (404, ERROR_PAGE)})
        ):
            self.assertEqual(scraper._html_scrape("http://dead/"), "")

    def test_403_returns_empty(self):
        with mock.patch.object(
            scraper.httpx, "get", _responder({"http://forbidden/": (403, ERROR_PAGE)})
        ):
            self.assertEqual(scraper._html_scrape("http://forbidden/"), "")

    def test_200_returns_body(self):
        """Positive control: the guard must not swallow live pages."""
        with mock.patch.object(
            scraper.httpx, "get", _responder({"http://live/": (200, GRANT_PAGE)})
        ):
            self.assertEqual(scraper._html_scrape("http://live/"), GRANT_PAGE)


class DeadSourceYieldsNothing(unittest.TestCase):
    TARGETS = [
        {
            "source": "Dead Funder",
            "url": "http://dead/apply/",
            "fallback_url": "http://dead/",
        }
    ]

    def test_dead_primary_and_dead_fallback_yield_zero_grants(self):
        """No grant may be fabricated out of an error page."""
        mapping = {"http://dead/apply/": (404, ERROR_PAGE), "http://dead/": (404, ERROR_PAGE)}
        with mock.patch.object(scraper, "SCRAPE_TARGETS", self.TARGETS), \
             mock.patch.object(scraper.httpx, "get", _responder(mapping)):
            grants = scraper.fetch_scraped_sources()
        self.assertEqual(
            grants, [], f"fabricated {len(grants)} grant(s) from an HTTP error page"
        )

    def test_error_page_never_becomes_a_grant_description(self):
        """Belt-and-braces: assert on the artifact a human would read."""
        mapping = {"http://dead/apply/": (404, ERROR_PAGE), "http://dead/": (404, ERROR_PAGE)}
        with mock.patch.object(scraper, "SCRAPE_TARGETS", self.TARGETS), \
             mock.patch.object(scraper.httpx, "get", _responder(mapping)):
            grants = scraper.fetch_scraped_sources()
        for g in grants:
            self.assertNotIn("404", g.description)
            self.assertNotIn("Page not found", g.description)


class FallbackUrlIsReachable(unittest.TestCase):
    TARGETS = [
        {
            "source": "Recovering Funder",
            "url": "http://funder/apply/",
            "fallback_url": "http://funder/grantmaking/",
        }
    ]

    def test_fallback_fires_when_primary_errors(self):
        """The documented fallback_url knob must actually be used."""
        mapping = {
            "http://funder/apply/": (404, ERROR_PAGE),
            "http://funder/grantmaking/": (200, GRANT_PAGE),
        }
        with mock.patch.object(scraper, "SCRAPE_TARGETS", self.TARGETS), \
             mock.patch.object(scraper.httpx, "get", _responder(mapping)):
            grants = scraper.fetch_scraped_sources()
        self.assertEqual(len(grants), 1, "fallback_url did not recover the source")
        self.assertNotIn("404", grants[0].description)
        self.assertIn("Community technology", grants[0].description)

    def test_recovered_grant_links_to_the_page_that_served_content(self):
        """A recovered grant must not carry the dead primary URL."""
        mapping = {
            "http://funder/apply/": (404, ERROR_PAGE),
            "http://funder/grantmaking/": (200, GRANT_PAGE),
        }
        with mock.patch.object(scraper, "SCRAPE_TARGETS", self.TARGETS), \
             mock.patch.object(scraper.httpx, "get", _responder(mapping)):
            grants = scraper.fetch_scraped_sources()
        self.assertEqual(grants[0].url, "http://funder/grantmaking/")


if __name__ == "__main__":
    unittest.main()
