"""
Guard: scoring a normal-size fetch must not hit max_tokens.

The fake client behaves like the API at the output cap: it renders the full JSON
array the model would write, then cuts it at max_tokens (~4 chars per token).
One request for 60 grants (fetch_all can return ~84) is truncated, json.loads fails, and every grant comes
back as a placeholder 5/10. Batched requests each fit and keep their real scores.
"""
import json
import unittest
from types import SimpleNamespace
from unittest import mock

from grant_agent import scorer
from grant_agent.models import Grant

SUMMARY = (
    "The organization delivers AI literacy workshops to residents of south suburban "
    "Cook County, which matches this program's focus on equitable access to emerging "
    "technology. Its community partners and nonprofit status meet the eligibility "
    "rules, and the planned curriculum maps directly to the funded activities."
)


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, *, max_tokens, messages, **_):
        prompt = messages[0]["content"]
        count = prompt.count("    TITLE: ")
        self.calls.append(count)
        full = json.dumps(
            [{"index": i, "fit_score": 8, "qualification_summary": SUMMARY} for i in range(count)],
            indent=2,
        )
        text = full[: max_tokens * 4]
        return SimpleNamespace(
            content=[SimpleNamespace(text=text)],
            stop_reason="max_tokens" if len(text) < len(full) else "end_turn",
        )


class FakeClient:
    def __init__(self, *_, **__):
        self.messages = FakeMessages()


def grants(n):
    return [Grant(title=f"Grant {i}", url=f"https://example.org/{i}", source="Test",
                  description="AI education") for i in range(n)]


class ScorerBatchingTest(unittest.TestCase):
    def run_scorer(self, n):
        fake = FakeClient()
        with mock.patch.object(scorer, "ANTHROPIC_API_KEY", "test-key"), \
             mock.patch.object(scorer.anthropic, "Anthropic", return_value=fake):
            return scorer.score_grants(grants(n)), fake.messages.calls

    def test_sixty_grants_all_keep_real_scores(self):
        results, _ = self.run_scorer(60)
        self.assertEqual(len(results), 60)
        self.assertEqual([r.fit_score for r in results], [8] * 60)
        self.assertTrue(all(r.qualification_summary == SUMMARY for r in results))

    def test_every_grant_is_scored_exactly_once(self):
        results, calls = self.run_scorer(23)
        self.assertEqual(sorted(r.grant.title for r in results),
                         sorted(f"Grant {i}" for i in range(23)))
        self.assertEqual(sum(calls), 23)
        self.assertTrue(all(c <= scorer.SCORE_BATCH_SIZE for c in calls))

    def test_batch_size_fits_output_budget(self):
        _, calls = self.run_scorer(scorer.SCORE_BATCH_SIZE)
        self.assertEqual(calls, [scorer.SCORE_BATCH_SIZE])


if __name__ == "__main__":
    unittest.main()
