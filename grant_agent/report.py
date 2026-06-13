"""Markdown report generator."""
import os
from datetime import date
from pathlib import Path
from typing import List

from .config import ALERT_DAYS, SCORE_BOLD_THRESHOLD
from .models import ScoredGrant

REPORTS_DIR = Path(__file__).parent.parent / "reports"


def generate(scored_grants: list[ScoredGrant]) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    today = date.today().strftime("%Y-%m-%d")
    path = REPORTS_DIR / f"grants-{today}.md"

    urgent = [sg for sg in scored_grants if sg.is_urgent(ALERT_DAYS)]
    lines: list[str] = []

    lines.append(f"# Grant Opportunities Report — {today}\n")
    lines.append(f"**Mission:** AI education and community literacy platform targeting underserved "
                 f"communities in Chicago south suburban Cook County\n")
    lines.append(f"**Total grants found:** {len(scored_grants)}  ")
    lines.append(f"**Deadlines within {ALERT_DAYS} days:** {len(urgent)}\n")

    # ── Deadline alert block ────────────────────────────────────────────────
    if urgent:
        lines.append("---\n")
        lines.append("## ⚠️ DEADLINE ALERTS\n")
        for sg in sorted(urgent, key=lambda s: s.grant.deadline):
            days_left = sg.grant.days_until_deadline()
            lines.append(
                f"- **{sg.grant.title}** ({sg.grant.source}) — "
                f"**{days_left} days left** — Deadline: {sg.deadline_str()} — "
                f"[Source]({sg.grant.url})"
            )
        lines.append("")

    # ── Ranked summary table ────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## Ranked Grant List\n")
    lines.append("| Rank | Score | Grant | Source | Deadline | Award Range | URL |")
    lines.append("|------|-------|-------|--------|----------|-------------|-----|")
    for rank, sg in enumerate(scored_grants, 1):
        title = f"**{sg.grant.title}**" if sg.fit_score >= SCORE_BOLD_THRESHOLD else sg.grant.title
        score = f"**{sg.fit_score}/10**" if sg.fit_score >= SCORE_BOLD_THRESHOLD else f"{sg.fit_score}/10"
        lines.append(
            f"| {rank} | {score} | {title} | {sg.grant.source} | "
            f"{sg.deadline_str()} | {sg.grant.award_range_str()} | [Link]({sg.grant.url}) |"
        )
    lines.append("")

    # ── Per-grant detail sections ───────────────────────────────────────────
    lines.append("---\n")
    lines.append("## Grant Details\n")
    for rank, sg in enumerate(scored_grants, 1):
        urgency = " ⚠️" if sg.is_urgent(ALERT_DAYS) else ""
        lines.append(f"### {rank}. {sg.grant.title}{urgency}")
        lines.append(f"- **Source:** {sg.grant.source}")
        lines.append(f"- **Fit Score:** {sg.fit_score}/10")
        lines.append(f"- **Deadline:** {sg.deadline_str()}")
        lines.append(f"- **Award Range:** {sg.grant.award_range_str()}")
        lines.append(f"- **URL:** {sg.grant.url}")
        lines.append(f"\n**Why You Qualify:**\n{sg.qualification_summary}\n")
        if sg.grant.description:
            lines.append(f"**Grant Description:**\n> {sg.grant.description[:400]}...\n")
        lines.append("")

    lines.append("---")
    lines.append(f"*Report generated {today}. Grants older than 90 days excluded.*")

    content = "\n".join(lines)
    path.write_text(content, encoding="utf-8")
    print(f"[report] Saved → {path}")
    return path
