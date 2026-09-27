"""The scorer must survive a Claude response of any shape.

`score_grants` catches every exception around the API call and falls back to
`_placeholder_scores`, but it used to consume the parsed JSON *outside* that
try/except: `{item["index"]: item for item in scored_data}`. A response that
was valid JSON but not the promised array of `{"index", "fit_score",
"qualification_summary"}` objects therefore crashed the run after the API had
already been billed, or silently discarded every score.

Each test below is a payload shape measured against the real scorer.
"""
import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:  # keep the suite runnable without the SDK installed
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    sys.modules["anthropic"] = types.SimpleNamespace(Anthropic=object)

from grant_agent.models import Grant  # noqa: E402
from grant_agent import scorer  # noqa: E402

NEUTRAL_SCORE = 5
PLACEHOLDER_SUMMARY = "Score unavailable — manual review recommended."
NO_API_KEY_MARKER = "no API key"


class _FakeAnthropic:
    """Stands in for anthropic.Anthropic and replays a scripted response."""

    raw = "[]"

    def __init__(self, api_key=None):
        self.messages = self

    def create(self, **kwargs):
        block = types.SimpleNamespace(text=self.raw)
        return types.SimpleNamespace(content=[block])


def score(raw, count=2):
    """Run the real score_grants against a scripted model response."""
    grants = [
        Grant(title=f"Grant {i}", url=f"https://example.test/{i}",
              source="Test Source", description="description")
        for i in range(count)
    ]
    fake = type("Scripted", (_FakeAnthropic,), {"raw": raw})
    with mock.patch.object(scorer.anthropic, "Anthropic", fake), \
            mock.patch.object(scorer, "ANTHROPIC_API_KEY", "sk-test"):
        results = scorer.score_grants(grants)
    return {sg.grant.title: sg for sg in results}


