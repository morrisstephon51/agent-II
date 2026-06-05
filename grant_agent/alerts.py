"""
Alert layer: stdout ⚠️ block + Composio Gmail email for near-deadline grants.
Email is only sent if ALERT_EMAIL and COMPOSIO_API_KEY are set.
"""
import sys
from datetime import date
from pathlib import Path

import httpx

from .config import ALERT_DAYS, ALERT_EMAIL, COMPOSIO_API_KEY
from .models import ScoredGrant


def _send_composio_email(subject: str, body: str) -> bool:
    if not COMPOSIO_API_KEY or not ALERT_EMAIL:
        return False
    try:
        r = httpx.post(
            "https://backend.composio.dev/api/v2/actions/GMAIL_SEND_EMAIL/execute",
            headers={
                "X-API-Key": COMPOSIO_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "input": {
                    "recipient_email": ALERT_EMAIL,
                    "subject": subject,
                    "body": body,
                    "is_html": False,
                }
            },
            timeout=20,
        )
        if r.status_code in (200, 201):
            data = r.json()
            return data.get("successfull") or data.get("success") or data.get("executed", False)
        else:
            print(f"[alerts] Composio email failed: {r.status_code} {r.text[:200]}", file=sys.stderr)
    except Exception as exc:
        print(f"[alerts] Composio email error: {exc}", file=sys.stderr)
    return False


def check_and_alert(scored_grants: list[ScoredGrant], report_path: Path) -> None:
    urgent = [sg for sg in scored_grants if sg.is_urgent(ALERT_DAYS)]

    if not urgent:
        print("[alerts] No grants within 30-day deadline window.")
        return

    # ── Stdout alert ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("⚠️  DEADLINE ALERT — Grants due within 30 days")
    print("=" * 60)
    for sg in sorted(urgent, key=lambda s: s.grant.deadline):
        days_left = sg.grant.days_until_deadline()
        print(
            f"  [{sg.fit_score}/10] {sg.grant.title}\n"
            f"          Source: {sg.grant.source}\n"
            f"          Deadline: {sg.deadline_str()} ({days_left} days)\n"
            f"          URL: {sg.grant.url}\n"
        )
    print("=" * 60 + "\n")

    # ── Composio email ──────────────────────────────────────────────────────
    if not ALERT_EMAIL:
        print("[alerts] ALERT_EMAIL not set — skipping email notification.")
        return

    subject = f"⚠️ Grant Deadline Alert — {len(urgent)} grant(s) due within 30 days [{date.today()}]"

    body_lines = [
        f"Grant Deadline Alert — {date.today()}",
        f"The following {len(urgent)} grant(s) have deadlines within the next 30 days:\n",
    ]
    for sg in sorted(urgent, key=lambda s: s.grant.deadline):
        days_left = sg.grant.days_until_deadline()
        body_lines += [
            f"Grant: {sg.grant.title}",
            f"Source: {sg.grant.source}",
            f"Fit Score: {sg.fit_score}/10",
            f"Deadline: {sg.deadline_str()} ({days_left} days remaining)",
            f"Award: {sg.grant.award_range_str()}",
            f"URL: {sg.grant.url}",
            f"\nWhy You Qualify:\n{sg.qualification_summary}",
            "-" * 50,
        ]
    body_lines.append(f"\nFull report: {report_path}")

    sent = _send_composio_email(subject, "\n".join(body_lines))
    if sent:
        print(f"[alerts] Email sent to {ALERT_EMAIL} via Composio.")
    else:
        print("[alerts] Email not sent (check COMPOSIO_API_KEY / ALERT_EMAIL).")
