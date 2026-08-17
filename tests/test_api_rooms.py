import hashlib
import http.cookiejar
import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import api_rooms


def test_catalog() -> api_rooms.Catalog:
    def player(
        suffix: str,
        name: str,
        positions: list[str],
        rating: int,
    ) -> dict:
        return {
            "id": f"player-{suffix}",
            "personId": f"person-{suffix}",
            "name": name,
            "positions": positions,
            "seasonRating": rating,
            "primeRating": rating + 2,
            "ratingKind": "test",
        }

    def record(
        suffix: str,
        year: int,
        rating_offset: int,
    ) -> dict:
        return {
            "id": f"club-{suffix}-{year}",
            "club": {
                "id": f"club-{suffix}",
                "name": f"Club {suffix.upper()}",
                "shortName": suffix.upper(),
            },
            "season": {
                "label": f"{year}/{str(year + 1)[-2:]}",
                "startYear": year,
                "endYear": year + 1,
            },
            "players": [
                player(f"{suffix}-gk", f"Keeper {suffix}", ["GK"], 75 + rating_offset),
                player(
                    f"{suffix}-utility",
                    f"Utility {suffix}",
                    ["CM", "DM", "AM", "RW", "LW"],
                    77 + rating_offset,
                ),
                player(
                    f"{suffix}-def",
                    f"Defender {suffix}",
                    ["CB", "RB", "LB"],
                    76 + rating_offset,
                ),
                player(
                    f"{suffix}-st",
                    f"Striker {suffix}",
                    ["ST", "RW", "LW"],
                    79 + rating_offset,
                ),
            ],
            "source": {"kind": "unit-test"},
            "confidence": 1.0,
        }

    return api_rooms.Catalog(
        [
            record("a", 2000, 0),
            record("b", 2001, 2),
            record("c", 2002, 4),
        ],
        {
            "completeness": "unit-test",
            "confidence": 1.0,
            "sources": [{"name": "fixture"}],
        },
        source_path="memory://unit-test",
    )


class CatalogPositionIntegrityTests(unittest.TestCase):
    def test_goalkeeper_cannot_receive_outfield_eligibility(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "cannot combine goalkeeper and outfield positions",
        ):
            api_rooms.Catalog._normalize_player(
                {
                    "name": "Broken fallback",
                    "positions": ["GK", "CB", "ST"],
                    "seasonRating": 70,
                },
                "club-season",
                "club",
                "2001/02",
            )

    def test_unknown_position_is_never_draft_eligible(self) -> None:
        player = api_rooms.Catalog._normalize_player(
            {
                "name": "Unresolved player",
                "positions": ["UNK"],
                "seasonRating": 70,
                "draftEligible": True,
            },
            "club-season",
            "club",
            "2001/02",
        )
        self.assertFalse(player["draftEligible"])


