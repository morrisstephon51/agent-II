"""
Claude API scorer. Sends all grants in one batched prompt, returns ScoredGrant list.
Uses claude-sonnet-4-6 with prompt caching on the system prompt.
"""
import json
import sys
from typing import Optional

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

    # Build the user message listing all grants
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
                    "cache_control": {"type": "ephemeral"},  # cache system prompt
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

        scored_data = json.loads(raw)
    except Exception as exc:
        print(f"[scorer] Claude API call failed: {exc}", file=sys.stderr)
        return _placeholder_scores(grants)

    results: list[ScoredGrant] = []
    score_map: dict[int, dict] = {item["index"]: item for item in scored_data}
    for i, g in enumerate(grants):
        item = score_map.get(i, {})
        results.append(
            ScoredGrant(
                grant=g,
                fit_score=int(item.get("fit_score", 5)),
                qualification_summary=item.get(
                    "qualification_summary",
                    "Score unavailable — manual review recommended.",
                ),
            )
        )

    results.sort(key=lambda s: s.fit_score, reverse=True)
    return results


def _placeholder_scores(grants: list[Grant]) -> list[ScoredGrant]:
    """Fallback when API key is absent — assigns neutral scores so report still renders."""
    import random
    results = [
        ScoredGrant(
            grant=g,
            fit_score=5,
            qualification_summary=(
                "Automated scoring unavailable (no API key). "
                "Manual review required. "
                f"Grant from {g.source} — see {g.url}"
            ),
        )
        for g in grants
    ]
    results.sort(key=lambda s: s.grant.deadline or __import__("datetime").date.max)
    return results


# Fix missing import in score_grants
import re
