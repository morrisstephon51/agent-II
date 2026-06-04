#!/usr/bin/env python3
"""
Grant Agent CLI
Usage:
  python main.py              # run once now
  python main.py --cron       # install weekly Monday 8am cron entry
  python main.py --dry-run    # scrape + score but don't save report or send email
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path


def run(dry_run: bool = False) -> None:
    start = time.time()
    print("=" * 60)
    print("Grant Agent — The Plug AI")
    print("=" * 60)

    from grant_agent.scraper import fetch_all
    from grant_agent.scorer import score_grants
    from grant_agent.report import generate
    from grant_agent.alerts import check_and_alert

    print("\n[1/4] Scraping grant sources...")
    grants = fetch_all()
    if not grants:
        print("No grants found. Check network connectivity and API keys.")
        sys.exit(0)

    print(f"\n[2/4] Scoring {len(grants)} grants with Claude...")
    scored = score_grants(grants)

    if dry_run:
        print("\n[dry-run] Results (not saved):\n")
        for sg in scored:
            print(f"  {sg.fit_score}/10  {sg.grant.title} — {sg.deadline_str()}")
        elapsed = time.time() - start
        print(f"\nDone in {elapsed:.1f}s")
        return

    print("\n[3/4] Generating report...")
    report_path = generate(scored)

    print("\n[4/4] Checking deadline alerts...")
    check_and_alert(scored, report_path)

    elapsed = time.time() - start
    print(f"\nDone in {elapsed:.1f}s  |  Report: {report_path}")


def install_cron() -> None:
    script = Path(__file__).resolve()
    python = sys.executable
    cron_line = f"0 8 * * 1 cd {script.parent} && {python} {script} >> {script.parent}/grant_agent.log 2>&1"

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = result.stdout if result.returncode == 0 else ""

    if cron_line in existing:
        print("Cron job already installed.")
        return

    new_crontab = existing.rstrip("\n") + "\n" + cron_line + "\n"
    proc = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
    if proc.returncode == 0:
        print(f"Cron installed: {cron_line}")
    else:
        print(f"Failed to install cron: {proc.stderr}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant Agent — The Plug AI")
    parser.add_argument("--cron", action="store_true", help="Install weekly Monday 8am cron job")
    parser.add_argument("--dry-run", action="store_true", help="Run without saving report or sending email")
    args = parser.parse_args()

    if args.cron:
        install_cron()
    else:
        run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