class ScorerParseTests(unittest.TestCase):

    def test_valid_payload_scores_are_passed_through(self):
        """Positive control: a well-formed response must be untouched."""
        by_title = score(json.dumps([
            {"index": 0, "fit_score": 9, "qualification_summary": "strong fit"},
            {"index": 1, "fit_score": 3, "qualification_summary": "weak fit"},
        ]))
        self.assertEqual(by_title["Grant 0"].fit_score, 9)
        self.assertEqual(by_title["Grant 0"].qualification_summary, "strong fit")
        self.assertEqual(by_title["Grant 1"].fit_score, 3)
        self.assertEqual(by_title["Grant 1"].qualification_summary, "weak fit")

    def test_results_are_ranked_high_to_low(self):
        results_by_title = score(json.dumps([
            {"index": 0, "fit_score": 2, "qualification_summary": "low"},
            {"index": 1, "fit_score": 8, "qualification_summary": "high"},
        ]))
        self.assertEqual(
            [sg.fit_score for sg in results_by_title.values()], [8, 2],
            "score_grants must still return grants sorted by fit_score desc",
        )

    def test_array_wrapped_in_an_object_does_not_crash(self):
        """The model ignoring 'return ONLY a JSON array' used to be a TypeError."""
        by_title = score(json.dumps(
            {"grants": [{"index": 0, "fit_score": 9,
                         "qualification_summary": "strong fit"}]}
        ))
        self.assertEqual(by_title["Grant 0"].fit_score, 9)
        self.assertEqual(by_title["Grant 0"].qualification_summary, "strong fit")

    def test_entry_missing_index_does_not_crash_the_run(self):
        """One bad entry used to raise KeyError and kill the whole report."""
        by_title = score(json.dumps([
            {"fit_score": 9, "qualification_summary": "no index here"},
            {"index": 1, "fit_score": 4, "qualification_summary": "has index"},
        ]))
        self.assertEqual(by_title["Grant 0"].fit_score, NEUTRAL_SCORE)
        self.assertEqual(by_title["Grant 0"].qualification_summary,
                         PLACEHOLDER_SUMMARY)
        self.assertEqual(by_title["Grant 1"].fit_score, 4,
                         "a usable sibling entry must keep its real score")

    def test_string_index_still_maps_to_its_grant(self):
        """'0' never equals 0, so every real score was silently discarded."""
        by_title = score(json.dumps([
            {"index": "0", "fit_score": 9, "qualification_summary": "strong fit"},
            {"index": "1", "fit_score": 8, "qualification_summary": "good fit"},
        ]))
        self.assertEqual(by_title["Grant 0"].fit_score, 9)
        self.assertEqual(by_title["Grant 1"].fit_score, 8)
        self.assertNotIn(PLACEHOLDER_SUMMARY,
                         [sg.qualification_summary for sg in by_title.values()])

    def test_non_numeric_fit_score_does_not_crash(self):
        """int('high') used to raise ValueError outside the try/except."""
        by_title = score(json.dumps([
            {"index": 0, "fit_score": "high", "qualification_summary": "kept"},
            {"index": 1, "fit_score": 7, "qualification_summary": "fine"},
        ]))
        self.assertEqual(by_title["Grant 0"].fit_score, NEUTRAL_SCORE)
        self.assertEqual(by_title["Grant 0"].qualification_summary, "kept",
                         "an unusable score must not discard a usable summary")
        self.assertEqual(by_title["Grant 1"].fit_score, 7)

    def test_fit_score_is_clamped_to_the_declared_rubric(self):
        """The 1-10 rubric is told to the model but was never enforced in code."""
        by_title = score(json.dumps([
            {"index": 0, "fit_score": 95, "qualification_summary": "off scale"},
            {"index": 1, "fit_score": 0, "qualification_summary": "below scale"},
        ]))
        self.assertEqual(by_title["Grant 0"].fit_score, 10)
        self.assertEqual(by_title["Grant 1"].fit_score, 1)

    def test_scalar_payload_yields_neutral_scores(self):
        by_title = score("7")
        self.assertEqual([sg.fit_score for sg in by_title.values()],
                         [NEUTRAL_SCORE, NEUTRAL_SCORE])

    def test_list_of_non_objects_does_not_crash(self):
        by_title = score(json.dumps([1, 2]))
        self.assertEqual([sg.fit_score for sg in by_title.values()],
                         [NEUTRAL_SCORE, NEUTRAL_SCORE])

    def test_non_string_summary_is_replaced(self):
        """A dict here would be f-strung straight into the report and the email."""
        by_title = score(json.dumps([
            {"index": 0, "fit_score": 8, "qualification_summary": {"text": "oops"}},
        ]))
        self.assertEqual(by_title["Grant 0"].qualification_summary,
                         PLACEHOLDER_SUMMARY)

    def test_non_finite_number_is_dropped_like_any_other_bad_value(self):
        """json.loads accepts NaN and Infinity, and int() of either raises."""
        by_title = score('[{"index": NaN, "fit_score": 1, '
                         '"qualification_summary": "x"}, '
                         '{"index": 1, "fit_score": 6, '
                         '"qualification_summary": "kept"}]')
        self.assertEqual(by_title["Grant 0"].fit_score, NEUTRAL_SCORE)
        self.assertEqual(by_title["Grant 1"].fit_score, 6,
                         "one non-finite value must not cost the other grants")

    def test_a_parse_failure_falls_back_instead_of_propagating(self):
        """Pins the placement, not the parser.

        Every use of the model's output has to sit inside the try/except that
        owns _placeholder_scores. _parse_scores handles the shapes known today;
        the next unforeseen one must degrade the report, not kill the run after
        the API call has already been billed.
        """
        payload = json.dumps([{"index": 0, "fit_score": 9,
                               "qualification_summary": "strong fit"}])
        with mock.patch.object(scorer, "_parse_scores",
                               side_effect=RuntimeError("unforeseen shape")):
            by_title = score(payload)
        self.assertEqual(by_title["Grant 0"].fit_score, NEUTRAL_SCORE)
        self.assertIn(NO_API_KEY_MARKER.split()[0],
                      by_title["Grant 0"].qualification_summary)

    def test_unparseable_json_still_uses_placeholder_scores(self):
        """The pre-existing fallback must survive the change."""
        by_title = score("not json at all")
        self.assertEqual(by_title["Grant 0"].fit_score, NEUTRAL_SCORE)
        self.assertIn(NO_API_KEY_MARKER.split()[0],
                      by_title["Grant 0"].qualification_summary)


if __name__ == "__main__":
    unittest.main()
