#!/usr/bin/env python3
"""
Google Search Logger → OpenClaw Workspace

Captures Google search queries from local Chrome history and writes them
to daily Markdown files in:

    ~/.openclaw/workspace/google-searches/YYYY-MM-DD.md

Each entry format:

    HH:MM:SS — [web] search query
    HH:MM:SS — [image] image search query

If a daily file does not yet exist, the logger creates it with a simple header:

    # Google Searches
    Date: YYYY-MM-DD

Design goals:
- simple
- local-first
- append-only
- stdlib only
- safe reading of Chrome's SQLite history DB via a copied temp file
- avoid duplicate writes even if history is replayed or state is reset
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, unquote_plus, urlparse


CHROME_USER_DATA_DIR = Path(
    "~/Library/Application Support/Google/Chrome"
).expanduser()

OUTPUT_DIR = Path("~/.openclaw/workspace/google-searches").expanduser()
STATE_FILE = Path("~/.google_search_logger_state.json").expanduser()

INTERVAL_SECONDS = 60
DEDUPE_MINUTES = 10

GOOGLE_SEARCH_HOSTS = {
    "www.google.com",
    "google.com",
    "images.google.com",
}

LOG_LINE_RE = re.compile(
    r"^(?P<time>\d{2}:\d{2}:\d{2})\s+—\s+(?:\[(?P<tag>[a-z]+)\]\s+)?(?P<query>.+?)\s*$"
)


class GracefulExit(SystemExit):
    pass


def _handle_signal(signum, _frame):
    raise GracefulExit(f"Received signal {signum}")


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def chrome_time_to_datetime(microseconds: int) -> datetime:
    chrome_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    return chrome_epoch + timedelta(microseconds=microseconds)


def normalize_query(query: str) -> str:
    return " ".join(query.strip().split()).lower()


def classify_google_search(url: str) -> Optional[dict]:
    """
    Returns a dict like:
        {"query": "...", "search_type": "web"}
        {"query": "...", "search_type": "image"}

    Practical heuristic:
    - Any recognized Google search URL with a q=... param is a search
    - images.google.com => image search
    - tbm=isch => image search
    - udm=2 => image search
    - otherwise => web search
    """
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return None

        hostname = (parsed.hostname or "").lower()
        if hostname not in GOOGLE_SEARCH_HOSTS:
            return None

        if hostname == "images.google.com":
            allowed_paths = {"/", "/search"}
        else:
            allowed_paths = {"/search"}

        if parsed.path not in allowed_paths:
            return None

        params = parse_qs(parsed.query)
        if "q" not in params:
            return None

        query = unquote_plus(params["q"][0]).strip()
        if not query:
            return None

        tbm = params.get("tbm", [""])[0].strip().lower()
        udm = params.get("udm", [""])[0].strip().lower()

        if hostname == "images.google.com" or tbm == "isch" or udm == "2":
            search_type = "image"
        else:
            search_type = "web"

        return {
            "query": query,
            "search_type": search_type,
        }

    except Exception:
        return None


def discover_profile_name() -> str:
    env_profile = os.getenv("GOOGLE_SEARCH_LOGGER_PROFILE", "").strip()

    if env_profile:
        history_path = CHROME_USER_DATA_DIR / env_profile / "History"
        if history_path.exists():
            return env_profile
        raise FileNotFoundError(
            f"GOOGLE_SEARCH_LOGGER_PROFILE was set to {env_profile!r}, "
            f"but no History file exists at {history_path}"
        )

    default_history = CHROME_USER_DATA_DIR / "Default" / "History"
    if default_history.exists():
        return "Default"

    if CHROME_USER_DATA_DIR.exists():
        for child in sorted(CHROME_USER_DATA_DIR.iterdir()):
            if child.is_dir() and child.name.startswith("Profile "):
                history_path = child / "History"
                if history_path.exists():
                    return child.name

    raise FileNotFoundError(
        "Could not find a Chrome History file. Check chrome://version for Profile Path, "
        "or set GOOGLE_SEARCH_LOGGER_PROFILE."
    )


def history_path_for_profile(profile_name: str) -> Path:
    return CHROME_USER_DATA_DIR / profile_name / "History"


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {
            "last_visit_time": 0,
            "dedupe": {},
            "profile_name": None,
        }

    with STATE_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    data.setdefault("last_visit_time", 0)
    data.setdefault("dedupe", {})
    data.setdefault("profile_name", None)
    return data


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    tmp.replace(STATE_FILE)


def prune_dedupe_map(state: dict) -> None:
    cutoff = datetime.now().astimezone() - timedelta(minutes=DEDUPE_MINUTES * 3)
    keep = {}
    for key, iso_ts in state.get("dedupe", {}).items():
        try:
            dt = datetime.fromisoformat(iso_ts)
        except Exception:
            continue
        if dt >= cutoff:
            keep[key] = iso_ts
    state["dedupe"] = keep


def ensure_daily_file(path: Path, day: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return

    header = f"# Google Searches\nDate: {day.date().isoformat()}\n\n"
    with path.open("w", encoding="utf-8") as f:
        f.write(header)


def line_already_present(path: Path, query: str, dt: datetime) -> bool:
    """
    Returns True if the exact same timestamp + query already exists in the file,
    regardless of whether the existing line is legacy:
        HH:MM:SS — query
    or tagged:
        HH:MM:SS — [web] query
        HH:MM:SS — [image] query
    """
    if not path.exists():
        return False

    target_time = dt.strftime("%H:%M:%S")
    target_query = normalize_query(query)

    try:
        with path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                m = LOG_LINE_RE.match(raw_line.strip())
                if not m:
                    continue
                if m.group("time") != target_time:
                    continue
                if normalize_query(m.group("query")) == target_query:
                    return True
    except Exception:
        return False

    return False


def write_search(query: str, search_type: str, dt: datetime) -> bool:
    """
    Writes the line and returns True if a new line was appended.
    Returns False if the entry already exists.
    """
    date_file = OUTPUT_DIR / f"{dt.date().isoformat()}.md"
    ensure_daily_file(date_file, dt)

    if line_already_present(date_file, query, dt):
        return False

    time_str = dt.strftime("%H:%M:%S")
    line = f"{time_str} — [{search_type}] {query}\n"

    with date_file.open("a", encoding="utf-8") as f:
        f.write(line)

    return True


def query_history(history_file: Path, last_visit_time: int):
    with tempfile.TemporaryDirectory(prefix="chrome-history-copy-") as tmpdir:
        copied = Path(tmpdir) / "History"
        shutil.copy2(history_file, copied)

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


def main() -> int:
    state = load_state()
    profile_name = discover_profile_name()
    history_file = history_path_for_profile(profile_name)
    state["profile_name"] = profile_name

    print("google_search_logger starting", flush=True)
    print(f"Python executable: {sys.executable}", flush=True)
    print(f"Machine: {socket.gethostname()}", flush=True)
    print(f"Chrome profile: {profile_name}", flush=True)
    print(f"Chrome history file: {history_file}", flush=True)
    print(f"Output dir: {OUTPUT_DIR}", flush=True)
    print(f"State file: {STATE_FILE}", flush=True)

    try:
        while True:
            prune_dedupe_map(state)
            rows = query_history(history_file, int(state["last_visit_time"]))
            max_seen = int(state["last_visit_time"])

            for visit_time, url in rows:
                result = classify_google_search(url)
                if not result:
                    if int(visit_time) > max_seen:
                        max_seen = int(visit_time)
                    continue

                query = result["query"]
                search_type = result["search_type"]
                dt = chrome_time_to_datetime(int(visit_time)).astimezone()
                dedupe_key = f"{search_type}::{normalize_query(query)}"

                last_seen_iso = state["dedupe"].get(dedupe_key)
                if last_seen_iso:
                    try:
                        last_seen_dt = datetime.fromisoformat(last_seen_iso)
                        if dt - last_seen_dt < timedelta(minutes=DEDUPE_MINUTES):
                            if int(visit_time) > max_seen:
                                max_seen = int(visit_time)
                            continue
                    except Exception:
                        pass

                wrote = write_search(query, search_type, dt)
                state["dedupe"][dedupe_key] = dt.isoformat()

                if wrote:
                    print(
                        f"[logged] {dt.strftime('%Y-%m-%d %H:%M:%S')} — [{search_type}] {query}",
                        flush=True,
                    )
                else:
                    print(
                        f"[skipped-duplicate] {dt.strftime('%Y-%m-%d %H:%M:%S')} — [{search_type}] {query}",
                        flush=True,
                    )

                if int(visit_time) > max_seen:
                    max_seen = int(visit_time)

            state["last_visit_time"] = max_seen
            save_state(state)
            time.sleep(INTERVAL_SECONDS)

    except GracefulExit as exc:
        print(f"Shutting down: {exc}", flush=True)
        save_state(state)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
