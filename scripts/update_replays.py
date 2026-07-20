#!/usr/bin/env python3
"""
Power Hour replay updater.

Runs Fridays via GitHub Actions. Finds today's Power Hour recording in
Michelle's Grain workspace, grabs its share URL, and upserts it into
replays.json (keyed by date, so re-runs are harmless).

Env vars:
  GRAIN_API_TOKEN_V2  required - same token BIA's onboarding automation uses
  SLACK_WEBHOOK_URL   optional - posts a note on success or final failure
  FINAL_ATTEMPT       optional - "true" on the last cron slot of the day;
                      controls whether a miss is treated as a failure

Exit codes:
  0 = entry added, or already present, or not-found on a non-final attempt
  1 = hard error, or not-found on the final attempt
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

# Grain v2 public API. Recording search is a POST with a JSON filter body;
# this matches the contract BIA's client_onboarding.py already uses in prod.
GRAIN_RECORDINGS_URL = "https://api.grain.com/_/public-api/v2/recordings"
GRAIN_HEADERS = {
    "Authorization": f"Bearer {os.environ['GRAIN_API_TOKEN_V2']}",
    "Public-Api-Version": "2025-10-31",
    "Content-Type": "application/json",
}
REPLAYS_PATH = Path(__file__).resolve().parent.parent / "replays.json"
TITLE_KEYWORD = "power hour"  # case-insensitive; real title is "Coach Chelley's Power Hour"
ET = ZoneInfo("America/New_York")


def notify_slack(message: str) -> None:
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        return
    try:
        requests.post(url, json={"text": message}, timeout=10)
    except requests.RequestException:
        pass  # notifications are best-effort


def load_replays() -> dict:
    with open(REPLAYS_PATH) as f:
        return json.load(f)


def save_replays(data: dict) -> None:
    data["replays"].sort(key=lambda r: r["date"], reverse=True)
    with open(REPLAYS_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _recording_date_et(recording: dict) -> str | None:
    """Return the recording's start date (YYYY-MM-DD) in ET, or None."""
    raw = recording.get("start_datetime")
    if not raw:
        return None
    # Grain v2 returns ISO-8601, e.g. "2026-07-17T17:00:14Z".
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ET).strftime("%Y-%m-%d")


def fetch_todays_power_hour(today: str) -> dict | None:
    """Return the Grain recording dict for today's Power Hour, or None.

    `today` is a YYYY-MM-DD string in ET. Search is a POST with a title
    filter (Grain v2), then we keep only recordings that (a) contain the
    "Power Hour" keyword and (b) actually started today in ET.
    """
    resp = requests.post(
        GRAIN_RECORDINGS_URL,
        headers=GRAIN_HEADERS,
        json={"filter": {"title_search": "Power Hour"}},
        timeout=30,
    )
    resp.raise_for_status()
    recordings = resp.json().get("recordings", [])

    matches = [
        r for r in recordings
        if TITLE_KEYWORD in (r.get("title") or "").lower()
        and _recording_date_et(r) == today
    ]
    if not matches:
        return None
    # If somehow multiple today, take the most recent start.
    matches.sort(key=lambda r: r.get("start_datetime") or "", reverse=True)
    return matches[0]


def extract_share_url(recording: dict) -> str | None:
    """
    Pull the public share URL off the recording object. Grain's v2 recording
    objects expose it as `recording_url` (a .../share/recording/<id>/<token>
    link); older/related endpoints have used `url`. Check known keys and
    prefer an actual /share/ link so we never post an auth-gated workspace URL.
    """
    candidates = [
        recording.get(k)
        for k in ("recording_url", "url", "share_url", "public_url")
    ]
    candidates = [c for c in candidates if c and "grain.com" in c]
    if not candidates:
        return None
    for c in candidates:
        if "/share/" in c:
            return c
    return candidates[0]


def main() -> int:
    now_et = datetime.now(ET)
    today = now_et.strftime("%Y-%m-%d")
    final_attempt = os.environ.get("FINAL_ATTEMPT", "").lower() == "true"

    data = load_replays()

    # Idempotency: bail if today is already posted (earlier cron slot got it)
    if any(r["date"] == today for r in data["replays"]):
        print(f"Entry for {today} already exists. Nothing to do.")
        return 0

    try:
        recording = fetch_todays_power_hour(today)
    except requests.RequestException as e:
        print(f"Grain API error: {e}", file=sys.stderr)
        notify_slack(f":warning: Power Hour updater hit a Grain API error: {e}")
        return 1

    if recording is None:
        msg = f"No Power Hour recording found in Grain for {today} yet."
        print(msg)
        if final_attempt:
            notify_slack(
                f":x: Power Hour replay was NOT posted for {today} - "
                "no matching recording found in Grain by the last check. "
                "Check the recording title contains 'Power Hour', or add the link manually."
            )
            return 1
        return 0  # a later cron slot will retry

    share_url = extract_share_url(recording)
    if not share_url:
        rec_id = recording.get("id", "unknown")
        msg = (
            f"Found recording {rec_id} for {today} but it has no public share URL. "
            "The recording likely needs sharing enabled in Grain."
        )
        print(msg, file=sys.stderr)
        notify_slack(f":x: Power Hour updater: {msg}")
        return 1

    data["replays"].append({"date": today, "url": share_url})
    save_replays(data)
    print(f"Added {today} -> {share_url}")
    notify_slack(
        f":white_check_mark: Power Hour replay for {today} posted to "
        "bianutrition.com/ph-replays\n{0}".format(share_url)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
