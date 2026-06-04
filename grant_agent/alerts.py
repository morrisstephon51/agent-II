"""
Alert layer: stdout ⚠️ block + free Gmail SMTP email via stdlib smtplib.
No paid services required. Set SMTP_USER, SMTP_PASS, ALERT_EMAIL to enable email.
"""
import smtplib
import sys
from datetime import date
from email.mime.text import MIMEText
from pathlib import Path

from .config import ALERT_DAYS, ALERT_EMAIL, SMTP_HOST, SMTP_PASS, SMTP_PORT, SMTP_USER
from .models import ScoredGrant


def _send_email(subject: str, body: str) -> bool:
    if not (SMTP_USER and SMTP_PASS and ALERT_EMAIL):
        return False
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.sendmail(SMTP_USER, [ALERT_EMAIL], msg.as_string())
        return True
    except Exception as exc:
        print(f"[alerts] Email failed: {exc}", file=sys.stderr)
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

    # ── SMTP email ──────────────────────────────────────────────────────────
    if not ALERT_EMAIL:
        print("[alerts] ALERT_EMAIL not set — skipping email notification.")
        return

    subject = f"⚠️ Grant Deadline Alert — {len(urgent)} grant(s) due within 30 days [{date.today()}]"
    body_lines = [
        f"Grant Deadline Alert — {date.today()}",
        f"{len(urgent)} grant(s) have deadlines within the next 30 days:\n",
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

    sent = _send_email(subject, "\n".join(body_lines))
    if sent:
        print(f"[alerts] Email sent to {ALERT_EMAIL}.")
    else:
        print("[alerts] Email not sent (set SMTP_USER, SMTP_PASS, ALERT_EMAIL to enable).")