class FakeClock:
    def __init__(self, value: float = 1_000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value


def completed_xi_picks() -> list[dict]:
    roles = [
        ("gk", "GK"),
        ("rb", "RB"),
        ("rcb", "CB"),
        ("lcb", "CB"),
        ("lb", "LB"),
        ("dm", "DM"),
        ("rcm", "CM"),
        ("lcm", "AM"),
        ("rw", "RW"),
        ("st", "ST"),
        ("lw", "LW"),
    ]
    return [
        {
            "turn": index,
            "slotId": slot_id,
            "player": {
                "id": f"xi-player-{index}",
                "personId": f"xi-person-{index}",
                "name": f"XI Player {index}",
                "positions": [position],
            },
            "selectedRating": 79 + index % 6,
        }
        for index, (slot_id, position) in enumerate(roles)
    ]


class SeasonPayloadTests(unittest.TestCase):
    def test_deterministic_full_season_and_aggregate_consistency(self) -> None:
        picks = completed_xi_picks()
        first = api_rooms.RoomStore._season_result(38_000_474, 1, picks)
        second = api_rooms.RoomStore._season_result(38_000_474, 1, picks)
        self.assertEqual(first, second)
        self.assertEqual(first["model"], "editorial-rating-poisson-v3")
        self.assertEqual(first["played"], 36)
        self.assertEqual(len(first["matches"]), 36)
        self.assertEqual(
            [match["matchweek"] for match in first["matches"]],
            list(range(1, 37)),
        )
        for match in first["matches"]:
            animation = match["animation"]
            self.assertEqual(animation["recommendedDurationMs"], 1_400)
            self.assertEqual(animation["extraDurationMs"], 0)
            self.assertNotIn("timeline", match)

        wins = sum(match["outcome"] == "W" for match in first["matches"])
        draws = sum(match["outcome"] == "D" for match in first["matches"])
        losses = sum(match["outcome"] == "L" for match in first["matches"])
        goals_for = sum(match["goalsFor"] for match in first["matches"])
        goals_against = sum(
            match["goalsAgainst"] for match in first["matches"]
        )
        points = sum(match["pointsEarned"] for match in first["matches"])
        self.assertEqual((wins, draws, losses), (first["wins"], first["draws"], first["losses"]))
        self.assertEqual(wins + draws + losses, 36)
        self.assertEqual(goals_for, first["goalsFor"])
        self.assertEqual(goals_against, first["goalsAgainst"])
        self.assertEqual(points, first["points"])
        self.assertEqual(points, wins * 3 + draws)
        self.assertEqual(
            first["goalDifference"],
            first["goalsFor"] - first["goalsAgainst"],
        )
        self.assertEqual(
            first["matches"][-1]["running"],
            {
                "played": first["played"],
                "wins": first["wins"],
                "draws": first["draws"],
                "losses": first["losses"],
                "points": first["points"],
                "goalsFor": first["goalsFor"],
                "goalsAgainst": first["goalsAgainst"],
                "goalDifference": first["goalDifference"],
            },
        )

        xi_ids = {pick["player"]["id"] for pick in picks}
        scorer_events = [
            event
            for match in first["matches"]
            for event in match["scorers"]
        ]
        self.assertEqual(len(scorer_events), goals_for)
        self.assertTrue(
            all(event["playerId"] in xi_ids for event in scorer_events)
        )
        self.assertTrue(
            all(
                event.get("assistPlayerId") in xi_ids
                for event in scorer_events
                if "assistPlayerId" in event
            )
        )
        player_stats = {
            player["playerId"]: player for player in first["playerStats"]
        }
        self.assertEqual(set(player_stats), xi_ids)
        self.assertEqual(
            sum(player["goals"] for player in player_stats.values()),
            goals_for,
        )
        self.assertEqual(
            sum(player["assists"] for player in player_stats.values()),
            sum("assistPlayerId" in event for event in scorer_events),
        )

        opponent_counts: dict[str, int] = {}
        venue_counts: dict[tuple[str, str], int] = {}
        opponent_scorer_count = 0
        opponent_by_id = {
            opponent["id"]: opponent
            for opponent in api_rooms.HNL_SIMULATION_OPPONENTS
        }
        for match in first["matches"]:
            opponent_id = match["opponent"]["id"]
            opponent_counts[opponent_id] = opponent_counts.get(opponent_id, 0) + 1
            key = (opponent_id, match["venue"])
            venue_counts[key] = venue_counts.get(key, 0) + 1
            opponent_events = match["opponentScorers"]
            opponent_scorer_count += len(opponent_events)
            self.assertEqual(len(opponent_events), match["goalsAgainst"])
            self.assertEqual(
                [event["minute"] for event in opponent_events],
                match["opponentGoalMinutes"],
            )
            scorer_pool = set(opponent_by_id[opponent_id]["scorers"])
            for event in opponent_events:
                self.assertEqual(
                    set(event), {"playerId", "playerName", "minute"}
                )
                self.assertIsNone(event["playerId"])
                self.assertIn(event["playerName"], scorer_pool)
                self.assertNotIn("strijelac", event["playerName"].casefold())
        self.assertEqual(opponent_scorer_count, goals_against)
        self.assertEqual(set(opponent_counts.values()), {4})
        self.assertTrue(
            all(
                venue_counts[(opponent["id"], venue)] == 2
                for opponent in api_rooms.HNL_SIMULATION_OPPONENTS
                for venue in ("H", "A")
            )
        )

        self.assertEqual(len(first["leagueTable"]), 10)
        self.assertTrue(
            all(row["played"] == 36 for row in first["leagueTable"])
        )
        self.assertTrue(
            all(
                row["points"] == row["wins"] * 3 + row["draws"]
                and row["goalDifference"]
                == row["goalsFor"] - row["goalsAgainst"]
                for row in first["leagueTable"]
            )
        )
        self.assertEqual(
            sum(row["goalsFor"] for row in first["leagueTable"]),
            sum(row["goalsAgainst"] for row in first["leagueTable"]),
        )
        drafted_row = next(
            row for row in first["leagueTable"] if row["isDraftedXI"]
        )
        self.assertEqual(drafted_row["position"], first["finalPosition"])
        for key in (
            "played",
            "wins",
            "draws",
            "losses",
            "points",
            "goalsFor",
            "goalsAgainst",
            "goalDifference",
        ):
            self.assertEqual(drafted_row[key], first[key])
        projection = first["projection"]
        self.assertIn(projection["projectedPosition"], range(1, 11))
        for key in (
            "titleProbability",
            "topFourProbability",
            "perfectProbability",
        ):
            self.assertGreaterEqual(projection[key], 0)
            self.assertLessEqual(projection[key], 1)
        self.assertIn("earned", first["awards"])
        self.assertIn("biggestWin", first["records"])
        self.assertIn("highestScoringMatch", first["records"])

    def test_static_scorer_names_cannot_perturb_season_outcomes(self) -> None:
        def outcome_payload(result: dict) -> dict:
            match_fields = (
                "fixtureId",
                "matchweek",
                "venue",
                "homeTeamId",
                "awayTeamId",
                "homeGoals",
                "awayGoals",
                "goalsFor",
                "goalsAgainst",
                "outcome",
                "pointsEarned",
                "expectedGoalsFor",
                "expectedGoalsAgainst",
                "opponentGoalMinutes",
            )
            summary_fields = (
                "played",
                "wins",
                "draws",
                "losses",
                "points",
                "goalsFor",
                "goalsAgainst",
                "goalDifference",
                "finalPosition",
            )
            return {
                "seed": result["seed"],
                "seasonId": result["seasonId"],
                "summary": {
                    field: result[field] for field in summary_fields
                },
                "projection": result["projection"],
                "matches": [
                    {field: match[field] for field in match_fields}
                    for match in result["matches"]
                ],
                "leagueTable": result["leagueTable"],
            }

        picks = completed_xi_picks()
        baseline = api_rooms.RoomStore._season_result(
            38_000_474, 1, picks
        )
        relabeled_opponents = tuple(
            {
                **opponent,
                "scorers": tuple(reversed(opponent["scorers"])),
            }
            for opponent in api_rooms.HNL_SIMULATION_OPPONENTS
        )
        with mock.patch.object(
            api_rooms,
            "HNL_SIMULATION_OPPONENTS",
            relabeled_opponents,
        ):
            relabeled = api_rooms.RoomStore._season_result(
                38_000_474, 1, picks
            )

        baseline_outcomes = outcome_payload(baseline)
        self.assertEqual(baseline_outcomes, outcome_payload(relabeled))
        serialized = json.dumps(
            baseline_outcomes,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        self.assertEqual(
            hashlib.sha256(serialized).hexdigest(),
            "bacce4d20405d861e7a337e0c21c4a8874bf452c25d81481aaf4136457bf4ff2",
        )

    def test_seed_changes_season_but_viewer_seat_does_not(self) -> None:
        picks = completed_xi_picks()
        baseline = api_rooms.RoomStore._season_result(2026, 1, picks)
        different_seed = api_rooms.RoomStore._season_result(2027, 1, picks)
        different_seat = api_rooms.RoomStore._season_result(2026, 2, picks)
        self.assertNotEqual(baseline["matches"], different_seed["matches"])
        self.assertEqual(baseline["matches"], different_seat["matches"])
        self.assertNotEqual(baseline["seed"], different_seat["seed"])


class RoomStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.clock = FakeClock()
        self.store = api_rooms.RoomStore(
            Path(self.temp_dir.name) / "rooms.sqlite3",
            test_catalog(),
            room_ttl_seconds=60,
            password_scrypt_n=1 << 14,
            clock=self.clock,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def create(
        self,
        *,
        mode: str = "solo",
        name: str = "Host",
        seed: int = 380,
        target_picks: int = 2,
        max_players: int | None = None,
        account_id: str | None = None,
    ) -> dict:
        settings = {
            "formation": "4-3-3",
            "targetPicks": target_picks,
            "seasonStart": 2000,
            "seasonEnd": 2002,
        }
        if max_players is not None:
            settings["maxPlayers"] = max_players
        return self.store.create_room(
            {
                "mode": mode,
                "name": name,
                "seed": seed,
                "settings": settings,
            },
            account_id=account_id,
        )

    @staticmethod
    def own_participant(room: dict) -> dict:
        viewer_id = room["viewerParticipantId"]
        return next(
            participant
            for participant in room["participants"]
            if participant["id"] == viewer_id
        )

    def first_available(self, room: dict) -> tuple[dict, str]:
        participant = self.own_participant(room)
        player = next(
            item
            for item in participant["currentSpin"]["players"]
            if item["available"]
        )
        return player, player["eligibleSlotIds"][0]

    def complete_one_pick(self, created: dict) -> dict:
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            created["room"]["version"],
        )
        room = self.store.spin(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
        )
        player, slot_id = self.first_available(room)
        return self.store.pick(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
            player["id"],
            slot_id,
        )

    def test_create_start_spin_pick_and_complete(self) -> None:
        created = self.create(target_picks=1)
        self.assertEqual(len(created["roomCode"]), 6)
        self.assertEqual(created["room"]["status"], "lobby")
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            created["room"]["version"],
        )
        room = self.store.spin(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
        )
        player, slot_id = self.first_available(room)
        room = self.store.pick(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
            player["id"],
            slot_id,
        )
        self.assertEqual(room["status"], "complete")
        participant = self.own_participant(room)
        self.assertEqual(participant["turn"], 1)
        self.assertEqual(participant["picks"][0]["player"]["id"], player["id"])
        self.assertEqual(participant["result"]["played"], 36)
        self.assertEqual(
            participant["result"]["points"],
            participant["result"]["wins"] * 3 + participant["result"]["draws"],
        )
        self.assertEqual(room["leaderboard"][0]["participantId"], participant["id"])
        fetched = self.store.get_room(
            created["roomCode"], created["participantToken"]
        )
        self.assertEqual(fetched["participants"][0]["result"], participant["result"])

    def test_version_and_turn_conflicts_are_rejected(self) -> None:
        created = self.create()
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            created["room"]["version"],
        )
        pre_spin_version = room["version"]
        room = self.store.spin(
            created["roomCode"],
            created["participantToken"],
            pre_spin_version,
            0,
        )
        with self.assertRaises(api_rooms.RequestError) as stale_version:
            self.store.spin(
                created["roomCode"],
                created["participantToken"],
                pre_spin_version,
                0,
                reroll=True,
            )
        self.assertEqual(stale_version.exception.code, "version_conflict")
        player, slot_id = self.first_available(room)
        with self.assertRaises(api_rooms.RequestError) as stale_turn:
            self.store.pick(
                created["roomCode"],
                created["participantToken"],
                room["version"],
                9,
                player["id"],
                slot_id,
            )
        self.assertEqual(stale_turn.exception.code, "turn_conflict")

    def test_same_seed_and_seat_produce_same_first_spin(self) -> None:
        first = self.create(seed=12345, target_picks=1)
        second = self.create(seed=12345, target_picks=1)
        first_room = self.store.start_room(
            first["roomCode"],
            first["participantToken"],
            first["room"]["version"],
        )
        second_room = self.store.start_room(
            second["roomCode"],
            second["participantToken"],
            second["room"]["version"],
        )
        first_room = self.store.spin(
            first["roomCode"],
            first["participantToken"],
            first_room["version"],
            0,
        )
        second_room = self.store.spin(
            second["roomCode"],
            second["participantToken"],
            second_room["version"],
            0,
        )
        self.assertEqual(
            self.own_participant(first_room)["currentSpin"]["clubSeasonId"],
            self.own_participant(second_room)["currentSpin"]["clubSeasonId"],
        )

    def test_live_join_capacity_host_rule_and_private_spin(self) -> None:
        created = self.create(mode="live", max_players=2)
        joined = self.store.join_room(
            created["roomCode"],
            {"name": "Ana"},
        )
        self.assertEqual(len(joined["room"]["participants"]), 2)
        with self.assertRaises(api_rooms.RequestError) as full:
            self.store.join_room(created["roomCode"], {"name": "Ivan"})
        self.assertEqual(full.exception.code, "room_full")
        with self.assertRaises(api_rooms.RequestError) as not_host:
            self.store.start_room(
                created["roomCode"],
                joined["participantToken"],
                joined["room"]["version"],
            )
        self.assertEqual(not_host.exception.code, "host_required")
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            joined["room"]["version"],
        )
        room = self.store.spin(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
        )
        ana_view = self.store.get_room(
            created["roomCode"],
            joined["participantToken"],
        )
        host = next(item for item in ana_view["participants"] if item["isHost"])
        self.assertTrue(host["currentSpin"]["squadHidden"])
        self.assertIsNone(host["currentSpin"]["players"])

    def test_live_room_uses_shared_mirrored_manager_fixtures(self) -> None:
        created = self.create(
            mode="live",
            target_picks=1,
            max_players=2,
            seed=20_260_726,
        )
        joined = self.store.join_room(
            created["roomCode"],
            {"name": "Ana"},
        )
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            joined["room"]["version"],
        )
        room = self.store.spin(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
        )
        host_player, host_slot = self.first_available(room)
        room = self.store.pick(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
            host_player["id"],
            host_slot,
        )
        room = self.store.spin(
            created["roomCode"],
            joined["participantToken"],
            room["version"],
            0,
        )
        guest_player, guest_slot = self.first_available(room)
        room = self.store.pick(
            created["roomCode"],
            joined["participantToken"],
            room["version"],
            0,
            guest_player["id"],
            guest_slot,
        )
        self.assertEqual(room["status"], "complete")
        host = next(
            participant
            for participant in room["participants"]
            if participant["id"] == created["participantId"]
        )
        guest = next(
            participant
            for participant in room["participants"]
            if participant["id"] == joined["participantId"]
        )
        self.assertEqual(len(host["result"]["matches"]), 36)
        self.assertEqual(len(guest["result"]["matches"]), 36)
        self.assertEqual(host["result"]["seasonMode"], "shared-live")
        self.assertEqual(
            host["result"]["seasonId"],
            guest["result"]["seasonId"],
        )
        self.assertEqual(
            host["result"]["managerParticipantId"],
            created["participantId"],
        )
        self.assertEqual(
            guest["result"]["managerParticipantId"],
            joined["participantId"],
        )
        host_h2h = {
            match["fixtureId"]: match
            for match in host["result"]["matches"]
            if match["isManagerVsManager"]
        }
        guest_h2h = {
            match["fixtureId"]: match
            for match in guest["result"]["matches"]
            if match["isManagerVsManager"]
        }
        self.assertEqual(set(host_h2h), set(guest_h2h))
        self.assertEqual(len(host_h2h), 4)
        for fixture_id in host_h2h:
            host_match = host_h2h[fixture_id]
            guest_match = guest_h2h[fixture_id]
            self.assertEqual(host_match["matchType"], "manager-head-to-head")
            self.assertTrue(host_match["opponent"]["isHuman"])
            self.assertTrue(guest_match["opponent"]["isHuman"])
            self.assertEqual(
                host_match["opponent"]["participantId"],
                joined["participantId"],
            )
            self.assertEqual(
                guest_match["opponent"]["participantId"],
                created["participantId"],
            )
            self.assertNotEqual(host_match["venue"], guest_match["venue"])
            self.assertEqual(
                host_match["goalsFor"],
                guest_match["goalsAgainst"],
            )
            self.assertEqual(
                host_match["goalsAgainst"],
                guest_match["goalsFor"],
            )
            self.assertEqual(
                host_match["scorers"],
                guest_match["opponentScorers"],
            )
            self.assertEqual(
                host_match["opponentScorers"],
                guest_match["scorers"],
            )
            self.assertEqual(
                host_match["timeline"][-1]["goalsFor"],
                host_match["goalsFor"],
            )
            self.assertEqual(
                guest_match["timeline"][-1]["goalsFor"],
                guest_match["goalsFor"],
            )
            animation = host_match["animation"]
            self.assertEqual(animation["recommendedDurationMs"], 4_400)
            self.assertEqual(animation["extraDurationMs"], 3_000)
            self.assertEqual(animation["fullTimeHoldMs"], 400)
            self.assertEqual(animation["startLabel"], "0′")
            self.assertEqual(animation["endLabel"], "FT")
            timeline = host_match["timeline"]
            self.assertEqual(len(timeline), 92)
            self.assertEqual(timeline[0]["minute"], 0)
            self.assertEqual(timeline[0]["atMs"], 0)
            self.assertEqual(timeline[-1]["minuteLabel"], "FT")
            self.assertEqual(
                timeline[-1]["atMs"],
                animation["recommendedDurationMs"],
            )
            self.assertEqual(
                animation["goalEventCount"],
                host_match["goalsFor"] + host_match["goalsAgainst"],
            )
            self.assertEqual(
                sum(len(frame["events"]) for frame in timeline),
                host_match["goalsFor"] + host_match["goalsAgainst"],
            )

        table_fields = (
            "played",
            "wins",
            "draws",
            "losses",
            "points",
            "goalsFor",
            "goalsAgainst",
            "goalDifference",
            "position",
        )
        host_table = {
            row["teamId"]: tuple(row[field] for field in table_fields)
            for row in host["result"]["leagueTable"]
        }
        guest_table = {
            row["teamId"]: tuple(row[field] for field in table_fields)
            for row in guest["result"]["leagueTable"]
        }
        self.assertEqual(host_table, guest_table)
        self.assertEqual(
            sum(row["isHuman"] for row in host["result"]["leagueTable"]),
            2,
        )
        fetched = self.store.get_room(
            created["roomCode"],
            created["participantToken"],
        )
        fetched_host = next(
            participant
            for participant in fetched["participants"]
            if participant["id"] == created["participantId"]
        )
        self.assertEqual(fetched_host["result"], host["result"])

    def test_reposition_into_compatible_open_slot(self) -> None:
        created = self.create(target_picks=2)
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            created["room"]["version"],
        )
        room = self.store.spin(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
        )
        participant = self.own_participant(room)
        versatile = next(
            player
            for player in participant["currentSpin"]["players"]
            if len(player["eligibleSlotIds"]) >= 2
        )
        from_slot, to_slot = versatile["eligibleSlotIds"][:2]
        room = self.store.pick(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
            versatile["id"],
            from_slot,
        )
        room = self.store.move(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            from_slot,
            to_slot,
        )
        participant = self.own_participant(room)
        self.assertEqual(participant["picks"][0]["slotId"], to_slot)
        self.assertIn(to_slot, participant["filledSlotIds"])
        self.assertNotIn(from_slot, participant["filledSlotIds"])

    def test_concurrent_participant_moves_ignore_unrelated_room_version(self) -> None:
        created = self.create(mode="live", target_picks=2, max_players=2)
        joined = self.store.join_room(
            created["roomCode"],
            {"name": "Guest"},
        )
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            joined["room"]["version"],
        )
        move_requests: list[tuple[str, str, str]] = []
        for token in (
            created["participantToken"],
            joined["participantToken"],
        ):
            room = self.store.spin(
                created["roomCode"],
                token,
                room["version"],
                0,
            )
            participant = self.own_participant(room)
            versatile = next(
                player
                for player in participant["currentSpin"]["players"]
                if len(player["eligibleSlotIds"]) >= 2
            )
            from_slot, to_slot = versatile["eligibleSlotIds"][:2]
            room = self.store.pick(
                created["roomCode"],
                token,
                room["version"],
                0,
                versatile["id"],
                from_slot,
            )
            move_requests.append((token, from_slot, to_slot))

        shared_version = room["version"]
        barrier = threading.Barrier(3)
        outcomes: list[str] = []

        def worker(token: str, from_slot: str, to_slot: str) -> None:
            barrier.wait()
            try:
                self.store.move(
                    created["roomCode"],
                    token,
                    shared_version,
                    from_slot,
                    to_slot,
                )
                outcomes.append("ok")
            except api_rooms.RequestError as error:
                outcomes.append(error.code)

        threads = [
            threading.Thread(target=worker, args=request)
            for request in move_requests
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(outcomes, ["ok", "ok"])
        self.assertEqual(
            self.store.get_room(
                created["roomCode"],
                created["participantToken"],
            )["version"],
            shared_version + 2,
        )
        for token, from_slot, to_slot in move_requests:
            view = self.store.get_room(created["roomCode"], token)
            participant = self.own_participant(view)
            self.assertIn(to_slot, participant["filledSlotIds"])
            self.assertNotIn(from_slot, participant["filledSlotIds"])

    def test_stale_same_participant_lineup_move_is_rejected(self) -> None:
        created = self.create(target_picks=2)
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            created["room"]["version"],
        )
        room = self.store.spin(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
        )
        participant = self.own_participant(room)
        versatile = next(
            player
            for player in participant["currentSpin"]["players"]
            if len(player["eligibleSlotIds"]) >= 2
        )
        from_slot, to_slot = versatile["eligibleSlotIds"][:2]
        room = self.store.pick(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
            versatile["id"],
            from_slot,
        )
        before_move_version = room["version"]
        self.store.move(
            created["roomCode"],
            created["participantToken"],
            before_move_version,
            from_slot,
            to_slot,
        )
        with self.assertRaises(api_rooms.RequestError) as stale:
            self.store.move(
                created["roomCode"],
                created["participantToken"],
                before_move_version,
                to_slot,
                from_slot,
            )
        self.assertEqual(stale.exception.code, "version_conflict")

    def test_expired_room_is_visible_but_cannot_mutate(self) -> None:
        created = self.create()
        self.clock.value += 61
        room = self.store.get_room(
            created["roomCode"],
            created["participantToken"],
        )
        self.assertEqual(room["status"], "expired")
        with self.assertRaises(api_rooms.RequestError) as expired:
            self.store.start_room(
                created["roomCode"],
                created["participantToken"],
                room["version"],
            )
        self.assertEqual(expired.exception.status, 410)
        self.assertEqual(expired.exception.code, "room_expired")

    def test_concurrent_same_participant_spin_is_idempotent(self) -> None:
        created = self.create()
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            created["room"]["version"],
        )
        barrier = threading.Barrier(3)
        outcomes: list[str] = []
        spins: list[tuple[str, int]] = []

        def worker() -> None:
            barrier.wait()
            try:
                result = self.store.spin(
                    created["roomCode"],
                    created["participantToken"],
                    room["version"],
                    0,
                )
                outcomes.append("ok")
                current = self.own_participant(result)["currentSpin"]
                spins.append(
                    (current["clubSeasonId"], current["spinNumber"])
                )
            except api_rooms.RequestError as error:
                outcomes.append(error.code)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()
        self.assertEqual(outcomes, ["ok", "ok"])
        self.assertEqual(len(set(spins)), 1)
        self.assertEqual(spins[0][1], 1)
        fetched = self.store.get_room(
            created["roomCode"],
            created["participantToken"],
        )
        self.assertEqual(fetched["version"], room["version"] + 1)
        self.assertEqual(
            self.own_participant(fetched)["currentSpin"]["spinNumber"],
            1,
        )

    def test_concurrent_participant_spins_ignore_unrelated_room_version(self) -> None:
        created = self.create(mode="live", max_players=2)
        joined = self.store.join_room(
            created["roomCode"],
            {"name": "Guest"},
        )
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            joined["room"]["version"],
        )
        barrier = threading.Barrier(3)
        outcomes: list[str] = []

        def worker(token: str) -> None:
            barrier.wait()
            try:
                self.store.spin(
                    created["roomCode"],
                    token,
                    room["version"],
                    0,
                )
                outcomes.append("ok")
            except api_rooms.RequestError as error:
                outcomes.append(error.code)

        threads = [
            threading.Thread(
                target=worker,
                args=(created["participantToken"],),
            ),
            threading.Thread(
                target=worker,
                args=(joined["participantToken"],),
            ),
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(outcomes, ["ok", "ok"])
        host_view = self.store.get_room(
            created["roomCode"],
            created["participantToken"],
        )
        guest_view = self.store.get_room(
            created["roomCode"],
            joined["participantToken"],
        )
        self.assertIsNotNone(self.own_participant(host_view)["currentSpin"])
        self.assertIsNotNone(self.own_participant(guest_view)["currentSpin"])
        self.assertEqual(host_view["version"], room["version"] + 2)

    def test_concurrent_participant_picks_ignore_unrelated_room_version(self) -> None:
        created = self.create(mode="live", max_players=2)
        joined = self.store.join_room(
            created["roomCode"],
            {"name": "Guest"},
        )
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            joined["room"]["version"],
        )
        host_spin = self.store.spin(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
        )
        guest_spin = self.store.spin(
            created["roomCode"],
            joined["participantToken"],
            host_spin["version"],
            0,
        )
        host_player, host_slot = self.first_available(host_spin)
        guest_player, guest_slot = self.first_available(guest_spin)
        shared_version = guest_spin["version"]
        barrier = threading.Barrier(3)
        outcomes: list[str] = []

        def worker(token: str, player_id: str, slot_id: str) -> None:
            barrier.wait()
            try:
                self.store.pick(
                    created["roomCode"],
                    token,
                    shared_version,
                    0,
                    player_id,
                    slot_id,
                )
                outcomes.append("ok")
            except api_rooms.RequestError as error:
                outcomes.append(error.code)

        threads = [
            threading.Thread(
                target=worker,
                args=(
                    created["participantToken"],
                    host_player["id"],
                    host_slot,
                ),
            ),
            threading.Thread(
                target=worker,
                args=(
                    joined["participantToken"],
                    guest_player["id"],
                    guest_slot,
                ),
            ),
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(outcomes, ["ok", "ok"])
        host_view = self.store.get_room(
            created["roomCode"],
            created["participantToken"],
        )
        guest_view = self.store.get_room(
            created["roomCode"],
            joined["participantToken"],
        )
        self.assertEqual(host_view["version"], shared_version + 2)
        for view in (host_view, guest_view):
            participant = self.own_participant(view)
            self.assertEqual(participant["turn"], 1)
            self.assertEqual(len(participant["picks"]), 1)
            self.assertIsNone(participant["currentSpin"])

    def test_concurrent_same_participant_pick_is_idempotent(self) -> None:
        created = self.create()
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            created["room"]["version"],
        )
        room = self.store.spin(
            created["roomCode"],
            created["participantToken"],
            room["version"],
            0,
        )
        player, slot_id = self.first_available(room)
        shared_version = room["version"]
        barrier = threading.Barrier(3)
        outcomes: list[str] = []

        def worker() -> None:
            barrier.wait()
            try:
                self.store.pick(
                    created["roomCode"],
                    created["participantToken"],
                    shared_version,
                    0,
                    player["id"],
                    slot_id,
                )
                outcomes.append("ok")
            except api_rooms.RequestError as error:
                outcomes.append(error.code)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

        self.assertEqual(outcomes, ["ok", "ok"])
        fetched = self.store.get_room(
            created["roomCode"],
            created["participantToken"],
        )
        participant = self.own_participant(fetched)
        self.assertEqual(fetched["version"], shared_version + 1)
        self.assertEqual(participant["turn"], 1)
        self.assertEqual(len(participant["picks"]), 1)
        self.assertEqual(participant["picks"][0]["player"]["id"], player["id"])
        with self.assertRaises(api_rooms.RequestError) as conflicting_retry:
            self.store.pick(
                created["roomCode"],
                created["participantToken"],
                shared_version,
                0,
                player["id"],
                "different-slot",
            )
        self.assertEqual(conflicting_retry.exception.code, "turn_conflict")

    def test_account_password_session_and_generic_auth_failures(self) -> None:
        registered, session_token = self.store.register_account(
            {
                "username": "josip.hnl",
                "email": "JOSIP@example.com",
                "password": "correct horse battery staple 380",
            }
        )
        self.assertEqual(registered["account"]["email"], "josip@example.com")
        self.assertEqual(registered["stats"]["seasonsPlayed"], 0)
        self.assertGreaterEqual(len(session_token), 40)

        connection = self.store._connect()
        try:
            account_row = connection.execute(
                "SELECT * FROM accounts WHERE id = ?",
                (registered["account"]["id"],),
            ).fetchone()
            session_row = connection.execute(
                "SELECT * FROM auth_sessions WHERE account_id = ?",
                (registered["account"]["id"],),
            ).fetchone()
        finally:
            connection.close()
        self.assertNotEqual(
            account_row["password_hash"],
            "correct horse battery staple 380",
        )
        self.assertEqual(len(account_row["password_salt"]), 32)
        self.assertEqual(account_row["password_n"], 1 << 14)
        self.assertEqual(session_row["token_hash"], api_rooms._sha256(session_token))
        self.assertNotEqual(session_row["token_hash"], session_token)

        with self.assertRaises(api_rooms.RequestError) as duplicate:
            self.store.register_account(
                {
                    "username": "someone.else",
                    "email": "josip@example.com",
                    "password": "another sufficiently long password 99",
                }
            )
        self.assertEqual(duplicate.exception.code, "account_exists")
        with self.assertRaises(api_rooms.RequestError) as missing_account:
            self.store.login_account(
                {
                    "identifier": "nobody@example.com",
                    "password": "incorrect but valid length",
                }
            )
        with self.assertRaises(api_rooms.RequestError) as wrong_password:
            self.store.login_account(
                {
                    "identifier": "josip.hnl",
                    "password": "incorrect but valid length",
                }
            )
        self.assertEqual(missing_account.exception.code, "invalid_credentials")
        self.assertEqual(wrong_password.exception.code, "invalid_credentials")

        logged_in, second_token = self.store.login_account(
            {
                "identifier": "JOSIP.HNL",
                "password": "correct horse battery staple 380",
            }
        )
        self.assertEqual(logged_in["account"]["id"], registered["account"]["id"])
        self.store.logout_account(second_token)
        with self.assertRaises(api_rooms.RequestError) as logged_out:
            self.store.account_me(second_token)
        self.assertEqual(logged_out.exception.code, "authentication_required")
        self.assertEqual(
            self.store.account_me(session_token)["account"]["username"],
            "josip.hnl",
        )

    def test_password_reset_is_generic_one_time_and_revokes_sessions(self) -> None:
        deliveries: list[tuple[str, str, str]] = []
        delivery_ready = threading.Event()

        def capture_delivery(
            recipient: str,
            username: str,
            reset_url: str,
        ) -> None:
            deliveries.append((recipient, username, reset_url))
            delivery_ready.set()

        self.store._password_reset_sender = capture_delivery
        registered, old_session = self.store.register_account(
            {
                "username": "reset-user",
                "email": "reset@example.com",
                "password": "the original long account password",
            }
        )
        known_response = self.store.request_password_reset(
            {"email": "RESET@example.com"}
        )
        self.assertTrue(delivery_ready.wait(timeout=1))
        self.assertEqual(
            known_response,
            {
                "ok": True,
                "message": api_rooms.PASSWORD_RESET_GENERIC_MESSAGE,
            },
        )
        self.assertNotIn("resetToken", known_response)
        self.assertEqual(deliveries[0][:2], ("reset@example.com", "reset-user"))
        reset_url = deliveries[0][2]
        self.assertTrue(
            reset_url.startswith("http://localhost:3001/#reset-password=")
        )
        reset_token = reset_url.split("#reset-password=", 1)[1]

        unknown_response = self.store.request_password_reset(
            {"email": "unknown@example.com"}
        )
        self.assertEqual(unknown_response, known_response)
        self.assertEqual(len(deliveries), 1)

        connection = self.store._connect()
        try:
            token_row = connection.execute(
                "SELECT * FROM password_reset_tokens WHERE account_id = ?",
                (registered["account"]["id"],),
            ).fetchone()
        finally:
            connection.close()
        self.assertEqual(token_row["token_hash"], api_rooms._sha256(reset_token))
        self.assertNotEqual(token_row["token_hash"], reset_token)

        with self.assertRaises(api_rooms.RequestError) as weak_password:
            self.store.complete_password_reset(
                {"token": reset_token, "newPassword": "too short"}
            )
        self.assertEqual(weak_password.exception.code, "invalid_password")
        completed = self.store.complete_password_reset(
            {
                "token": reset_token,
                "newPassword": "the replacement long account password",
            }
        )
        self.assertEqual(completed, {"ok": True})
        with self.assertRaises(api_rooms.RequestError) as replayed:
            self.store.complete_password_reset(
                {
                    "token": reset_token,
                    "newPassword": "short",
                }
            )
        self.assertEqual(replayed.exception.code, "invalid_reset_token")
        with self.assertRaises(api_rooms.RequestError) as revoked:
            self.store.account_me(old_session)
        self.assertEqual(revoked.exception.code, "authentication_required")
        with self.assertRaises(api_rooms.RequestError) as old_password:
            self.store.login_account(
                {
                    "identifier": "reset-user",
                    "password": "the original long account password",
                }
            )
        self.assertEqual(old_password.exception.code, "invalid_credentials")
        logged_in, _ = self.store.login_account(
            {
                "identifier": "reset-user",
                "password": "the replacement long account password",
            }
        )
        self.assertEqual(logged_in["account"]["id"], registered["account"]["id"])

    def test_password_reset_cooldown_preserves_links_and_expiry(self) -> None:
        deliveries: list[str] = []
        delivery_ready = threading.Event()

        def capture_delivery(_email: str, _username: str, reset_url: str) -> None:
            deliveries.append(reset_url)
            delivery_ready.set()

        self.store._password_reset_sender = capture_delivery
        self.store.register_account(
            {
                "username": "recovery-user",
                "email": "recovery@example.com",
                "password": "a sufficiently long recovery password",
            }
        )
        first = self.store.request_password_reset(
            {"email": "recovery@example.com"}
        )
        self.assertTrue(delivery_ready.wait(timeout=1))
        first_token = deliveries[-1].split("#reset-password=", 1)[1]

        delivery_ready.clear()
        repeated = self.store.request_password_reset(
            {"email": "recovery@example.com"}
        )
        self.assertEqual(repeated, first)
        self.assertFalse(delivery_ready.wait(timeout=0.05))
        self.assertEqual(len(deliveries), 1)

        self.clock.value += 61
        self.store.request_password_reset({"email": "recovery@example.com"})
        self.assertTrue(delivery_ready.wait(timeout=1))
        second_token = deliveries[-1].split("#reset-password=", 1)[1]
        self.assertNotEqual(first_token, second_token)

        # A new request does not make the earlier unexpired recovery link fail.
        self.store.complete_password_reset(
            {
                "token": first_token,
                "newPassword": "a newly recovered account password",
            }
        )
        with self.assertRaises(api_rooms.RequestError) as sibling_token:
            self.store.complete_password_reset(
                {
                    "token": second_token,
                    "newPassword": "yet another recovered account password",
                }
            )
        self.assertEqual(sibling_token.exception.code, "invalid_reset_token")

        delivery_ready.clear()
        self.clock.value += 61
        self.store.request_password_reset({"email": "recovery@example.com"})
        self.assertTrue(delivery_ready.wait(timeout=1))
        expired_token = deliveries[-1].split("#reset-password=", 1)[1]
        self.clock.value += self.store.password_reset_seconds + 1
        with self.assertRaises(api_rooms.RequestError) as expired:
            self.store.complete_password_reset(
                {
                    "token": expired_token,
                    "newPassword": "an expired replacement account password",
                }
            )
        self.assertEqual(expired.exception.code, "invalid_reset_token")

    def test_password_reset_rechecks_expiry_after_password_hashing(self) -> None:
        deliveries: list[str] = []
        delivery_ready = threading.Event()

        def capture_delivery(_email: str, _username: str, reset_url: str) -> None:
            deliveries.append(reset_url)
            delivery_ready.set()

        self.store._password_reset_sender = capture_delivery
        self.store.register_account(
            {
                "username": "hash-expiry-user",
                "email": "hash-expiry@example.com",
                "password": "the original hash expiry password",
            }
        )
        self.store.request_password_reset({"email": "hash-expiry@example.com"})
        self.assertTrue(delivery_ready.wait(timeout=1))
        reset_token = deliveries[-1].split("#reset-password=", 1)[1]
        original_digest = self.store._password_digest

        def slow_digest(
            password: str,
            salt_hex: str,
            *,
            work_factor: int | None = None,
        ) -> str:
            self.clock.value += self.store.password_reset_seconds + 1
            return original_digest(
                password,
                salt_hex,
                work_factor=work_factor,
            )

        with mock.patch.object(
            self.store,
            "_password_digest",
            side_effect=slow_digest,
        ):
            with self.assertRaises(api_rooms.RequestError) as expired:
                self.store.complete_password_reset(
                    {
                        "token": reset_token,
                        "newPassword": "the replacement hash expiry password",
                    }
                )
        self.assertEqual(expired.exception.code, "invalid_reset_token")
        logged_in, _ = self.store.login_account(
            {
                "identifier": "hash-expiry-user",
                "password": "the original hash expiry password",
            }
        )
        self.assertEqual(logged_in["account"]["username"], "hash-expiry-user")

    def test_password_reset_dev_exposure_and_starttls_delivery(self) -> None:
        environment = {
            "HNL_PUBLIC_URL": "https://shnl36.example/game?ignored=yes",
            "HNL_PASSWORD_RESET_EXPOSE_TOKEN": "true",
            "HNL_SMTP_HOST": "smtp.example.com",
            "HNL_SMTP_PORT": "2525",
            "HNL_SMTP_USERNAME": "smtp-user",
            "HNL_SMTP_PASSWORD": "smtp-password",
            "HNL_SMTP_FROM": "SHNL 36-0 <no-reply@example.com>",
            "HNL_SMTP_STARTTLS": "1",
        }
        with mock.patch.dict(os.environ, environment):
            with tempfile.TemporaryDirectory() as temp_dir:
                store = api_rooms.RoomStore(
                    Path(temp_dir) / "reset.sqlite3",
                    test_catalog(),
                    password_scrypt_n=1 << 14,
                    password_reset_sender=lambda *_args: None,
                )
                store.register_account(
                    {
                        "username": "exposed-user",
                        "email": "exposed@example.com",
                        "password": "a long developer reset password",
                    }
                )
                response = store.request_password_reset(
                    {"email": "exposed@example.com"}
                )
                self.assertIn("resetToken", response)
                self.assertEqual(
                    response["resetUrl"],
                    "https://shnl36.example/game/#reset-password="
                    + response["resetToken"],
                )

                smtp_context = object()
                with (
                    mock.patch.object(
                        api_rooms.ssl,
                        "create_default_context",
                        return_value=smtp_context,
                    ),
                    mock.patch.object(api_rooms.smtplib, "SMTP") as smtp_class,
                ):
                    smtp = smtp_class.return_value.__enter__.return_value
                    store._send_password_reset_email(
                        "player@example.com",
                        "player-one",
                        response["resetUrl"],
                    )
                smtp_class.assert_called_once_with(
                    "smtp.example.com",
                    2525,
                    timeout=10,
                )
                self.assertEqual(smtp.ehlo.call_count, 2)
                smtp.starttls.assert_called_once_with(context=smtp_context)
                smtp.login.assert_called_once_with("smtp-user", "smtp-password")
                message = smtp.send_message.call_args.args[0]
                self.assertEqual(message["To"], "player@example.com")
                self.assertIn(response["resetUrl"], message.get_content())

    def test_password_policy_allows_unicode_and_has_no_composition_rule(self) -> None:
        registered, _ = self.store.register_account(
            {
                "username": "unicode-user",
                "email": "unicode@example.com",
                "password": "duga lozinka bez brojeva 🔐",
            }
        )
        self.assertEqual(registered["account"]["username"], "unicode-user")
        with self.assertRaises(api_rooms.RequestError) as too_short:
            self.store.register_account(
                {
                    "username": "short-user",
                    "email": "short@example.com",
                    "password": "short password",
                }
            )
        self.assertEqual(too_short.exception.code, "invalid_password")

    def test_completed_authenticated_season_is_snapshotted_once(self) -> None:
        registered, session_token = self.store.register_account(
            {
                "username": "history-user",
                "email": "history@example.com",
                "password": "long enough history password",
            }
        )
        created = self.create(
            target_picks=1,
            account_id=registered["account"]["id"],
        )
        room = self.complete_one_pick(created)
        participant = self.own_participant(room)
        history = self.store.account_history(session_token)
        self.assertEqual(history["total"], 1)
        self.assertEqual(history["stats"]["seasonsPlayed"], 1)
        self.assertEqual(history["stats"]["points"], participant["result"]["points"])
        self.assertEqual(history["stats"]["wins"], participant["result"]["wins"])
        self.assertEqual(
            history["stats"]["goalDifference"],
            participant["result"]["goalDifference"],
        )
        summary = history["seasons"][0]
        self.assertEqual(summary["roomCode"], created["roomCode"])
        self.assertEqual(summary["formation"], "4-3-3")

        # Re-reading a completed room recomputes the deterministic simulation,
        # but the unique snapshot key prevents duplicate history entries.
        self.store.get_room(created["roomCode"], created["participantToken"])
        self.assertEqual(self.store.account_history(session_token)["total"], 1)
        detail = self.store.account_history_detail(session_token, summary["id"])
        self.assertEqual(detail["season"]["result"], participant["result"])
        self.assertEqual(len(detail["season"]["picks"]), 1)

        profile = self.store.public_profile("HISTORY-USER")["profile"]
        self.assertNotIn("email", profile)
        self.assertEqual(profile["stats"], history["stats"])
        self.assertNotIn("roomCode", profile["recentSeasons"][0])

    def test_account_can_claim_anonymous_completed_season(self) -> None:
        registered, session_token = self.store.register_account(
            {
                "username": "claim-user",
                "email": "claim@example.com",
                "password": "claim this completed season",
            }
        )
        account_id = registered["account"]["id"]

        first = self.create(
            seed=379,
            target_picks=1,
            account_id=account_id,
        )
        first_room = self.complete_one_pick(first)
        first_result = self.own_participant(first_room)["result"]
        before_claim = self.store.account_history(session_token)
        self.assertEqual(before_claim["total"], 1)
        self.assertEqual(before_claim["stats"]["seasonsPlayed"], 1)

        created = self.create(seed=380, target_picks=1)
        completed_room = self.complete_one_pick(created)
        claimed_result = self.own_participant(completed_room)["result"]
        claimed = self.store.claim_room_participant(
            created["roomCode"],
            created["participantToken"],
            account_id,
        )
        self.assertTrue(claimed["claimed"])
        expected_points = first_result["points"] + claimed_result["points"]
        self.assertEqual(claimed["stats"]["seasonsPlayed"], 2)
        self.assertEqual(claimed["stats"]["points"], expected_points)

        history = self.store.account_history(session_token)
        self.assertEqual(history["total"], 2)
        self.assertEqual(history["stats"], claimed["stats"])
        self.assertEqual(
            self.store.account_me(session_token)["stats"],
            claimed["stats"],
        )
        profile = self.store.public_profile("CLAIM-USER")["profile"]
        self.assertEqual(profile["stats"], claimed["stats"])
        self.assertEqual(len(profile["recentSeasons"]), 2)

        claimed_again = self.store.claim_room_participant(
            created["roomCode"],
            created["participantToken"],
            account_id,
        )
        self.assertTrue(claimed_again["claimed"])
        self.assertEqual(claimed_again["stats"], claimed["stats"])
        self.assertEqual(self.store.account_history(session_token)["total"], 2)

        other, _ = self.store.register_account(
            {
                "username": "other-user",
                "email": "other@example.com",
                "password": "another long account password",
            }
        )
        with self.assertRaises(api_rooms.RequestError) as conflict:
            self.store.claim_room_participant(
                created["roomCode"],
                created["participantToken"],
                other["account"]["id"],
            )
        self.assertEqual(conflict.exception.code, "participant_already_claimed")

    def test_auth_session_expires(self) -> None:
        _, session_token = self.store.register_account(
            {
                "username": "expiry-user",
                "email": "expiry@example.com",
                "password": "a sufficiently long passphrase",
            }
        )
        self.clock.value += self.store.auth_session_seconds + 1
        with self.assertRaises(api_rooms.RequestError) as expired:
            self.store.account_me(session_token)
        self.assertEqual(expired.exception.code, "authentication_required")

    def test_login_scrypt_does_not_hold_room_store_lock(self) -> None:
        self.store.register_account(
            {
                "username": "concurrency-user",
                "email": "concurrency@example.com",
                "password": "concurrent authentication password",
            }
        )
        verification_started = threading.Event()
        release_verification = threading.Event()
        room_created = threading.Event()
        login_errors: list[Exception] = []
        original_matches = self.store._password_matches

        def delayed_matches(*args: object, **kwargs: object) -> bool:
            verification_started.set()
            release_verification.wait(timeout=3)
            return original_matches(*args, **kwargs)

        def login() -> None:
            try:
                self.store.login_account(
                    {
                        "identifier": "concurrency-user",
                        "password": "concurrent authentication password",
                    }
                )
            except Exception as error:  # pragma: no cover - diagnostic path
                login_errors.append(error)

        def create_room() -> None:
            self.create(target_picks=1)
            room_created.set()

        with mock.patch.object(
            self.store,
            "_password_matches",
            side_effect=delayed_matches,
        ):
            login_thread = threading.Thread(target=login)
            room_thread = threading.Thread(target=create_room)
            login_thread.start()
            self.assertTrue(verification_started.wait(timeout=1))
            room_thread.start()
            created_while_hashing = room_created.wait(timeout=1)
            release_verification.set()
            login_thread.join(timeout=3)
            room_thread.join(timeout=3)
        self.assertTrue(created_while_hashing)
        self.assertFalse(login_errors)


