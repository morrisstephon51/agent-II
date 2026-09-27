"""
Claude API scorer using claude-sonnet-4-6.
Sends all grants in one batched prompt with prompt caching on the system prompt.
"""
import json
import re
import sys

import anthropic

from .config import ANTHROPIC_API_KEY, CLAUDE_MODEL, MISSION
from .models import Grant, ScoredGrant

_SYSTEM = f"""You are a grant-fit analyst for a nonprofit technology organization.

Organization mission: {MISSION}

For each grant, you will:
1. Score fit 1–10 (10 = perfect mission alignment + eligibility match)
   Scoring rubric:
   - 9-10: Direct AI/tech education + underserved/equity focus + Chicago/Illinois eligible
   - 7-8:  AI or education focus + equity/community angle, geography flexible
   - 5-6:  Partial overlap (e.g. workforce training OR community tech, not both)
   - 3-4:  Tangential connection, worth monitoring
   - 1-2:  Misaligned (wrong sector, geography locked out, or nonprofit ineligible)
2. Write one paragraph (3-5 sentences) explaining exactly WHY the org qualifies,
   citing specific mission elements that map to grant criteria.

Return ONLY a JSON array. Each element:
{{
  "index": <int>,
  "fit_score": <int 1-10>,
  "qualification_summary": "<paragraph>"
}}
"""


def score_grants(grants: list[Grant]) -> list[ScoredGrant]:
    if not grants:
        return []

    if not ANTHROPIC_API_KEY:
        print("[scorer] ANTHROPIC_API_KEY not set — using placeholder scores", file=sys.stderr)
        return _placeholder_scores(grants)

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    lines = []
    for i, g in enumerate(grants):
        lines.append(
            f"[{i}] SOURCE: {g.source}\n"
            f"    TITLE: {g.title}\n"
            f"    URL: {g.url}\n"
            f"    DEADLINE: {g.deadline or 'Unknown'}\n"
            f"    AWARD: {g.award_range_str()}\n"
            f"    DESCRIPTION: {g.description[:500]}\n"
        )
    user_content = "Score each grant below:\n\n" + "\n".join(lines)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        scored_data = json.loads(raw)
        score_map = _parse_scores(scored_data)
    except Exception as exc:
        print(f"[scorer] Claude API call failed: {exc}", file=sys.stderr)
        return _placeholder_scores(grants)

    if not score_map:
        print(
            "[scorer] No usable scores in the Claude response — every grant "
            "falls back to a neutral score",
            file=sys.stderr,
        )

    results: list[ScoredGrant] = []
    for i, g in enumerate(grants):
        item = score_map.get(i, {})
        score = _coerce_int(item.get("fit_score"))
        summary = item.get("qualification_summary")
        results.append(
            ScoredGrant(
                grant=g,
                # The rubric is 1-10; the model is not bound by it, so clamp.
                fit_score=5 if score is None else max(1, min(10, score)),
                qualification_summary=(
                    summary
                    if isinstance(summary, str) and summary.strip()
                    else "Score unavailable — manual review recommended."
                ),
            )
        )

    results.sort(key=lambda s: s.fit_score, reverse=True)
    return results


def _coerce_int(value) -> int | None:
    """Model output is untyped JSON: accept 7, "7" and 7.0, reject "high"."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _parse_scores(payload) -> dict[int, dict]:
    """Map {grant index: score item} from a response of unverified shape.

    Called inside the try/except above so a malformed payload reaches the
    placeholder fallback instead of crashing the run after the API was billed.
    Individual unusable entries are dropped with a note on stderr rather than
    raised: the caller already defaults a missing index to a neutral score, so
    one bad entry costs one grant its score instead of the whole report.
    """
    if isinstance(payload, dict):
        # "Return ONLY a JSON array" is an instruction, not a guarantee; a
        # single wrapping key ({"grants": [...]}) is the usual deviation.
        payload = next((v for v in payload.values() if isinstance(v, list)), None)
    if not isinstance(payload, list):
        print(
            f"[scorer] Expected a JSON array of scores, got "
            f"{type(payload).__name__}",
            file=sys.stderr,
        )
        return {}

    score_map: dict[int, dict] = {}
    dropped = 0
    for item in payload:
        index = _coerce_int(item.get("index")) if isinstance(item, dict) else None
        if index is None:
            dropped += 1
            continue
        score_map[index] = item
    if dropped:
        print(
            f"[scorer] Dropped {dropped} score entr{'y' if dropped == 1 else 'ies'} "
            f"with a missing or non-numeric index",
            file=sys.stderr,
        )
    return score_map


def _placeholder_scores(grants: list[Grant]) -> list[ScoredGrant]:
    return [
        ScoredGrant(
            grant=g,
            fit_score=5,
            qualification_summary=(
                "Automated scoring unavailable (no API key). "
                f"Manual review required. See {g.url}"
            ),
        )
        for g in grants
    ]
