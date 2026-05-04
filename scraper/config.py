"""
Configuration for the Class B North Softball dashboard scraper.

Season-specific values (dateId, year, etc.) may need to be updated each
season. The team list is defined here so the dashboard knows which teams
belong to Class B North.

If any of the MPA URL parameters change (they occasionally do season to
season), update the constants below.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BASE_DATA_DIR = PROJECT_ROOT / "site" / "data"
CACHE_DIR = PROJECT_ROOT / ".cache"

# Season-specific data lives under site/data/{SEASON_YEAR}/
# DATA_DIR is set after SEASON_YEAR is defined below.

# ---------------------------------------------------------------------------
# MPA Reports endpoint
# ---------------------------------------------------------------------------
# The MPA publishes Heal Point standings through mpareports.com. The URL
# takes query parameters for sport, classification, region, and date range.
#
# Observed example:
#   https://mpareports.com/reports/loadreport?dateId=607&
#     start-date=2025-04-17&end-date=2025-06-04&year=2025&
#     sportId=10&classificationId=3000001516&regionId=3000001506&
#     getLatest=1&targetReport=/reports/rankingslist&report-type=2
#
# These IDs were observed for the 2025 season and may shift slightly each
# year. Update SEASON_YEAR and verify the ID values at the start of each
# spring season by loading the Varsity Softball rankings page and copying
# the URL.
# MPA exposes the actual data via /reports/rankingslist (not /reports/loadreport,
# which is just a JS loader shell that does an AJAX call to rankingslist).
MPA_REPORTS_BASE = "https://mpareports.com/reports/rankingslist"

# SEASON_YEAR corresponds to the MPA "year" URL param.  MPA labels Spring 2024
# (April–June 2024) as year=2024.  Spring 2026 data has not been published yet
# as of April 2026 (too early in the season / MPA hasn't configured it yet).
# Update to 2025 (or whatever year MPA starts publishing) once it appears.
SEASON_YEAR = 2026

SOFTBALL_SPORT_ID = 10
# Class B classification ID changes each two-year cycle.
#   school-year=2023 (Spring 2023): 1000006992
#   school-year=2024 (Spring 2024): 3000001518  ← current
# If MPA changes IDs again, fetch the filter page as described in README.
CLASS_B_CLASSIFICATION_ID = 3000001518
NORTH_REGION_ID = 3000001506

SEASON_START = f"{SEASON_YEAR}-04-17"
SEASON_END = f"{SEASON_YEAR}-06-04"

# Season-specific output directory; created on import.
DATA_DIR = _BASE_DATA_DIR / str(SEASON_YEAR)
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# MPA Schedules (per team schedule + results)
# ---------------------------------------------------------------------------
# mpaschedules.org exposes per-team schedule pages. URL structure is
# typically: https://mpaschedules.org/g5-bin/client.cgi?G5genie=...
# We'll store the schedule URL per team in TEAMS below.
MPA_SCHEDULES_BASE = "https://mpaschedules.org"

# ---------------------------------------------------------------------------
# Class B North Softball teams
# ---------------------------------------------------------------------------
# Source: MPA /reports/rankingslist for year=2024, classificationId=3000001518,
# regionId=3000001506 (verified April 2026).
#
# MPA reclassifies every two years. The 2023-24 / 2024-25 cycle teams are
# listed below.  When the MPA publishes the 2025-26 standings, compare and
# update as needed.
#
# Fields:
#   key             internal slug used throughout the codebase
#   name            display name (as shown on MPA)
#   city            city/town
#   mpa_tr_id       MPA table-row ID from the North rankings table
#   schedule_id     mpaschedules.org school ID (for scorestanding/list URLs)
#   maxpreps_slug   URL slug for MaxPreps scouting page
TEAMS = [
    {
        "key": "nokomis",
        "name": "Nokomis Regional",
        "city": "Newport",
        "mpa_tr_id": "78557000",
        "schedule_id": "1645",
        "mpa_cc_school_id": 39,
        "maxpreps_slug": "nokomis-regional-warriors",
    },
    {
        "key": "oldtown",
        "name": "Old Town",
        "city": "Old Town",
        "mpa_tr_id": "115541200",
        "schedule_id": "2539",
        "mpa_cc_school_id": 123,
        "maxpreps_slug": "old-town-coyotes",
    },
    {
        "key": "ellsworth",
        "name": "Ellsworth/George Stevens",
        "city": "Ellsworth",
        "mpa_tr_id": "78797700",
        "schedule_id": "2227",
        "mpa_cc_school_id": 87,
        "maxpreps_slug": "ellsworth-eagles",
    },
    {
        "key": "hermon",
        "name": "Hermon",
        "city": "Hermon",
        "mpa_tr_id": "92006100",
        "schedule_id": "2331",
        "mpa_cc_school_id": 98,
        "maxpreps_slug": "hermon-hawks",
    },
    {
        "key": "belfast",
        "name": "Belfast Area",
        "city": "Belfast",
        "mpa_tr_id": "78401000",
        "schedule_id": "1525",
        "mpa_cc_school_id": 28,
        "maxpreps_slug": "belfast-area-lions",
    },
    {
        "key": "mdi",
        "name": "MDI High School",
        "city": "Bar Harbor",
        "mpa_tr_id": "210357100",
        "schedule_id": "2483",
        "mpa_cc_school_id": 309,
        "maxpreps_slug": "mount-desert-island-trojans",
    },
    {
        "key": "cony",
        "name": "Cony",
        "city": "Augusta",
        "mpa_tr_id": "78425000",
        "schedule_id": "2116",
        "mpa_cc_school_id": 73,
        "maxpreps_slug": "cony-rams",
    },
    {
        "key": "oceanside",
        "name": "Oceanside",
        "city": "Rockland",
        "mpa_tr_id": "78564600",
        "schedule_id": "1693",
        "mpa_cc_school_id": 43,
        "maxpreps_slug": "oceanside-mariners",
    },
    {
        "key": "presque_isle",
        "name": "Presque Isle",
        "city": "Presque Isle",
        "mpa_tr_id": "148457000",
        "schedule_id": "1765",
        "mpa_cc_school_id": 49,
        "maxpreps_slug": "presque-isle-wildcats",
    },
    {
        "key": "lawrence",
        "name": "Lawrence",
        "city": "Fairfield",
        "mpa_tr_id": "135764300",
        "schedule_id": "2379",
        "mpa_cc_school_id": 103,
        "maxpreps_slug": "lawrence-bulldogs",
    },
    {
        "key": "john_bapst",
        "name": "John Bapst",
        "city": "Bangor",
        "mpa_tr_id": "139871800",
        "schedule_id": "2355",
        "mpa_cc_school_id": 100,
        "maxpreps_slug": "john-bapst-memorial-crusaders",
    },
    {
        "key": "caribou",
        "name": "Caribou",
        "city": "Caribou",
        "mpa_tr_id": "78770900",
        "schedule_id": "1985",
        "mpa_cc_school_id": 64,
        "maxpreps_slug": "caribou-vikings",
    },
    {
        "key": "waterville",
        "name": "Waterville",
        "city": "Waterville",
        "mpa_tr_id": "78596100",
        "schedule_id": "1549",
        "mpa_cc_school_id": 31,
        "maxpreps_slug": "waterville-purple-panthers",
    },
    {
        "key": "winslow",
        "name": "Winslow",
        "city": "Winslow",
        "mpa_tr_id": "67129500",
        "schedule_id": "1585",
        "mpa_cc_school_id": 34,
        "maxpreps_slug": "winslow-black-raiders",
    },
    # Joined Class B North starting in the 2025-26 school year (Spring 2026)
    {
        "key": "foxcroft",
        "name": "Foxcroft Academy",
        "city": "Dover-Foxcroft",
        "mpa_tr_id": "",
        "schedule_id": "",
        "mpa_cc_school_id": 130,
        "maxpreps_slug": "foxcroft-academy-ponies",
    },
    {
        "key": "gardiner",
        "name": "Gardiner Area",
        "city": "Gardiner",
        "mpa_tr_id": "",
        "schedule_id": "",
        "mpa_cc_school_id": 92,
        "maxpreps_slug": "gardiner-area-tigers",
    },
]

# Season/activity IDs used by mpaschedules.org scorestanding/list URLs.
# Pattern: /public/scorestanding/list/genie/1142/school/{schedule_id}/agls/{SCHED_AGLS}/{SCHED_SEASON}/...
# Verified for Spring 2024. Update if MPA changes IDs for the new season.
MPA_SCHED_GENIE = "1142"
MPA_SCHED_AGLS = "154"
MPA_SCHED_SEASON = "1/161/139"  # 1=most-recent flag, 161/139=season internal IDs

# Heal point values per opponent class (for softball — same values used for
# most non-football sports in Maine).
HEAL_POINTS_PER_CLASS = {
    "A": 40,
    "B": 35,
    "C": 30,
    "D": 25,
}

# HTTP request settings
REQUEST_HEADERS = {
    "User-Agent": (
        "Class-B-North-Softball-Dashboard/1.0 "
        "(coaching tool; contact: jeremiah.johnson01@mymail.champlain.edu)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
REQUEST_TIMEOUT = 20  # seconds
REQUEST_DELAY_SECONDS = 1.5  # polite delay between requests

# ---------------------------------------------------------------------------
# Per-year override map for season-specific MPA URL parameters
# ---------------------------------------------------------------------------
# When build_data.py is run with --year <Y>, any keys present here replace
# the module-level defaults for that year. Update each spring by loading the
# MPA varsity softball rankings page and copying the URL parameters.
#
# MPA_SCHED_AGLS and MPA_SCHED_SEASON are internal mpaschedules.org IDs that
# may change each season. Verify them from the schedule page URL if fetches
# return empty data.
YEAR_OVERRIDES: dict = {
    2024: {
        "CLASS_B_CLASSIFICATION_ID": 3000001518,
        "SEASON_START": "2024-04-17",
        "SEASON_END": "2024-06-04",
        "MPA_SCHED_AGLS": "154",
        "MPA_SCHED_SEASON": "1/161/139",
    },
    2025: {
        # classificationId=3000001516 observed in MPA URL example for 2025.
        # Verify MPA_SCHED_AGLS and MPA_SCHED_SEASON from the live schedule URL.
        "CLASS_B_CLASSIFICATION_ID": 3000001516,
        "SEASON_START": "2025-04-17",
        "SEASON_END": "2025-06-04",
        "MPA_SCHED_AGLS": "154",
        "MPA_SCHED_SEASON": "1/161/139",
    },
    2026: {
        # New two-year classification cycle (2025-26 school year).
        # Schedules come from mpa.cc (mpaschedules.org does not carry 2026 data).
        # MPA standings classification ID is unknown until MPA publishes it mid-season.
        "schedule_source": "mpa_cc",
        "mpa_cc_sport_id": "3_1031_5",  # Girls Softball Varsity, Spring 2026
        "SEASON_START": "2026-04-17",
        "SEASON_END": "2026-06-10",
        # Teams active in Class B North for Spring 2026 (reclassification changed
        # from 2024: Winslow → Class C; Foxcroft Academy + Gardiner Area added).
        "team_keys": [
            "belfast", "caribou", "cony", "ellsworth", "foxcroft", "gardiner",
            "hermon", "john_bapst", "lawrence", "mdi", "nokomis", "oceanside",
            "oldtown", "presque_isle", "waterville",
        ],
    },
}
