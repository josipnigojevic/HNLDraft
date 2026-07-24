import unittest

import sim_engine


class SimEngineTests(unittest.TestCase):
    def test_official_schedule_invariants(self) -> None:
        team_names = [team.name for team in sim_engine.default_teams()]
        schedule = sim_engine.hnl_schedule(team_names)
        self.assertEqual(len(schedule), 36)
        appearances = {team: 0 for team in team_names}
        venues: dict[tuple[str, str], int] = {}
        for round_pairings in schedule:
            self.assertEqual(len(round_pairings), 5)
            seen: set[str] = set()
            for home, away in round_pairings:
                self.assertNotIn(home, seen)
                self.assertNotIn(away, seen)
                seen.update([home, away])
                appearances[home] += 1
                appearances[away] += 1
                venues[(home, away)] = venues.get((home, away), 0) + 1
            self.assertEqual(set(team_names), seen)
        self.assertTrue(all(matches == 36 for matches in appearances.values()))
        for index, team_a in enumerate(team_names):
            for team_b in team_names[index + 1 :]:
                self.assertEqual(venues.get((team_a, team_b)), 2)
                self.assertEqual(venues.get((team_b, team_a)), 2)

    def test_same_seed_is_identical(self) -> None:
        first = sim_engine.simulate_season(38_020_261_743)
        second = sim_engine.simulate_season(38_020_261_743)
        self.assertEqual(first["content_sha256"], second["content_sha256"])
        self.assertEqual(first, second)

    def test_different_seed_changes_run(self) -> None:
        first = sim_engine.simulate_season(38_020_261_743)
        second = sim_engine.simulate_season(38_020_261_744)
        self.assertNotEqual(first["content_sha256"], second["content_sha256"])

    def test_disclosed_golden_path(self) -> None:
        result = sim_engine.simulate_challenge(
            seed=474,
            matches_count=38,
            showcase_boost=41.0,
        )
        self.assertTrue(result["perfect"])
        self.assertEqual(
            result["record"],
            {
                "wins": 38,
                "draws": 0,
                "losses": 0,
                "points": 114,
                "goals_for": 119,
                "goals_against": 27,
                "goal_difference": 92,
            },
        )


if __name__ == "__main__":
    unittest.main()

