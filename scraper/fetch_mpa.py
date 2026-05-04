"""
Fetchers for the MPA data sources.

Two sources:
    1. mpareports.com — Heal Point rankings (sport/class/region/date range).
    2. mpaschedules.org — per-team schedules and results.

Both return raw HTML; parsing is deferred to parse_mpa.py so we can cache
raw pages and re-parse without re-hitting the network while developing.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Optional

import requests

from config import (
    CACHE_DIR,
    CLASS_B_CLASSIFICATION_ID,
    MPA_REPORTS_BASE,
    MPA_SCHED_AGLS,
    MPA_SCHED_GENIE,
    MPA_SCHED_SEASON,
    MPA_SCHEDULES_BASE,
    NORTH_REGION_ID,
    REQUEST_DELAY_SECONDS,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    SEASON_END,
    SEASON_START,
    SEASON_YEAR,
    SOFTBALL_SPORT_ID,
)


class FetchError(RuntimeError):
    pass


def _cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{digest}.html"


def _polite_get(url: str, params: Optional[dict] = None, use_cache: bool = True, max_age_seconds: int = 60 * 60 * 3) -> str:
    """
    GET with a polite delay, a descriptive user-agent, and an optional on-disk
    cache. The cache is especially useful while iterating on the parser so we
    don't pound MPA's servers.
    """
    final_url = url
    if params:
        prepped = requests.Request("GET", url, params=params).prepare()
        final_url = prepped.url

    cache_file = _cache_path(final_url)
    if use_cache and cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age <= max_age_seconds:
            return cache_file.read_text(encoding="utf-8")

    time.sleep(REQUEST_DELAY_SECONDS)
    resp = requests.get(final_url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        raise FetchError(f"HTTP {resp.status_code} fetching {final_url}")
    text = resp.text
    if use_cache:
        cache_file.write_text(text, encoding="utf-8")
    return text


def fetch_class_b_north_standings(
    *,
    season_year: int = SEASON_YEAR,
    season_start: str = SEASON_START,
    season_end: str = SEASON_END,
    classification_id: int = CLASS_B_CLASSIFICATION_ID,
    region_id: int = NORTH_REGION_ID,
) -> str:
    """
    Fetch Class B North softball Heal Point standings HTML from mpareports.com.

    Targets the /reports/rankingslist endpoint directly (not the JS loader at
    /reports/loadreport — that shell page just does an AJAX call to rankingslist
    so we cut out the middleman).

    Returns the raw HTML fragment — see parse_mpa.parse_standings().
    Keyword arguments override the config defaults for multi-season backfills.
    """
    params = {
        "start-date": season_start,
        "end-date": season_end,
        "year": str(season_year),
        "sportId": str(SOFTBALL_SPORT_ID),
        "classificationId": str(classification_id),
        "regionId": str(region_id),
        "getLatest": "1",
        "report-type": "2",
    }
    return _polite_get(MPA_REPORTS_BASE, params=params)


def fetch_team_schedule(
    schedule_id: str,
    *,
    sched_genie: str = MPA_SCHED_GENIE,
    sched_agls: str = MPA_SCHED_AGLS,
    sched_season: str = MPA_SCHED_SEASON,
) -> str:
    """
    Fetch a team's score/standings page from mpaschedules.org.

    URL pattern:
      /public/scorestanding/list/genie/{genie}/school/{schedule_id}
        /agls/{agls}/{season}/lowerschool/0

    Keyword arguments override the config defaults for multi-season backfills.
    """
    url = (
        f"{MPA_SCHEDULES_BASE}/public/scorestanding/list"
        f"/genie/{sched_genie}"
        f"/school/{schedule_id}"
        f"/agls/{sched_agls}"
        f"/{sched_season}"
        f"/lowerschool/0"
    )
    return _polite_get(url)


MPA_CC_BASE = "https://www.mpa.cc"


def fetch_mpa_cc_schedule(school_id: int, sport_id: str) -> str:
    """
    Fetch a team's season schedule from mpa.cc/DashboardSchedule.aspx.

    URL: /DashboardSchedule.aspx?SportID={sport_id}&SchoolID={school_id}&QuickFilter=3
    QuickFilter=3 returns "All Games" for the school's current sport season.
    """
    url = f"{MPA_CC_BASE}/DashboardSchedule.aspx"
    params = {
        "SportID": sport_id,
        "SchoolID": str(school_id),
        "QuickFilter": "3",
    }
    return _polite_get(url, params=params)


if __name__ == "__main__":
    # Quick CLI smoke test — `python fetch_mpa.py` pulls the standings and
    # prints the first 1000 chars so you can confirm the shape of the data.
    html = fetch_class_b_north_standings()
    print(f"Fetched {len(html)} bytes")
    print(html[:1000])
