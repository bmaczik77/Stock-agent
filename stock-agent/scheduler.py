#!/usr/bin/env python3
"""
Scheduler — automatically run stock analysis on a daily schedule.

Reads the watchlist and schedule settings from config.json, then
runs reports for every ticker at the configured time each trading day.
"""

import json
import logging
import smtplib
import sys
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import schedule

from agent import generate_report, load_config, print_report, save_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Job
# ------------------------------------------------------------------


def run_analysis_job():
    """Execute analysis for every ticker on the watchlist."""
    config = load_config()
    sched_cfg = config.get("scheduler", {})
    watchlist = sched_cfg.get("watchlist", [])

    if not watchlist:
        logger.warning("Watchlist is empty — nothing to analyse.")
        return

    logger.info("Starting scheduled analysis for %d tickers", len(watchlist))

    reports = []
    for ticker in watchlist:
        try:
            report = generate_report(ticker, config)
            print_report(report)
            save_report(report, config.get("report_output_dir", "reports"))
            reports.append(report)
        except Exception as exc:
            logger.error("Failed to analyse %s: %s", ticker, exc)

    # Optional e-mail notification
    if sched_cfg.get("email_notifications") and reports:
        send_email_summary(reports, sched_cfg)

    logger.info("Scheduled run complete — %d/%d reports generated",
                len(reports), len(watchlist))


# ------------------------------------------------------------------
# E-mail notifications
# ------------------------------------------------------------------


def send_email_summary(reports: list[dict], sched_cfg: dict):
    """Send a summary e-mail with all recommendations."""
    smtp_server = sched_cfg.get("smtp_server", "")
    smtp_port = sched_cfg.get("smtp_port", 587)
    email_from = sched_cfg.get("email_from", "")
    email_to = sched_cfg.get("email_to", "")

    if not all([smtp_server, email_from, email_to]):
        logger.warning("E-mail settings incomplete — skipping notification.")
        return

    subject = f"Stock Analysis Report — {datetime.now():%Y-%m-%d}"
    body_lines = [f"Daily Stock Analysis Report — {datetime.now():%Y-%m-%d %H:%M}\n"]

    for r in reports:
        ticker = r.get("ticker", "???")
        rec = r.get("overall_recommendation", "N/A")
        price = r.get("technical", {}).get("current_price", "N/A")
        body_lines.append(f"  {ticker:6s}  ${price}  →  {rec}")

    body_lines.append(f"\n{len(reports)} reports saved to disk.")
    body = "\n".join(body_lines)

    msg = MIMEMultipart()
    msg["From"] = email_from
    msg["To"] = email_to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.send_message(msg)
        logger.info("Summary e-mail sent to %s", email_to)
    except Exception as exc:
        logger.error("Failed to send e-mail: %s", exc)


# ------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------


def main():
    config = load_config()
    sched_cfg = config.get("scheduler", {})
    run_time = sched_cfg.get("schedule_time", "08:00")
    tz_name = sched_cfg.get("timezone", "US/Eastern")

    logger.info("Scheduler started — will run daily at %s (%s)", run_time, tz_name)
    logger.info("Watchlist: %s", sched_cfg.get("watchlist", []))

    schedule.every().day.at(run_time).do(run_analysis_job)

    # Also offer an immediate run via --now flag
    if "--now" in sys.argv:
        logger.info("Immediate run requested (--now flag)")
        run_analysis_job()

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")


if __name__ == "__main__":
    main()
