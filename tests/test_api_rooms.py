import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

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
        for match in first["matches"]:
            opponent_id = match["opponent"]["id"]
            opponent_counts[opponent_id] = opponent_counts.get(opponent_id, 0) + 1
            key = (opponent_id, match["venue"])
            venue_counts[key] = venue_counts.get(key, 0) + 1
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
            }
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

    def test_concurrent_same_version_spin_commits_once(self) -> None:
        created = self.create()
        room = self.store.start_room(
            created["roomCode"],
            created["participantToken"],
            created["room"]["version"],
        )
        barrier = threading.Barrier(3)
        outcomes: list[str] = []

        def worker() -> None:
            barrier.wait()
            try:
                self.store.spin(
                    created["roomCode"],
                    created["participantToken"],
                    room["version"],
                    0,
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
        self.assertCountEqual(outcomes, ["ok", "version_conflict"])


class HTTPAdapterTests(unittest.TestCase):
    def test_health_create_and_cors_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = api_rooms.RoomStore(
                Path(temp_dir) / "rooms.sqlite3",
                test_catalog(),
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


if __name__ == "__main__":
    unittest.main()
