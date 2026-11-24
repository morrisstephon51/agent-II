"""
Guard: an API row with an explicit JSON null must not drop the batch or crash the run.

Granted / SBIR rows can carry a key whose value is null ("description": null).
item.get(key, "") returns None for a present-but-null key, so the old
`(item.get(a) or item.get(b, ""))[:800]` sliced None, the per-item loop raised
TypeError, and the surrounding except discarded EVERY grant in that response,
including good rows after the bad one. A null URL was worse: it reached
fetch_all() as None and `g.url.rstrip` crashed the whole run.
"""
import unittest
from unittest import mock

from grant_agent import scraper


class _Resp:
    status_code = 200

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def _get(data):
    return mock.patch.object(scraper.httpx, "get", return_value=_Resp(data))


class GrantedNullFieldsTest(unittest.TestCase):
    def test_null_description_row_keeps_whole_batch(self):
        rows = [
            {"title": "Null first", "url": "https://x/b", "deadline": "2026-12-20",
             "description": None, "summary": None},
            {"title": "Good after", "url": "https://x/a", "deadline": "2026-12-31",
             "description": "ok"},
        ]
        with _get({"results": rows}):
            grants = scraper._fetch_granted_query("q")
        self.assertEqual([g.title for g in grants], ["Null first", "Good after"])
        self.assertEqual(grants[0].description, "")

    def test_null_url_title_source_fall_back_to_strings(self):
        rows = [{"title": None, "name": None, "url": None, "link": None,
                 "source_url": None, "funder": None, "agency": None,
                 "award_max": None, "amount": "$50,000"}]
        with _get(rows):
            (g,) = scraper._fetch_granted_query("woods fund")
        self.assertEqual(g.title, "Unknown")
        self.assertEqual(g.url, "")
        self.assertEqual(g.source, "woods fund")
        self.assertEqual(g.award_max, 50000)


class SbirNullFieldsTest(unittest.TestCase):
    def test_null_description_row_keeps_whole_batch(self):
        rows = [
            {"solicitation_title": "SBIR B", "solicitation_url": "https://s/b",
             "close_date": "2026-12-15", "program_description": None, "description": None},
            {"solicitation_title": "SBIR A", "solicitation_url": "https://s/a",
             "close_date": "2026-12-31", "program_description": "p"},
        ]
        with _get(rows):
            grants = scraper.fetch_nsf_sbir()
        self.assertEqual([g.title for g in grants], ["SBIR B", "SBIR A"])

    def test_null_url_uses_default_and_fetch_all_survives(self):
        rows = [{"solicitation_title": "SBIR C", "solicitation_url": None, "url": None,
                 "close_date": None, "program_description": "p"}]
        with _get(rows):
            (g,) = scraper.fetch_nsf_sbir()
        self.assertEqual(g.url, "https://www.sbir.gov")
        with mock.patch.object(scraper, "fetch_granted", return_value=[]), \
             mock.patch.object(scraper, "fetch_nsf_sbir", return_value=[g]), \
             mock.patch.object(scraper, "fetch_scraped_sources", return_value=[]):
            self.assertEqual([x.title for x in scraper.fetch_all()], ["SBIR C"])


if __name__ == "__main__":
    unittest.main()