class AccountSchemaMigrationTests(unittest.TestCase):
    def test_existing_participants_table_receives_nullable_account_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Path(temp_dir) / "legacy.sqlite3"
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE rooms (
                    code TEXT PRIMARY KEY,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    settings_json TEXT NOT NULL,
                    host_participant_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                );
                CREATE TABLE participants (
                    id TEXT PRIMARY KEY,
                    room_code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    seat INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    spin_count INTEGER NOT NULL,
                    rerolls_remaining INTEGER NOT NULL,
                    current_spin_json TEXT,
                    spin_history_json TEXT NOT NULL,
                    joined_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    UNIQUE(room_code, seat)
                );
                CREATE TABLE picks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_code TEXT NOT NULL,
                    participant_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    club_season_id TEXT NOT NULL,
                    player_season_id TEXT NOT NULL,
                    person_id TEXT NOT NULL,
                    slot_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    UNIQUE(participant_id, turn_index),
                    UNIQUE(participant_id, slot_id),
                    UNIQUE(participant_id, player_season_id)
                );
                """
            )
            connection.close()
            store = api_rooms.RoomStore(
                database,
                test_catalog(),
                password_scrypt_n=1 << 14,
            )
            migrated = store._connect()
            try:
                columns = {
                    row["name"]
                    for row in migrated.execute(
                        "PRAGMA table_info(participants)"
                    ).fetchall()
                }
                tables = {
                    row["name"]
                    for row in migrated.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
            finally:
                migrated.close()
            self.assertIn("account_id", columns)
            self.assertIn("lineup_version", columns)
            self.assertIn("accounts", tables)
            self.assertIn("auth_sessions", tables)
            self.assertIn("password_reset_tokens", tables)
            self.assertIn("season_history", tables)


class HTTPAdapterTests(unittest.TestCase):
    def test_health_create_and_cors_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = api_rooms.RoomStore(
                Path(temp_dir) / "rooms.sqlite3",
                test_catalog(),
                password_scrypt_n=1 << 14,
            )
            try:
                server = api_rooms.make_server(store, "127.0.0.1", 0)
            except PermissionError:
                self.skipTest("The execution sandbox does not permit socket binding.")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                preflight = urllib.request.Request(
                    base + "/rooms",
                    method="OPTIONS",
                    headers={"Origin": "http://localhost:3001"},
                )
                with urllib.request.urlopen(preflight) as response:
                    self.assertEqual(response.status, 204)
                    self.assertEqual(
                        response.headers["Access-Control-Allow-Origin"],
                        "*",
                    )
                with urllib.request.urlopen(base + "/health") as response:
                    health = json.load(response)
                self.assertTrue(health["ok"])
                body = json.dumps(
                    {
                        "mode": "solo",
                        "name": "HTTP Host",
                        "seed": 7,
                        "settings": {
                            "targetPicks": 1,
                            "seasonStart": 2000,
                            "seasonEnd": 2002,
                        },
                    }
                ).encode()
                request = urllib.request.Request(
                    base + "/rooms",
                    data=body,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(request) as response:
                    created = json.load(response)
                self.assertEqual(response.status, 201)
                self.assertEqual(created["room"]["status"], "lobby")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

    def test_account_cookie_history_cors_and_rate_limit(self) -> None:
        environment = {
            "HNL_ALLOWED_ORIGINS": "http://localhost:3001",
            "HNL_AUTH_RATE_LIMIT_ATTEMPTS": "1",
            "HNL_AUTH_RATE_LIMIT_WINDOW_SECONDS": "60",
            "HNL_PASSWORD_RESET_EXPOSE_TOKEN": "true",
        }
        with mock.patch.dict(os.environ, environment):
            with tempfile.TemporaryDirectory() as temp_dir:
                store = api_rooms.RoomStore(
                    Path(temp_dir) / "rooms.sqlite3",
                    test_catalog(),
                    password_scrypt_n=1 << 14,
                    password_reset_sender=lambda *_args: None,
                )
                try:
                    server = api_rooms.make_server(store, "127.0.0.1", 0)
                except PermissionError:
                    self.skipTest(
                        "The execution sandbox does not permit socket binding."
                    )
                thread = threading.Thread(
                    target=server.serve_forever,
                    daemon=True,
                )
                thread.start()
                base = f"http://127.0.0.1:{server.server_address[1]}"
                cookie_jar = http.cookiejar.CookieJar()
                opener = urllib.request.build_opener(
                    urllib.request.HTTPCookieProcessor(cookie_jar)
                )

                def json_request(
                    path: str,
                    *,
                    payload: dict | None = None,
                    method: str = "GET",
                ) -> tuple[dict, object]:
                    body = json.dumps(payload).encode() if payload is not None else None
                    request = urllib.request.Request(
                        base + path,
                        data=body,
                        method=method,
                        headers={
                            "Content-Type": "application/json",
                            "Origin": "http://localhost:3001",
                        },
                    )
                    response = opener.open(request)
                    return json.load(response), response

                try:
                    registered, response = json_request(
                        "/account/register",
                        payload={
                            "username": "http-user",
                            "email": "http@example.com",
                            "password": "a long HTTP account password",
                        },
                        method="POST",
                    )
                    self.assertEqual(response.status, 201)
                    cookie_header = response.headers["Set-Cookie"]
                    self.assertIn("HttpOnly", cookie_header)
                    self.assertIn("SameSite=Lax", cookie_header)
                    self.assertNotIn("Secure", cookie_header)
                    self.assertEqual(
                        response.headers["Access-Control-Allow-Origin"],
                        "http://localhost:3001",
                    )
                    self.assertEqual(
                        response.headers["Access-Control-Allow-Credentials"],
                        "true",
                    )
                    self.assertNotIn("password", registered["account"])

                    me, _ = json_request("/account/me")
                    self.assertEqual(me["account"]["username"], "http-user")
                    history, _ = json_request("/account/history")
                    self.assertEqual(history["total"], 0)
                    profile, _ = json_request("/profiles/http-user")
                    self.assertNotIn("email", profile["profile"])

                    with self.assertRaises(urllib.error.HTTPError) as bad_login:
                        json_request(
                            "/account/login",
                            payload={
                                "identifier": "http-user",
                                "password": "wrong but sufficiently long",
                            },
                            method="POST",
                        )
                    self.assertEqual(bad_login.exception.code, 401)
                    with self.assertRaises(urllib.error.HTTPError) as limited:
                        json_request(
                            "/account/login",
                            payload={
                                "identifier": "http-user",
                                "password": "a long HTTP account password",
                            },
                            method="POST",
                        )
                    self.assertEqual(limited.exception.code, 429)
                    limited_payload = json.load(limited.exception)
                    self.assertEqual(
                        limited_payload["error"]["code"],
                        "auth_rate_limited",
                    )

                    reset_requested, response = json_request(
                        "/account/password-reset/request",
                        payload={"email": "http@example.com"},
                        method="POST",
                    )
                    self.assertEqual(response.status, 202)
                    self.assertTrue(reset_requested["ok"])
                    self.assertIn("resetToken", reset_requested)
                    reset_complete, response = json_request(
                        "/account/password-reset/complete",
                        payload={
                            "token": reset_requested["resetToken"],
                            "newPassword": "a new long HTTP account password",
                        },
                        method="POST",
                    )
                    self.assertEqual(reset_complete, {"ok": True})
                    # Password reset revokes every server-side session and
                    # clears this browser's now-stale session cookie too.
                    self.assertIn("Max-Age=0", response.headers["Set-Cookie"])
                    with self.assertRaises(urllib.error.HTTPError) as reset_anon:
                        json_request("/account/me")
                    self.assertEqual(reset_anon.exception.code, 401)

                    logged_out, response = json_request(
                        "/account/logout",
                        payload={},
                        method="POST",
                    )
                    self.assertTrue(logged_out["ok"])
                    self.assertIn("Max-Age=0", response.headers["Set-Cookie"])
                    with self.assertRaises(urllib.error.HTTPError) as anonymous:
                        json_request("/account/me")
                    self.assertEqual(anonymous.exception.code, 401)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
