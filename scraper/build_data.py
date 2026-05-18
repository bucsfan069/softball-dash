"""
Top-level orchestrator — fetches, parses, computes, writes JSON for the
frontend. Run this on a schedule (cron, GitHub Actions, etc.).

Output files (all under site/data/<year>/):
    standings.json      — current standings with PI, TI, record, rank
    schedule.json       — full schedule with results (all teams merged)
    teams.json          — team metadata (names, cities, scouting links)
    last_updated.json   — timestamp for the dashboard to display
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from config import (
    _BASE_DATA_DIR,
    CLASS_B_CLASSIFICATION_ID,
    MPA_SCHED_AGLS,
    MPA_SCHED_SEASON,
    SEASON_YEAR,
    TEAMS,
    YEAR_OVERRIDES,
)
from fetch_mpa import FetchError, fetch_class_b_north_standings, fetch_fpsports_standings, fetch_mpa_cc_schedule, fetch_team_schedule
from heal_points import Game, Team, compute_heal_points, compute_preliminary_indexes, compute_tournament_indexes
from parse_mpa import parse_fpsports_standings, parse_mpa_cc_schedule, parse_standings, parse_team_schedule


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    try:
        rel = path.relative_to(_BASE_DATA_DIR.parent)
    except ValueError:
        rel = path
    print(f"  wrote {rel}")


# Map from MPA table-row ID → team key (for cross-referencing schedule data)
_MPA_TR_ID_TO_KEY: Dict[str, str] = {t["mpa_tr_id"]: t["key"] for t in TEAMS}
_SCHEDULE_ID_TO_KEY: Dict[str, str] = {t["schedule_id"]: t["key"] for t in TEAMS}
_NAME_TO_KEY: Dict[str, str] = {t["name"].lower(): t["key"] for t in TEAMS}

# MPA scorestanding pages sometimes use different name variants than the
# standings page.  Add aliases here so deduplication works correctly.
_NAME_TO_KEY.update({
    # mpaschedules.org variants
    "cony middle/high school": "cony",
    "nokomis regional": "nokomis",
    "belfast area": "belfast",
    "mdi high school": "mdi",
    "john bapst memorial high school": "john_bapst",
    "ellsworth/george stevens": "ellsworth",
    # mpa.cc schedule page variants (team names shown without full formal name)
    "cony hs": "cony",
    "nokomis": "nokomis",
    "john bapst memorial": "john_bapst",
    "mount desert island": "mdi",
    "ellsworth": "ellsworth",
    "foxcroft academy": "foxcroft",
    "gardiner area": "gardiner",
})


def _load_mpa_standings(
    year: int,
    season_start: str,
    season_end: str,
    classification_id: int,
) -> List[dict]:
    """Fetch+parse MPA standings. Returns a list of dicts (JSON-safe)."""
    try:
        html = fetch_class_b_north_standings(
            season_year=year,
            season_start=season_start,
            season_end=season_end,
            classification_id=classification_id,
        )
    except FetchError as e:
        print(f"! Could not fetch MPA standings: {e}", file=sys.stderr)
        return []

    try:
        rows = parse_standings(html)
    except Exception:
        print("! Failed to parse MPA standings HTML:", file=sys.stderr)
        traceback.print_exc()
        return []

    if not rows:
        print(f"  No rows parsed from MPA (season {year} may not be published yet)")
        return []

    result = []
    for r in rows:
        team_key = _MPA_TR_ID_TO_KEY.get(r.mpa_tr_id, "")
        result.append({
            "rank": r.rank,
            "team_name": r.team_name,
            "team_key": team_key,
            "wins": r.wins,
            "losses": r.losses,
            "ties": r.ties,
            "scheduled_games": r.wins + r.losses + r.ties,
            "preliminary_index": round(r.preliminary_index, 4) if r.preliminary_index is not None else None,
            "tournament_index": round(r.tournament_index, 4) if r.tournament_index is not None else None,
            "source": "mpa",
        })
    return result


def _load_fpsports_standings(tournament_id: int, division_id: int) -> List[dict]:
    """Fetch+parse official standings from mpa.fpsports.org. Returns JSON-safe dicts."""
    try:
        html = fetch_fpsports_standings(tournament_id, division_id)
    except FetchError as e:
        print(f"! Could not fetch fpsports standings: {e}", file=sys.stderr)
        return []

    try:
        rows = parse_fpsports_standings(html)
    except Exception:
        print("! Failed to parse fpsports standings HTML:", file=sys.stderr)
        traceback.print_exc()
        return []

    if not rows:
        print("  No rows parsed from fpsports standings")
        return []

    result = []
    for r in rows:
        team_key = _NAME_TO_KEY.get(r["team_name"].lower(), "")
        result.append({
            "rank": r["rank"],
            "team_name": r["team_name"],
            "team_key": team_key,
            "wins": r["wins"],
            "losses": r["losses"],
            "ties": r["ties"],
            "scheduled_games": r["scheduled_games"],
            "preliminary_index": round(r["preliminary_index"], 4) if r["preliminary_index"] is not None else None,
            "tournament_index": round(r["tournament_index"], 4) if r["tournament_index"] is not None else None,
            "wins_detail": r["wins_detail"],
            "losses_detail": r["losses_detail"],
            "source": "fpsports",
        })
    return result


def _local_standings_fallback(games: List[dict], teams_list: List[dict] = None) -> List[dict]:
    """
    Derive standings locally from schedule.json when MPA data isn't available.
    Used early in the season before MPA publishes Heal Point data.
    """
    if teams_list is None:
        teams_list = TEAMS
    game_objs = [Game(**g) for g in games]
    teams = [
        Team(
            key=t["key"],
            name=t["name"],
            classification="B",
            scheduled_games=max(14, sum(
                1 for g in game_objs
                if g.home_team_key == t["key"] or g.away_team_key == t["key"]
            )),
        )
        for t in teams_list
    ]
    ranked = compute_heal_points(teams, game_objs)
    return [
        {
            "rank": i + 1,
            "team_name": t.name,
            "team_key": t.key,
            "wins": t.wins,
            "losses": t.losses,
            "ties": 0,
            "scheduled_games": t.scheduled_games,
            "preliminary_index": round(t.preliminary_index, 4),
            "tournament_index": round(t.tournament_index, 4),
            "source": "local_calc",
        }
        for i, t in enumerate(ranked)
    ]


def _fetch_all_schedules(sched_agls: str, sched_season: str) -> List[dict]:
    """
    Fetch each team's score/standings page from mpaschedules.org and merge
    results into a single list of game dicts.

    Each game appears twice in the raw data (once per team's schedule), so we
    deduplicate on (date, team_a, team_b) with the result that came from the
    winning team's page (which is more likely to have the correct score).
    """
    seen: Dict[tuple, dict] = {}  # (date, key_a, key_b) → game dict

    for team in TEAMS:
        schedule_id = team["schedule_id"]
        team_key    = team["key"]
        print(f"  fetching schedule for {team['name']} (id={schedule_id})…")
        try:
            html = fetch_team_schedule(
                schedule_id,
                sched_agls=sched_agls,
                sched_season=sched_season,
            )
        except FetchError as e:
            print(f"    ! fetch failed: {e}", file=sys.stderr)
            continue

        try:
            entries = parse_team_schedule(html, team_name=team["name"])
        except Exception:
            print(f"    ! parse failed for {team['name']}:", file=sys.stderr)
            traceback.print_exc()
            continue

        for e in entries:
            opp_name = e.opponent_name.lower()
            opp_key  = _NAME_TO_KEY.get(opp_name, opp_name)  # fallback to name if unknown

            played = e.result is not None
            if e.home_away == "H" or e.home_away == "":
                home_key, away_key = team_key, opp_key
                home_score = e.score_for   if played else None
                away_score = e.score_against if played else None
            else:  # Away
                home_key, away_key = opp_key, team_key
                home_score = e.score_against if played else None
                away_score = e.score_for     if played else None

            dedup_key = (e.date, *sorted([home_key, away_key]))
            game_dict = {
                "date": e.date,
                "home_team_key": home_key,
                "away_team_key": away_key,
                "home_score": home_score,
                "away_score": away_score,
                "opponent_class": "B",  # default; MPA page can refine this
                "played": played,
            }

            # Keep whichever version of this game has a score
            if dedup_key not in seen or (not seen[dedup_key]["played"] and played):
                seen[dedup_key] = game_dict

    return list(seen.values())


def _fetch_all_schedules_mpa_cc(sport_id: str, year: int, teams: List[dict]) -> List[dict]:
    """
    Fetch and merge game data from mpa.cc for seasons that use that source.
    Returns deduplicated game dicts identical in shape to _fetch_all_schedules().
    """
    seen: Dict[tuple, dict] = {}

    for team in teams:
        school_id = team.get("mpa_cc_school_id")
        if not school_id:
            print(f"  ! No mpa_cc_school_id for {team['name']}, skipping", file=sys.stderr)
            continue

        print(f"  fetching schedule for {team['name']} (mpa_cc_school_id={school_id})…")
        try:
            html = fetch_mpa_cc_schedule(school_id, sport_id)
        except FetchError as e:
            print(f"    ! fetch failed: {e}", file=sys.stderr)
            continue

        try:
            raw_games = parse_mpa_cc_schedule(html, year)
        except Exception:
            print(f"    ! parse failed for {team['name']}:", file=sys.stderr)
            traceback.print_exc()
            continue

        for g in raw_games:
            home_name = g["home_team_name"].lower()
            away_name = g["away_team_name"].lower()
            home_key = _NAME_TO_KEY.get(home_name, home_name)
            away_key = _NAME_TO_KEY.get(away_name, away_name)

            # Opponent class letter from e.g. "North-B" → "B"
            focus_is_home = home_key == team["key"]
            raw_class = g["away_class"] if focus_is_home else g["home_class"]
            cls_m = re.search(r"-([ABCD])$", raw_class)
            opp_class = cls_m.group(1) if cls_m else "B"

            dedup_key = (g["date"], *sorted([home_key, away_key]))
            game_dict = {
                "date": g["date"],
                "home_team_key": home_key,
                "away_team_key": away_key,
                "home_score": g["home_score"],
                "away_score": g["away_score"],
                "opponent_class": opp_class,
                "played": g["played"],
            }

            if dedup_key not in seen or (not seen[dedup_key]["played"] and g["played"]):
                seen[dedup_key] = game_dict

    return list(seen.values())


def _generate_ti_history(games: List[dict], teams_for_year: List[dict]) -> dict:
    """
    Replay the season chronologically and log every TI change per team.

    Two event types:
      "win"          — this team won a game; their TI went up because they added
                       the beaten opponent's PI to their running total.
      "opponent_win" — a team they previously beat won another game; that
                       opponent's PI increased, so this team's TI went up.

    Returns {team_key: {"team_name": str, "events": [...], "final_ti": float}}.
    """
    team_names = {t["key"]: t["name"] for t in teams_for_year}
    tracked_keys = set(team_names)

    sched: dict = {}
    for g in games:
        for k in (g["home_team_key"], g["away_team_key"]):
            if k in tracked_keys:
                sched[k] = sched.get(k, 0) + 1

    teams_list = [
        Team(
            key=t["key"],
            name=t["name"],
            classification="B",
            scheduled_games=max(sched.get(t["key"], 14), 14),
        )
        for t in teams_for_year
    ]
    teams_by_key = {t.key: t for t in teams_list}

    current_ti: dict = {k: 0.0 for k in tracked_keys}
    history: dict = {k: {"team_name": team_names[k], "events": [], "final_ti": 0.0} for k in tracked_keys}
    replay: list = []

    for gd in sorted((g for g in games if g["played"]), key=lambda g: g["date"]):
        hs = gd.get("home_score") or 0
        as_ = gd.get("away_score") or 0
        home_key = gd["home_team_key"]
        away_key = gd["away_team_key"]

        if hs > as_:
            winner_key, loser_key = home_key, away_key
        elif as_ > hs:
            winner_key, loser_key = away_key, home_key
        else:
            winner_key = loser_key = None

        replay.append(Game(
            date=gd["date"],
            home_team_key=home_key,
            away_team_key=away_key,
            home_score=hs,
            away_score=as_,
            opponent_class=gd.get("opponent_class", "B"),
            played=True,
        ))

        compute_preliminary_indexes(teams_list, replay)
        compute_tournament_indexes(teams_list, replay)

        for tk in tracked_keys:
            new_ti = round(teams_by_key[tk].tournament_index, 4)
            old_ti = current_ti[tk]
            delta = round(new_ti - old_ti, 4)
            if abs(delta) < 0.0001:
                continue

            if tk == winner_key:
                opp_key = away_key if tk == home_key else home_key
                opp = teams_by_key.get(opp_key)
                opp_pi = round(opp.preliminary_index, 4) if opp else 1.0
                score = f"{hs}–{as_}" if tk == home_key else f"{as_}–{hs}"
                history[tk]["events"].append({
                    "date": gd["date"],
                    "event_type": "win",
                    "opponent_key": opp_key,
                    "opponent_name": team_names.get(opp_key) or opp_key.replace("_", " ").title(),
                    "opponent_class": gd.get("opponent_class", "B"),
                    "score": score,
                    "opponent_pi": opp_pi,
                    "ti_before": old_ti,
                    "ti_after": new_ti,
                    "ti_delta": delta,
                })
            else:
                w_name = (team_names.get(winner_key) or winner_key.replace("_", " ").title()) if winner_key else "Unknown"
                l_name = (team_names.get(loser_key) or loser_key.replace("_", " ").title()) if loser_key else "Unknown"
                history[tk]["events"].append({
                    "date": gd["date"],
                    "event_type": "opponent_win",
                    "game_winner_key": winner_key,
                    "game_winner_name": w_name,
                    "game_loser_key": loser_key,
                    "game_loser_name": l_name,
                    "ti_before": old_ti,
                    "ti_after": new_ti,
                    "ti_delta": delta,
                })

            current_ti[tk] = new_ti

    for tk in tracked_keys:
        history[tk]["final_ti"] = current_ti[tk]

    return history


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch and build dashboard JSON for a given season year."
    )
    parser.add_argument(
        "--year",
        type=int,
        default=SEASON_YEAR,
        help=f"Season year to build (default: {SEASON_YEAR})",
    )
    args = parser.parse_args()
    year = args.year

    # Resolve year-specific overrides from config
    overrides = YEAR_OVERRIDES.get(year, {})
    data_dir = _BASE_DATA_DIR / str(year)
    data_dir.mkdir(parents=True, exist_ok=True)

    season_start      = overrides.get("SEASON_START", f"{year}-04-17")
    season_end        = overrides.get("SEASON_END", f"{year}-06-04")
    classification_id = overrides.get("CLASS_B_CLASSIFICATION_ID", CLASS_B_CLASSIFICATION_ID)
    sched_agls        = overrides.get("MPA_SCHED_AGLS", MPA_SCHED_AGLS)
    sched_season_str  = overrides.get("MPA_SCHED_SEASON", MPA_SCHED_SEASON)
    schedule_source   = overrides.get("schedule_source", "mpaschedules")
    mpa_cc_sport_id   = overrides.get("mpa_cc_sport_id", "")

    # Filter team list to only those active in this season's classification.
    active_keys = overrides.get("team_keys")
    teams_for_year = (
        [t for t in TEAMS if t["key"] in active_keys] if active_keys else TEAMS
    )

    print(f"Starting build for {year} at {datetime.now(timezone.utc).isoformat()}")
    print(f"  {len(teams_for_year)} teams, schedule source: {schedule_source}")

    # 1. Schedules first — standings fallback depends on them
    print("Fetching per-team schedules…")
    if schedule_source == "mpa_cc":
        schedule_games = _fetch_all_schedules_mpa_cc(mpa_cc_sport_id, year, teams_for_year)
    else:
        schedule_games = _fetch_all_schedules(sched_agls, sched_season_str)
    print(f"  {len(schedule_games)} unique games found")
    _write_json(data_dir / "schedule.json", schedule_games)

    # 2b. TI history — replay the season chronologically
    print("Computing TI history…")
    ti_history = _generate_ti_history(schedule_games, teams_for_year)
    _write_json(data_dir / "ti_history.json", ti_history)

    # 2. MPA standings — try fpsports.org first (has correct PI/TI + detail),
    #    then mpareports.com, then fall back to local calculation.
    print("Fetching MPA Heal Point standings…")
    fpsports_tid = overrides.get("fpsports_tournament_id")
    fpsports_did = overrides.get("fpsports_division_id")

    standings = []
    if fpsports_tid and fpsports_did:
        standings = _load_fpsports_standings(fpsports_tid, fpsports_did)
        if standings:
            print(f"  Got {len(standings)} rows from fpsports.org")

    if not standings:
        standings = _load_mpa_standings(year, season_start, season_end, classification_id)
        if standings:
            print(f"  Got {len(standings)} rows from mpareports.com")

    if not standings:
        print("  Falling back to local Heal Point calculation")
        standings = _local_standings_fallback(
            [g for g in schedule_games if g["played"]], teams_for_year
        )

    _write_json(data_dir / "standings.json", standings)

    # 3. Team metadata for the frontend
    teams_out = [
        {
            "key": t["key"],
            "name": t["name"],
            "city": t["city"],
            "maxpreps_slug": t["maxpreps_slug"],
        }
        for t in teams_for_year
    ]
    _write_json(data_dir / "teams.json", teams_out)

    # 4. Timestamp
    source = standings[0]["source"] if standings else "none"
    _write_json(
        data_dir / "last_updated.json",
        {"utc": datetime.now(timezone.utc).isoformat(), "standings_source": source},
    )

    # 5. Update seasons manifest so the frontend dropdown stays current.
    seasons_path = _BASE_DATA_DIR / "seasons.json"
    if seasons_path.exists():
        manifest = json.loads(seasons_path.read_text(encoding="utf-8"))
        # Migrate old array format to object format on first encounter
        if isinstance(manifest, list):
            manifest = {
                "seasons": manifest,
                "current": max((s["year"] for s in manifest), default=year),
            }
    else:
        manifest = {"seasons": [], "current": year}

    known_years = {s["year"] for s in manifest["seasons"]}
    if year not in known_years:
        manifest["seasons"].append({"year": year, "label": f"{year} Season"})
        manifest["seasons"].sort(key=lambda s: s["year"])

    # Promote current to the highest year that has been built
    if year >= manifest.get("current", 0):
        manifest["current"] = year

    seasons_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    seasons_listed = [s["year"] for s in manifest["seasons"]]
    print(f"  updated seasons.json — current={manifest['current']}, seasons={seasons_listed}")

    print("Build complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
