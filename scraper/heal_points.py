"""
Heal Point calculation engine.

MPA's Heal Point system (used for softball playoff seeding in Maine):

  Preliminary Index (PI):
      PI = sum over each win of POINTS[opponent_class]
           divided by number of scheduled games
      POINTS = {A: 40, B: 35, C: 30, D: 25}
      Teams with no wins: PI = 1.0

  Tournament Index (TI):
      TI = (sum over each win of opponent.PI)
           / scheduled_games * 10

Playoff seeding within a region (e.g. Class B North) is determined by
descending Tournament Index.

This module is deliberately pure — it takes in game records and team data
and returns structured results. That makes it trivial to unit test and to
run "what-if" projections for the rest of the season.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from config import HEAL_POINTS_PER_CLASS


@dataclass
class Game:
    """A single scheduled game."""
    date: str                     # YYYY-MM-DD
    home_team_key: str
    away_team_key: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    opponent_class: Optional[str] = None   # "A" | "B" | "C" | "D" — from the perspective of the non-focus team if needed
    played: bool = False

    @property
    def winner_key(self) -> Optional[str]:
        if not self.played or self.home_score is None or self.away_score is None:
            return None
        if self.home_score > self.away_score:
            return self.home_team_key
        if self.away_score > self.home_score:
            return self.away_team_key
        return None  # tie (rare in softball; treated as no win for either)


@dataclass
class Team:
    key: str
    name: str
    classification: str = "B"              # A / B / C / D
    scheduled_games: int = 0
    # Populated by compute_heal_points():
    wins: int = 0
    losses: int = 0
    preliminary_index: float = 1.0
    tournament_index: float = 0.0
    win_opponents: List[str] = field(default_factory=list)  # keys of teams this one has beaten


def _opponent_key(game: Game, focus_key: str) -> str:
    return game.away_team_key if game.home_team_key == focus_key else game.home_team_key


def _class_of_opponent(game: Game, focus_key: str, teams_by_key: Dict[str, Team]) -> str:
    """Class of the team this focus team played against."""
    opp_key = _opponent_key(game, focus_key)
    opp = teams_by_key.get(opp_key)
    if opp:
        return opp.classification
    # Fallback: we may have a game vs. an out-of-region team we don't track
    # fully; the scraper should populate game.opponent_class for those.
    return game.opponent_class or "B"


def compute_preliminary_indexes(teams: Iterable[Team], games: Iterable[Game]) -> None:
    """
    First pass: compute each team's Preliminary Index in place.
    Call compute_tournament_indexes() afterward.
    """
    teams_by_key = {t.key: t for t in teams}
    games_list = list(games)

    # Reset derived fields
    for t in teams_by_key.values():
        t.wins = 0
        t.losses = 0
        t.win_opponents = []

    for g in games_list:
        if not g.played:
            continue
        winner = g.winner_key
        if winner is None:
            continue
        for side_key in (g.home_team_key, g.away_team_key):
            team = teams_by_key.get(side_key)
            if not team:
                continue
            if side_key == winner:
                team.wins += 1
                team.win_opponents.append(_opponent_key(g, side_key))
            else:
                team.losses += 1

    for team in teams_by_key.values():
        if team.scheduled_games <= 0:
            team.preliminary_index = 1.0
            continue
        if team.wins == 0:
            team.preliminary_index = 1.0
            continue
        total_points = 0
        for g in games_list:
            if not g.played:
                continue
            if g.winner_key != team.key:
                continue
            opp_class = _class_of_opponent(g, team.key, teams_by_key)
            total_points += HEAL_POINTS_PER_CLASS.get(opp_class, 35)
        team.preliminary_index = total_points / team.scheduled_games


def compute_tournament_indexes(teams: Iterable[Team], games: Iterable[Game]) -> None:
    """
    Second pass: compute each team's Tournament Index in place, using
    opponents' preliminary indexes from the first pass.

    TI = (sum of opponents' PI for each win) / scheduled_games * 10
    """
    teams_by_key = {t.key: t for t in teams}

    for team in teams_by_key.values():
        if team.scheduled_games <= 0 or team.wins == 0:
            team.tournament_index = 0.0
            continue
        total = 0.0
        for opp_key in team.win_opponents:
            opp = teams_by_key.get(opp_key)
            # If we don't have the opponent modeled, assume PI = 1.0 to
            # match MPA's treatment of winless teams.
            total += opp.preliminary_index if opp else 1.0
        team.tournament_index = (total / team.scheduled_games) * 10


def compute_heal_points(teams: List[Team], games: List[Game]) -> List[Team]:
    """Run both passes and return the teams sorted by Tournament Index desc."""
    compute_preliminary_indexes(teams, games)
    compute_tournament_indexes(teams, games)
    return sorted(teams, key=lambda t: t.tournament_index, reverse=True)


# ---------------------------------------------------------------------------
# Projection: simulate what happens if the remaining games have specific
# outcomes. Handy for game-planning ("if we beat Skowhegan, what seed do
# we project to?").
# ---------------------------------------------------------------------------
def project_with_outcomes(
    teams: List[Team],
    games: List[Game],
    hypothetical_outcomes: Dict[int, str],  # {game_index: winning_team_key}
) -> List[Team]:
    """
    Return a new ranking assuming specific outcomes for the given upcoming
    games. Does not mutate the inputs.
    """
    import copy
    sim_games = copy.deepcopy(games)
    sim_teams = copy.deepcopy(teams)

    for idx, winner_key in hypothetical_outcomes.items():
        if idx < 0 or idx >= len(sim_games):
            continue
        g = sim_games[idx]
        g.played = True
        # Assign a plausible scoreline so winner_key resolves correctly.
        if winner_key == g.home_team_key:
            g.home_score, g.away_score = 1, 0
        elif winner_key == g.away_team_key:
            g.home_score, g.away_score = 0, 1
        else:
            continue

    return compute_heal_points(sim_teams, sim_games)
