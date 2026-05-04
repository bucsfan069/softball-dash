"""
HTML parsers for MPA pages.

MPA rankings page (/reports/rankingslist)
-----------------------------------------
The page renders a <table id="North"> (for the North region) containing:
  - Two header rows (colspan groupings, then column labels)
  - One data row per team: <tr id="{mpa_tr_id}" class="notSortable">
    The row has 23 cells, many hidden via style="display:none;".
    Visible cell positions (0-indexed among ALL cells, not just visible ones):
      0   Display order / rank
      1   School name (also contains an <a> with the scorestanding onclick)
      2-17  Per-game result columns (hidden)
      18  Wins (W)
      19  Losses (L)
      20  Ties (T)
      21  Preliminary Index
      22  Tournament Index

mpaschedules.org scorestanding/list page
-----------------------------------------
Returns an HTML table (.tbl-scores-standing) with columns:
  Date | Time | Event Type | Opponent | Loc. | Score | W/L/T | Comments
Data rows have class="table-data-styles".
A section header row (colspan=7) carries the season label ("Spring 2024").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup  # type: ignore


@dataclass
class StandingRow:
    rank: int
    team_name: str
    mpa_tr_id: str
    wins: int
    losses: int
    ties: int
    preliminary_index: Optional[float]
    tournament_index: Optional[float]


@dataclass
class ScheduleEntry:
    date: str                 # ISO YYYY-MM-DD
    opponent_name: str
    home_away: str            # "H" or "A" or ""
    result: Optional[str]     # "W" / "L" / "T" / None if not played
    score_for: Optional[int]
    score_against: Optional[int]


def _to_float(s: str) -> Optional[float]:
    try:
        cleaned = re.sub(r"[^0-9.\-]", "", s or "")
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _to_int(s: str, default: int = 0) -> int:
    try:
        cleaned = re.sub(r"[^0-9\-]", "", s or "")
        return int(cleaned) if cleaned else default
    except ValueError:
        return default


# Indices of the visible (not display:none) cells within a data row.
# Verified against live MPA HTML (April 2026).
_CELL_RANK   = 0
_CELL_NAME   = 1
_CELL_W      = 18
_CELL_L      = 19
_CELL_T      = 20
_CELL_PI     = 21
_CELL_TI     = 22


def parse_standings(html: str) -> List[StandingRow]:
    """
    Parse the MPA /reports/rankingslist HTML for Class B North.

    Looks for <table id="North"> and extracts each team row.
    Returns an empty list (not an error) if the structure isn't found —
    this happens early in the season before MPA publishes data.
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: List[StandingRow] = []

    table = soup.find("table", id="North")
    if table is None:
        # Fall back: try any table if MPA ever renames the region
        table = soup.find("table")
    if table is None:
        return rows

    for tr in table.find_all("tr"):
        mpa_tr_id = tr.get("id")
        if not mpa_tr_id:
            continue  # header rows have no id

        cells = tr.find_all(["td", "th"])
        if len(cells) < _CELL_TI + 1:
            continue

        rank       = _to_int(cells[_CELL_RANK].get_text(strip=True))
        team_name  = cells[_CELL_NAME].get_text(" ", strip=True)
        # Strip any trailing scorestanding link text that BeautifulSoup folds in
        team_name  = re.sub(r"\s{2,}", " ", team_name).strip()
        wins       = _to_int(cells[_CELL_W].get_text(strip=True))
        losses     = _to_int(cells[_CELL_L].get_text(strip=True))
        ties       = _to_int(cells[_CELL_T].get_text(strip=True))
        pi         = _to_float(cells[_CELL_PI].get_text(strip=True))
        ti         = _to_float(cells[_CELL_TI].get_text(strip=True))

        rows.append(
            StandingRow(
                rank=rank,
                team_name=team_name,
                mpa_tr_id=mpa_tr_id,
                wins=wins,
                losses=losses,
                ties=ties,
                preliminary_index=pi,
                tournament_index=ti,
            )
        )

    return rows


