"""
Generate realistic-looking demo data so the dashboard renders something
useful out-of-the-box (before the real scraper has pulled live MPA data).

Creates:
    site/data/standings.json
    site/data/schedule.json
    site/data/teams.json
    site/data/last_updated.json

Usage:
    python seed_demo_data.py
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import DATA_DIR, TEAMS
from heal_points import Game, Team, compute_heal_points


def main() -> int:
    random.seed(12)  # reproducible demo data

    # 1. Teams — match config TEAMS
    (DATA_DIR / "teams.json").write_text(json.dumps(TEAMS, indent=2), encoding="utf-8")

    # 2. Build a schedule — each team plays every other team once (round-robin)
    team_keys = [t["key"] for t in TEAMS]
    scheduled_games_per_team = len(team_keys) - 1  # round robin
    season_start = datetime(2026, 4, 17)

    games_raw: list[dict] = []
    # Generate matchups
    pairings = []
    for i, a in enumerate(team_keys):
        for b in team_keys[i + 1:]:
            # Alternate home/away
            if random.random() < 0.5:
                pairings.append((a, b))
            else:
                pairings.append((b, a))
    random.shuffle(pairings)

    # Spread games across the season; assume ~60% played already as of today
    for idx, (home, away) in enumerate(pairings):
        day_offset = idx // 3  # 3 games per day-ish
        game_date = season_start + timedelta(days=day_offset)
        played = idx < int(len(pairings) * 0.6)
        if played:
            home_score = random.randint(0, 10)
            away_score = random.randint(0, 10)
            while home_score == away_score:   # avoid ties
                away_score = random.randint(0, 10)
        else:
            home_score, away_score = None, None

        games_raw.append({
            "date": game_date.date().isoformat(),
            "home_team_key": home,
            "away_team_key": away,
            "home_score": home_score,
            "away_score": away_score,
            "opponent_class": "B",
            "played": played,
        })

    (DATA_DIR / "schedule.json").write_text(json.dumps(games_raw, indent=2), encoding="utf-8")

    # 3. Standings — compute using the heal_points engine
    games = [Game(**g) for g in games_raw]
    teams = [Team(key=t["key"], name=t["name"], classification="B",
                  scheduled_games=scheduled_games_per_team) for t in TEAMS]
    ranked = compute_heal_points(teams, games)

    standings = [
        {
            "rank": i + 1,
            "team_name": t.name,
            "team_key": t.key,
            "wins": t.wins,
            "losses": t.losses,
            "scheduled_games": t.scheduled_games,
            "preliminary_index": round(t.preliminary_index, 3),
            "tournament_index": round(t.tournament_index, 4),
            "source": "demo",
        }
        for i, t in enumerate(ranked)
    ]
    (DATA_DIR / "standings.json").write_text(json.dumps(standings, indent=2), encoding="utf-8")

    # 4. Last updated marker
    (DATA_DIR / "last_updated.json").write_text(json.dumps({
        "utc": datetime.now(timezone.utc).isoformat(),
        "standings_source": "demo",
    }, indent=2), encoding="utf-8")

    print(f"Seeded demo data into {DATA_DIR}")
    print(f"  {len(TEAMS)} teams, {len(games_raw)} games, {sum(1 for g in games_raw if g['played'])} played")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
