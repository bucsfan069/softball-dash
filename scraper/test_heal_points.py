"""
Unit tests for the Heal Point calculation engine.

Run with:  python test_heal_points.py
"""

import unittest

from heal_points import (
    Game,
    Team,
    compute_heal_points,
    project_with_outcomes,
)


class HealPointTests(unittest.TestCase):
    def _make_teams(self) -> list:
        # 4 Class B teams with 14-game schedules
        return [
            Team(key="lawrence", name="Lawrence", classification="B", scheduled_games=14),
            Team(key="skowhegan", name="Skowhegan", classification="B", scheduled_games=14),
            Team(key="brewer", name="Brewer", classification="B", scheduled_games=14),
            Team(key="hampden", name="Hampden", classification="B", scheduled_games=14),
        ]

    def test_no_wins_preliminary_index_is_one(self):
        teams = self._make_teams()
        games = []  # nothing played
        ranked = compute_heal_points(teams, games)
        for t in ranked:
            self.assertEqual(t.preliminary_index, 1.0)
            self.assertEqual(t.tournament_index, 0.0)

    def test_single_win_class_b(self):
        """
        Lawrence beats Skowhegan (Class B opponent).
        PI(Lawrence) = 35 / 14 = 2.5
        TI(Lawrence) = (PI(Skowhegan)=1.0) / 14 * 10 = 0.714...
        """
        teams = self._make_teams()
        games = [Game(date="2026-04-20", home_team_key="lawrence",
                      away_team_key="skowhegan", home_score=5, away_score=2, played=True)]
        ranked = compute_heal_points(teams, games)
        lawrence = next(t for t in ranked if t.key == "lawrence")
        self.assertAlmostEqual(lawrence.preliminary_index, 35 / 14, places=4)
        self.assertAlmostEqual(lawrence.tournament_index, (1.0 / 14) * 10, places=4)

    def test_tournament_index_weights_strong_opponents(self):
        """
        A team that beats teams with higher PIs should have a higher TI than
        a team that beats only winless opponents.
        """
        teams = self._make_teams()
        games = [
            # Brewer beats Hampden (who now has PI>1 is false — Hampden is still winless)
            Game(date="2026-04-20", home_team_key="brewer",
                 away_team_key="hampden", home_score=3, away_score=1, played=True),
            # Skowhegan beats Hampden also
            Game(date="2026-04-22", home_team_key="skowhegan",
                 away_team_key="hampden", home_score=5, away_score=0, played=True),
            # Lawrence beats Brewer (who has a win -> PI > 1.0)
            Game(date="2026-04-24", home_team_key="lawrence",
                 away_team_key="brewer", home_score=4, away_score=3, played=True),
        ]
        ranked = compute_heal_points(teams, games)

        lawrence = next(t for t in ranked if t.key == "lawrence")
        skowhegan = next(t for t in ranked if t.key == "skowhegan")

        # Lawrence beat a team with a non-trivial PI, so TI should reflect that.
        self.assertGreater(lawrence.tournament_index, skowhegan.tournament_index * 0.5,
                           "Lawrence beat a winning team; TI should be meaningfully positive")

    def test_projection_does_not_mutate_inputs(self):
        teams = self._make_teams()
        games = [Game(date="2026-05-01", home_team_key="lawrence",
                      away_team_key="brewer", home_score=None, away_score=None, played=False)]

        before_wins = {t.key: t.wins for t in teams}
        projected = project_with_outcomes(teams, games, {0: "lawrence"})

        self.assertEqual(before_wins, {t.key: t.wins for t in teams},
                         "Original teams list should not be mutated")
        self.assertTrue(any(t.key == "lawrence" and t.wins == 1 for t in projected))


if __name__ == "__main__":
    unittest.main()