def parse_mpa_cc_schedule(html: str, year: int) -> List[dict]:
    """
    Parse an mpa.cc /DashboardSchedule.aspx TileTable page.

    Cell layout (every other <td> is a spacer):
      [0]  "FRI 4/24 4:00 PM"
      [2]  "Girls Softball Varsity {Home} - {Class} [{score}] {Away} - {Class} [{score}]"
      [4]  Location string

    Returns absolute game dicts with both team names (not team-perspective like ScheduleEntry).
    """
    soup = BeautifulSoup(html, "html.parser")
    games: list = []

    table = soup.find("table", class_="TileTable")
    if table is None:
        return games

    for row in table.find_all("tr"):
        cells = [td.get_text(" ", strip=True) for td in row.find_all("td")]
        if len(cells) < 3 or not cells[0]:
            continue

        # Date from cell[0]: "FRI 4/24 4:00 PM"
        dm = re.search(r"(\d{1,2})/(\d{1,2})", cells[0])
        if not dm:
            continue
        date_str = f"{year}-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"

        # Matchup from cell[2]: "Girls Softball Varsity Home - North-B [score] Away - North-B [score]"
        matchup = cells[2] if len(cells) > 2 else ""
        pm = re.search(
            r"Softball Varsity (.+?) - (\w+-[ABCD])(?:\s+(\d+))?\s+(.+?) - (\w+-[ABCD])(?:\s+(\d+))?",
            matchup,
        )
        if not pm:
            continue

        home_score = int(pm.group(3)) if pm.group(3) else None
        away_score = int(pm.group(6)) if pm.group(6) else None

        games.append(
            {
                "date": date_str,
                "home_team_name": pm.group(1).strip(),
                "home_class": pm.group(2),
                "home_score": home_score,
                "away_team_name": pm.group(4).strip(),
                "away_class": pm.group(5),
                "away_score": away_score,
                "played": home_score is not None and away_score is not None,
            }
        )

    return games


def parse_team_schedule(html: str, team_name: str = "") -> List[ScheduleEntry]:
    """
    Parse an mpaschedules.org scorestanding/list page.

    Table class: tbl-scores-standing
    Data rows: class="table-data-styles"
    Columns (0-indexed): Date | Time | Event Type | Opponent | Loc. | Score | W/L/T | Comments
    """
    soup = BeautifulSoup(html, "html.parser")
    entries: List[ScheduleEntry] = []

    table = soup.find("table", class_="tbl-scores-standing")
    if table is None:
        return entries

    for tr in table.find_all("tr", class_="table-data-styles"):
        cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if len(cells) < 7:
            continue

        raw_date     = cells[0]
        opponent     = cells[3]
        loc_raw      = cells[4].upper()
        score_raw    = cells[5]   # e.g. "5 - 1" or "1 - 11"
        result_raw   = cells[6].upper().strip()

        # Parse date: "04-17-24" or "04-17-2024" or various other formats
        iso_date = raw_date
        for fmt in ("%m-%d-%y", "%m-%d-%Y", "%m/%d/%Y", "%m/%d/%y",
                    "%B %d, %Y", "%b %d, %Y"):
            try:
                iso_date = datetime.strptime(raw_date, fmt).date().isoformat()
                break
            except ValueError:
                continue

        # Home/Away: loc cell may say "Home", "Away", "H", "A", or be blank
        if loc_raw.startswith("H"):
            home_away = "H"
        elif loc_raw.startswith("A"):
            home_away = "A"
        else:
            home_away = ""

        # Score: "5 - 1" → for=5, against=1
        score_for = score_against = None
        m = re.match(r"\s*(\d+)\s*[-–]\s*(\d+)", score_raw)
        if m:
            score_for     = int(m.group(1))
            score_against = int(m.group(2))

        # Result
        result: Optional[str] = None
        if result_raw in ("W", "L", "T"):
            result = result_raw

        entries.append(
            ScheduleEntry(
                date=iso_date,
                opponent_name=opponent,
                home_away=home_away,
                result=result,
                score_for=score_for,
                score_against=score_against,
            )
        )

    return entries
