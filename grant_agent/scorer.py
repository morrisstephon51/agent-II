"""
Keyword-based heuristic scorer. No API key or external service required.

Scoring rubric (1-10):
  +3  AI / machine learning / artificial intelligence keyword
  +2  Education / literacy / training / workforce
  +2  Equity / underserved / low-income / community / minority / BIPOC
  +1  Chicago / Illinois / Cook County geographic match
  +1  Nonprofit / community org / small business eligible
  +1  STEM / technology / digital literacy
  Clamp result to 1-10 range.
"""
import re
from .models import Grant, ScoredGrant

# (pattern, points, label)
_RULES: list[tuple[str, int, str]] = [
    (r"\b(artificial intelligence|machine learning|AI\b|deep learning|NLP|LLM)\b", 3, "AI/ML focus"),
    (r"\b(education|literacy|learning|curriculum|training|workforce development)\b", 2, "education focus"),
    (r"\b(underserved|equity|low.income|community|minority|BIPOC|marginalized|disadvantaged)\b", 2, "equity focus"),
    (r"\b(Chicago|Illinois|Cook County|Midwest)\b", 1, "geographic match"),
    (r"\b(nonprofit|non.profit|501.c|small business|SBIR|SBDC|community org)\b", 1, "nonprofit/SMB eligible"),
    (r"\b(STEM|technology|digital|innovation|tech)\b", 1, "STEM/tech alignment"),
]

_MISSION_KEYWORDS = [
    "AI education", "community literacy", "underserved", "Chicago",
    "south suburban", "Cook County", "workforce", "digital equity",
]


def _score_text(text: str) -> tuple[int, list[str]]:
    text_lower = text.lower()
    total = 0
    matched_labels: list[str] = []
    for pattern, pts, label in _RULES:
        if re.search(pattern, text, re.IGNORECASE):
            total += pts
            matched_labels.append(label)
    return max(1, min(10, total)), matched_labels


def _build_summary(grant: Grant, score: int, matched: list[str]) -> str:
    source_sentence = (
        f"This grant from {grant.source} aligns with The Plug AI's mission "
        f"based on the following criteria: {', '.join(matched) if matched else 'general community focus'}."
    )

    if score >= 8:
        strength = "strong"
        extra = (
            "The grant's emphasis on AI, education, and underserved communities directly mirrors "
            "The Plug AI's work delivering AI literacy programs to south suburban Cook County residents."
        )
    elif score >= 6:
        strength = "moderate"
        extra = (
            "The Plug AI's community-focused AI education platform demonstrates meaningful overlap "
            "with this funder's priorities, particularly around workforce development and digital equity."
        )
    elif score >= 4:
        strength = "partial"
        extra = (
            "While not a perfect fit, The Plug AI could frame its work around the workforce "
            "and community technology elements of this opportunity."
        )
    else:
        strength = "limited"
        extra = (
            "This grant has limited direct alignment with The Plug AI's current program model; "
            "significant proposal tailoring would be required."
        )

    award_note = (
        f"The award range of {grant.award_range_str()} would support program expansion. "
        if grant.award_max else ""
    )

    return f"{source_sentence} The fit is {strength}. {extra} {award_note}".strip()


def score_grants(grants: list[Grant]) -> list[ScoredGrant]:
    results: list[ScoredGrant] = []
    for g in grants:
        combined = f"{g.title} {g.description} {g.source}"
        score, matched = _score_text(combined)
        summary = _build_summary(g, score, matched)
        results.append(ScoredGrant(grant=g, fit_score=score, qualification_summary=summary))

    results.sort(key=lambda s: s.fit_score, reverse=True)
    return results
