#!/usr/bin/env python3

"""
Google Search Logger → OpenClaw Workspace

Captures Google search queries from Chrome history and writes them
to daily Markdown files in:

~/.openclaw/workspace/google-searches/YYYY-MM-DD.md

Each entry format:

HH:MM:SS — search query

Key improvements in v2:
- auto-discovers Chrome profiles instead of assuming Default
- clearer startup diagnostics
- safer handling when Chrome history path is missing
- optional override via env vars
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlparse

DEFAULT_USER_DATA_DIR = Path("~/Library/Application Support/Google/Chrome").expanduser()
OUTPUT_DIR = Path("~/.openclaw/workspace/google-searches").expanduser()
STATE_FILE = Path("~/.google_search_logger_state.json").expanduser()
INTERVAL_SECONDS = 60
DEDUPE_MINUTES = 10

# Optional overrides
USER_DATA_DIR = Path(os.getenv("GOOGLE_SEARCH_LOGGER_USER_DATA_DIR", str(DEFAULT_USER_DATA_DIR))).expanduser()
PROFILE_OVERRIDE = os.getenv("GOOGLE_SEARCH_LOGGER_PROFILE", "").strip()


class GracefulExit(SystemExit):
    pass


def _handle_signal(signum, _frame):
    raise GracefulExit(f"received signal {signum}")


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def chrome_time_to_datetime(microseconds: int) -> datetime:
    chrome_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    return chrome_epoch + timedelta(microseconds=microseconds)


def normalize_query(q: str) -> str:
    return " ".join(q.strip().split()).lower()


def extract_google_query(url: str) -> str | None:
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()

        if hostname not in {"www.google.com", "google.com"}:
            return None

        if parsed.path != "/search":
            return None

        params = parse_qs(parsed.query)
        values = params.get("q")
        if not values:
            return None

        q = unquote_plus(values[0]).strip()
        return q or None
    except Exception:
        return None


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"profiles": {}, "dedupe": {}}

    with open(STATE_FILE, encoding="utf-8") as f:
        state = json.load(f)

    if "profiles" not in state:
        # migrate from old single-profile format
        last_visit_time = int(state.get("last_visit_time", 0))
        state = {
            "profiles": {"Default": {"last_visit_time": last_visit_time}},
            "dedupe": state.get("dedupe", {}),
        }

    state.setdefault("profiles", {})
    state.setdefault("dedupe", {})
    return state


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def write_search(query: str, dt: datetime) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_file = OUTPUT_DIR / f"{dt.date().isoformat()}.md"
    time_str = dt.strftime("%H:%M:%S")
    line = f"{time_str} — {query}\n"
    with open(date_file, "a", encoding="utf-8") as f:
        f.write(line)


def discover_profiles() -> list[str]:
    if PROFILE_OVERRIDE:
        history = USER_DATA_DIR / PROFILE_OVERRIDE / "History"
        if history.exists():
            return [PROFILE_OVERRIDE]
        raise FileNotFoundError(
            f"GOOGLE_SEARCH_LOGGER_PROFILE={PROFILE_OVERRIDE!r} was set, but no History file exists at {history}"
        )

    if not USER_DATA_DIR.exists():
        raise FileNotFoundError(
            f"Chrome user data directory not found: {USER_DATA_DIR}\n"
            "If Chrome is installed in a different place/profile, set GOOGLE_SEARCH_LOGGER_USER_DATA_DIR."
        )

    profiles: list[str] = []
    for child in sorted(USER_DATA_DIR.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if name == "Default" or name.startswith("Profile "):
            history = child / "History"
            if history.exists():
                profiles.append(name)

    if not profiles:
        raise FileNotFoundError(
            f"No Chrome profiles with a History DB were found under {USER_DATA_DIR}.\n"
            "Open chrome://version and check 'Profile Path', then either:\n"
            "1) set GOOGLE_SEARCH_LOGGER_PROFILE to that profile directory name, or\n"
            "2) set GOOGLE_SEARCH_LOGGER_USER_DATA_DIR if Chrome uses a different base directory."
        )

    return profiles


def query_history(history_path: Path, last_visit_time: int):
    with tempfile.TemporaryDirectory() as tmpdir:
        copied = Path(tmpdir) / "History"
        shutil.copy2(history_path, copied)

        conn = sqlite3.connect(f"file:{copied}?mode=ro", uri=True)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT last_visit_time, url
                FROM urls
                WHERE last_visit_time > ?
                ORDER BY last_visit_time ASC
                """,
                (last_visit_time,),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

    return rows


def cleanup_dedupe(dedupe: dict[str, str]) -> None:
    cutoff = datetime.now().astimezone() - timedelta(minutes=DEDUPE_MINUTES * 3)
    stale = []
    for key, value in dedupe.items():
        try:
            dt = datetime.fromisoformat(value)
        except Exception:
            stale.append(key)
            continue
        if dt < cutoff:
            stale.append(key)
    for key in stale:
        dedupe.pop(key, None)


def print_startup_info(profiles: list[str]) -> None:
    print("Google Search Logger starting")
    print(f"Chrome user data dir: {USER_DATA_DIR}")
    print(f"Detected profiles: {', '.join(profiles)}")
    print(f"Output dir: {OUTPUT_DIR}")
    print(f"State file: {STATE_FILE}")
    print(f"Poll interval: {INTERVAL_SECONDS}s")
    print(f"Hostname: {socket.gethostname()}")


def main() -> int:
    state = load_state()

    try:
        profiles = discover_profiles()
    except FileNotFoundError as e:
        print("\nERROR: Could not find Chrome history to read.\n")
        print(str(e))
        print("\nMost likely cause: your active Chrome profile is not 'Default'.")
        print("Fix:")
        print("- Open chrome://version")
        print("- Look at 'Profile Path'")
        print("- Export GOOGLE_SEARCH_LOGGER_PROFILE to that directory name")
        print("  Example: export GOOGLE_SEARCH_LOGGER_PROFILE='Profile 1'")
        return 2

    print_startup_info(profiles)

    try:
        while True:
            cleanup_dedupe(state["dedupe"])

            for profile in profiles:
                history_path = USER_DATA_DIR / profile / "History"
                profile_state = state["profiles"].setdefault(profile, {"last_visit_time": 0})
                last_visit_time = int(profile_state.get("last_visit_time", 0))

                rows = query_history(history_path, last_visit_time)
                max_seen = last_visit_time

                for visit_time, url in rows:
                    query = extract_google_query(url)
                    if visit_time > max_seen:
                        max_seen = visit_time
                    if not query:
                        continue

                    dt = chrome_time_to_datetime(visit_time).astimezone()
                    key = f"{profile}::{normalize_query(query)}"
                    last_seen = state["dedupe"].get(key)

                    if last_seen:
                        try:
                            last_dt = datetime.fromisoformat(last_seen)
                            if dt - last_dt < timedelta(minutes=DEDUPE_MINUTES):
                                continue
                        except Exception:
                            pass

                    write_search(query, dt)
                    state["dedupe"][key] = dt.isoformat()
                    print(f"[logged:{profile}] {dt.strftime('%Y-%m-%d %H:%M:%S')} — {query}")

                profile_state["last_visit_time"] = max_seen

            save_state(state)
            time.sleep(INTERVAL_SECONDS)

    except GracefulExit:
        save_state(state)
        print("Shutting down cleanly.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
