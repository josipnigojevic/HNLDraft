import json
import tempfile
import unittest
from pathlib import Path

from api_rooms import FORMATIONS, Catalog
from scripts import build_hnl_draft_catalog as catalog


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OVERRIDES_PATH = REPOSITORY_ROOT / "data" / "historical_position_overrides.json"
SUPPLEMENT_PATH = REPOSITORY_ROOT / "data" / "supplemental_club_seasons.json"
SQUAD_ENRICHMENT_PATH = (
    REPOSITORY_ROOT / "data" / "transfermarkt_squad_supplements.json"
)
CATALOG_PATH = REPOSITORY_ROOT / "data" / "hnl_draft_catalog.json"


class PositionIntegrityTests(unittest.TestCase):
    def test_four_digit_season_start_is_not_shifted_by_1900_years(self) -> None:
        self.assertEqual(catalog.season_start_year("2001/02"), 2001)
        self.assertEqual(catalog.season_start_year("95/96"), 1995)

    def test_goalkeeper_cannot_be_combined_with_outfield_roles(self) -> None:
        for positions in (["GK", "ST"], ["ST", "CB", "GK"]):
            with self.subTest(positions=positions):
                with self.assertRaisesRegex(
                    ValueError,
                    "GK cannot be combined with an outfield role",
                ):
                    catalog.validate_position_assignment(
                        "GK",
                        positions,
                        context="test-player",
                    )

    def test_unresolved_hns_player_is_unk_and_not_selectable(self) -> None:
        source = (
            "riznica_klubovi_pobjednici_prvenstava"
            "<h2>Test Club</h2>"
            "<h3>Šampionska momčad:</h3>"
            "<p>Unresolved Player (12/1), trener: Test Coach</p>"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "hns_riznica_1995-96.html"
            path.write_text(source, encoding="utf-8")
            records = catalog.load_hns_champion_squads(
                Path(temp_dir),
                {},
                {},
                {},
            )
        self.assertEqual(len(records), 1)
        player = records[0]["players"][0]
        self.assertEqual(player["positionGroup"], "UNVERIFIED")
        self.assertEqual(player["positions"], ["UNK"])
        self.assertFalse(player["draftEligible"])
        self.assertIsNone(player["positionSource"])

    def test_cited_broad_role_does_not_expand_to_exact_roles(self) -> None:
        overrides = catalog.load_position_overrides(OVERRIDES_PATH)
        viduka = overrides[catalog.normalized_name("Mark Viduka")]
        ladic = overrides[catalog.normalized_name("Dražen Ladić")]
        self.assertEqual(viduka["positionGroup"], "FWD")
        self.assertEqual(viduka["positions"], ["FWD"])
        self.assertEqual(ladic["positionGroup"], "GK")
        self.assertEqual(ladic["positions"], ["GK"])
        self.assertTrue(viduka["source"]["url"].startswith("https://"))

    def test_profile_roles_do_not_invent_secondary_positions(self) -> None:
        cases = (
            (("Defender", "Left-Back"), ("DEF", ["LB"])),
            (("Midfield", "Central Midfield"), ("MID", ["CM"])),
            (("Attack", "Left Winger"), ("FWD", ["LW"])),
            (("Attack", "Centre-Forward"), ("FWD", ["CF"])),
            (("Defender", ""), ("DEF", ["DEF"])),
            (("Midfield", ""), ("MID", ["MID"])),
            (("Attack", ""), ("FWD", ["FWD"])),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(catalog.role_for(*source), expected)

    def test_performance_player_name_uses_only_source_backed_fallbacks(self) -> None:
        self.assertEqual(
            catalog.resolve_performance_player_name(
                {
                    "player_name": "Primary Name (7)",
                    "first_name": "Ignored",
                    "last_name": "Fallback",
                },
                "7",
                {"full_name": "Ignored Index Name"},
            ),
            "Primary Name",
        )
        self.assertEqual(
            catalog.resolve_performance_player_name(
                {
                    "player_name": "",
                    "first_name": "Roger",
                    "last_name": "Tamba M'Pinda",
                },
                "427502",
            ),
            "Roger Tamba M'Pinda",
        )
        self.assertEqual(
            catalog.resolve_performance_player_name(
                {"player_name": ""},
                "228434",
                {"full_name": "Jordan N'Kololo"},
            ),
            "Jordan N'Kololo",
        )
        self.assertEqual(
            catalog.resolve_performance_player_name(
                {"player_name": ""},
                "228434",
                {"name": "Jordan N'Kololo"},
            ),
            "Jordan N'Kololo",
        )
        self.assertIsNone(
            catalog.resolve_performance_player_name(
                {"player_name": ""},
                "427502",
            )
        )

    def test_rijeka_position_repairs_are_cited_and_conservative(self) -> None:
        overrides = catalog.load_position_overrides(OVERRIDES_PATH)
        expected = {
            "Ahmad Sharbini": ("FWD", ["ST"]),
            "Daniel Šarić": ("DEF", ["RB"]),
            "Dario Knežević": ("DEF", ["DEF"]),
            "Ivan Mance": ("GK", ["GK"]),
            "Mario Tadejević": ("DEF", ["LB"]),
            "Sergej Jakirović": ("DEF", ["CB"]),
        }
        for name, (position_group, positions) in expected.items():
            with self.subTest(name=name):
                override = overrides[catalog.normalized_name(name)]
                self.assertEqual(override["positionGroup"], position_group)
                self.assertEqual(override["positions"], positions)
                self.assertTrue(override["source"]["url"].startswith("https://"))


class ClubSeasonPlayabilityTests(unittest.TestCase):
    @staticmethod
    def player(
        index: int,
        group: str,
        positions: list[str],
        *,
        source_player_id: str | None = None,
        draft_eligible: bool = True,
    ) -> dict:
        return {
            "id": f"player-{index}",
            "sourcePlayerId": source_player_id or f"person-{index}",
            "name": f"Player {index}",
            "positionGroup": group,
            "positions": positions,
            "draftEligible": draft_eligible,
        }

    @staticmethod
    def record(players: list[dict]) -> dict:
        return {
            "id": "test-club-2000",
            "club": "Test Club",
            "season": "2000/01",
            "players": players,
            "coverage": {"status": "test"},
        }

    def test_pipeline_slot_definitions_match_runtime_formations(self) -> None:
        runtime = {
            name: tuple((slot.category, slot.accepted) for slot in slots)
            for name, slots in FORMATIONS.items()
        }
        self.assertEqual(catalog.LEGAL_XI_FORMATIONS, runtime)

    def test_fewer_than_eleven_unique_players_is_not_playable(self) -> None:
        players = [
            self.player(0, "GK", ["GK"]),
            *[self.player(index, "DEF", ["DEF"]) for index in range(1, 5)],
            *[self.player(index, "MID", ["MID"]) for index in range(5, 8)],
            *[self.player(index, "FWD", ["FWD"]) for index in range(8, 10)],
        ]
        assessment = catalog.assess_club_season_playability(
            self.record(players)
        )
        self.assertFalse(assessment["playable"])
        self.assertEqual(assessment["uniquePlayers"], 10)
        self.assertIn(
            "fewer-than-11-unique-players",
            assessment["reasons"],
        )
        self.assertIn("no-legal-xi", assessment["reasons"])

    def test_duplicate_person_rows_do_not_count_twice(self) -> None:
        players = [
            self.player(0, "GK", ["GK"]),
            *[self.player(index, "DEF", ["DEF"]) for index in range(1, 5)],
            *[self.player(index, "MID", ["MID"]) for index in range(5, 9)],
            self.player(9, "FWD", ["FWD"]),
            self.player(10, "FWD", ["FWD"], source_player_id="person-9"),
        ]
        assessment = catalog.assess_club_season_playability(
            self.record(players)
        )
        self.assertFalse(assessment["playable"])
        self.assertEqual(assessment["playerRows"], 11)
        self.assertEqual(assessment["uniquePlayers"], 10)
        self.assertEqual(assessment["duplicatePlayerRows"], 1)

    def test_eleven_players_without_a_legal_xi_are_quarantined(self) -> None:
        players = [
            self.player(index, "MID", ["CM"])
            for index in range(11)
        ]
        playable, incomplete = catalog.partition_playable_club_seasons(
            [self.record(players)]
        )
        self.assertEqual(playable, [])
        self.assertEqual(len(incomplete), 1)
        assessment = incomplete[0]["coverage"]["playability"]
        self.assertEqual(assessment["uniquePlayers"], 11)
        self.assertEqual(assessment["draftEligibleUniquePlayers"], 11)
        self.assertEqual(assessment["legalFormations"], [])
        self.assertEqual(
            assessment["reasons"],
            ["no-legal-xi", "missing-supported-formations"],
        )
        self.assertEqual(
            assessment["missingSupportedFormations"],
            list(catalog.LEGAL_XI_FORMATIONS),
        )

    def test_distinct_players_that_fill_every_runtime_formation_are_playable(
        self,
    ) -> None:
        roles = [
            ("GK", ["GK"]),
            *[("DEF", ["DEF"])] * 5,
            *[("MID", ["MID"])] * 5,
            *[("FWD", ["FWD"])] * 3,
        ]
        players = [
            self.player(index, group, positions)
            for index, (group, positions) in enumerate(roles)
        ]
        assessment = catalog.assess_club_season_playability(
            self.record(players)
        )
        self.assertTrue(assessment["playable"])
        self.assertEqual(assessment["reasons"], [])
        self.assertEqual(
            assessment["legalFormations"],
            list(catalog.LEGAL_XI_FORMATIONS),
        )
        self.assertEqual(assessment["missingSupportedFormations"], [])

    def test_enrichment_preserves_stats_repairs_roles_and_appends_players(
        self,
    ) -> None:
        base = {
            **self.record(
                [
                    {
                        **self.player(0, "UNVERIFIED", ["UNK"]),
                        "appearances": 27,
                        "goals": 4,
                        "seasonRating": 78,
                        "marketValuePeakEur": 2_000_000,
                        "confidence": 0.3,
                    }
                ]
            ),
            "clubId": "100",
            "seasonStart": 2000,
            "confidence": 0.58,
        }
        enrichment = {
            **self.record(
                [
                    {
                        **self.player(20, "DEF", ["CB"]),
                        "sourcePlayerId": "person-0",
                        "appearances": None,
                        "goals": None,
                        "seasonRating": 66,
                        "dateOfBirth": "1980-01-02",
                        "marketValueSeasonEur": 1_000_000,
                        "marketValuePeakEur": None,
                        "confidence": 0.8,
                        "positionSource": {
                            "name": "Full squad page",
                            "url": "https://example.test/squad",
                        },
                        "positionDisclosure": "Source-backed exact role.",
                    },
                    self.player(1, "GK", ["GK"]),
                ]
            ),
            "clubId": "100",
            "seasonStart": 2000,
            "confidence": 0.8,
            "source": {
                "name": "Full squad page",
                "url": "https://example.test/squad",
            },
        }
        merged = catalog.merge_club_season_enrichment(base, enrichment)
        self.assertEqual(len(merged["players"]), 2)
        existing = next(
            player
            for player in merged["players"]
            if player["sourcePlayerId"] == "person-0"
        )
        self.assertEqual(existing["appearances"], 27)
        self.assertEqual(existing["goals"], 4)
        self.assertEqual(existing["seasonRating"], 78)
        self.assertEqual(existing["marketValuePeakEur"], 2_000_000)
        self.assertEqual(existing["marketValueSeasonEur"], 1_000_000)
        self.assertEqual(existing["dateOfBirth"], "1980-01-02")
        self.assertEqual(existing["positionGroup"], "DEF")
        self.assertEqual(existing["positions"], ["CB"])
        details = merged["coverage"]["enrichment"]
        self.assertEqual(details["matchedRows"], 1)
        self.assertEqual(details["appendedRows"], 1)
        self.assertEqual(details["positionRepairs"], 1)

    def test_enrichment_can_promote_a_below_threshold_source_fragment(
        self,
    ) -> None:
        partial = {
            **self.record([self.player(0, "GK", ["GK"])]),
            "clubId": "100",
            "seasonStart": 2000,
            "confidence": 0.4,
        }
        enrichment = {
            **self.record([self.player(1, "DEF", ["CB"])]),
            "clubId": "100",
            "seasonStart": 2000,
            "confidence": 0.8,
            "source": {
                "name": "Full squad page",
                "url": "https://example.test/squad",
            },
        }
        candidates, enriched_keys = catalog.merge_club_season_enrichments(
            [],
            [partial],
            [enrichment],
        )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(len(candidates[0]["players"]), 2)
        self.assertEqual(
            enriched_keys,
            {("test club", "2000/01")},
        )


class SupplementalCoverageTests(unittest.TestCase):
    def test_enrichment_factual_fields_feed_only_the_fallback_rating(
        self,
    ) -> None:
        payload = {
            "clubSeasons": [
                {
                    "clubId": "100",
                    "club": "Test Club",
                    "season": "2000/01",
                    "confidence": 0.8,
                    "source": {
                        "name": "Full squad page",
                        "url": "https://example.test/squad",
                    },
                    "players": [
                        {
                            "sourcePlayerId": "9",
                            "name": "Source Player",
                            "positionGroup": "DEF",
                            "positions": ["CB"],
                            "dateOfBirth": "1980-01-02",
                            "marketValueEur": 1_000_000,
                        }
                    ],
                }
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "enrichments.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            records = catalog.load_supplemental_club_seasons(
                path,
                {},
                {},
                {},
                id_prefix="enrichment",
            )
        player = records[0]["players"][0]
        self.assertEqual(player["sourcePlayerId"], "9")
        self.assertEqual(player["dateOfBirth"], "1980-01-02")
        self.assertEqual(player["marketValueSeasonEur"], 1_000_000)
        self.assertIsNone(player["marketValuePeakEur"])
        self.assertGreater(player["seasonRating"], 66)
        self.assertIn(
            "exact position",
            player["positionDisclosure"],
        )

    def test_hajduk_2001_02_transcription_and_provenance(self) -> None:
        overrides = catalog.load_position_overrides(OVERRIDES_PATH)
        records = catalog.load_supplemental_club_seasons(
            SUPPLEMENT_PATH,
            {},
            {},
            overrides,
        )
        self.assertEqual(len(records), 9)
        record = next(
            record
            for record in records
            if (record["club"], record["season"])
            == ("Hajduk Split", "2001/02")
        )
        self.assertEqual((record["club"], record["season"]), ("Hajduk Split", "2001/02"))
        self.assertEqual(record["seasonStart"], 2001)
        self.assertEqual(record["id"], "supplement-447-2001")
        self.assertEqual(len(record["players"]), 32)
        self.assertIn("hr.wikipedia.org", record["source"]["url"])
        players = {player["name"]: player for player in record["players"]}
        self.assertEqual(
            (players["Hrvoje Vejić"]["appearances"], players["Hrvoje Vejić"]["goals"]),
            (28, 4),
        )
        self.assertEqual(
            (
                players["Tomislav Erceg"]["appearances"],
                players["Tomislav Erceg"]["goals"],
            ),
            (21, 13),
        )
        self.assertEqual(
            (
                players["Stipe Pletikosa"]["appearances"],
                players["Stipe Pletikosa"]["goals"],
            ),
            (28, 0),
        )
        self.assertEqual(players["Tonči Pirija"]["positions"], ["MID"])
        self.assertTrue(players["Tonči Pirija"]["draftEligible"])

    def test_rijeka_2001_02_starts_substitutes_and_goals(self) -> None:
        overrides = catalog.load_position_overrides(OVERRIDES_PATH)
        records = catalog.load_supplemental_club_seasons(
            SUPPLEMENT_PATH,
            {},
            {},
            overrides,
        )
        record = next(
            record
            for record in records
            if (record["club"], record["season"])
            == ("HNK Rijeka", "2001/02")
        )
        self.assertEqual(len(record["players"]), 25)
        players = {player["name"]: player for player in record["players"]}
        self.assertEqual(
            (
                players["Natko Rački"]["starts"],
                players["Natko Rački"]["substituteAppearances"],
                players["Natko Rački"]["appearances"],
                players["Natko Rački"]["goals"],
            ),
            (12, 12, 24, 13),
        )
        self.assertEqual(
            (
                players["Sandro Klić"]["starts"],
                players["Sandro Klić"]["substituteAppearances"],
                players["Sandro Klić"]["appearances"],
            ),
            (0, 9, 9),
        )
        self.assertIn("en.wikipedia.org", record["source"]["url"])

    def test_dinamo_partial_snapshot_preserves_unknown_appearances(self) -> None:
        overrides = catalog.load_position_overrides(OVERRIDES_PATH)
        records = catalog.load_supplemental_club_seasons(
            SUPPLEMENT_PATH,
            {},
            {},
            overrides,
        )
        record = next(
            record
            for record in records
            if (record["club"], record["season"])
            == ("Dinamo Zagreb", "2001/02")
        )
        self.assertEqual(len(record["players"]), 26)
        players = {player["name"]: player for player in record["players"]}
        self.assertIsNone(players["Dario Zahora"]["appearances"])
        self.assertEqual(players["Dario Zahora"]["goals"], 14)
        self.assertEqual(players["Mario Jurić"]["positions"], ["MID"])
        self.assertEqual(
            players["Mario Jurić"]["positionSource"]["url"],
            record["source"]["url"],
        )
        self.assertIn(
            "were not inferred",
            players["Dario Zahora"]["statsDisclosure"],
        )

    def test_rijeka_2004_05_through_2009_10_transcriptions(self) -> None:
        overrides = catalog.load_position_overrides(OVERRIDES_PATH)
        records = catalog.load_supplemental_club_seasons(
            SUPPLEMENT_PATH,
            {},
            {},
            overrides,
        )
        rijeka = {
            record["season"]: record
            for record in records
            if record["club"] == "HNK Rijeka"
            and "2004/05" <= record["season"] <= "2009/10"
        }
        expected = {
            "2004/05": (23, "Tomislav Erceg", 31, 1, 32, 17),
            "2005/06": (27, "Davor Vugrinec", 23, 1, 24, 15),
            "2006/07": (36, "Ahmad Sharbini", 16, 11, 27, 21),
            "2007/08": (25, "Radomir Đalović", 29, 2, 31, 18),
            "2008/09": (34, "Anas Sharbini", 27, 0, 27, 14),
            "2009/10": (
                32,
                "Ramón Ignacio Fernández",
                18,
                9,
                27,
                6,
            ),
        }
        self.assertEqual(set(rijeka), set(expected))
        for season, (
            row_count,
            player_name,
            starts,
            substitutes,
            appearances,
            goals,
        ) in expected.items():
            with self.subTest(season=season):
                record = rijeka[season]
                self.assertEqual(len(record["players"]), row_count)
                self.assertIn(
                    season.replace("/", "%E2%80%93"),
                    record["source"]["url"],
                )
                player = next(
                    player
                    for player in record["players"]
                    if player["name"] == player_name
                )
                self.assertEqual(
                    (
                        player["starts"],
                        player["substituteAppearances"],
                        player["appearances"],
                        player["goals"],
                    ),
                    (starts, substitutes, appearances, goals),
                )


class CheckedInCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    def test_catalog_has_no_goalkeeper_outfield_or_universal_fallback(self) -> None:
        universal = {
            "GK",
            "RB",
            "CB",
            "LB",
            "DM",
            "CM",
            "AM",
            "RW",
            "LW",
            "ST",
        }
        for record in self.payload["clubSeasons"]:
            for player in record["players"]:
                positions = player["positions"]
                with self.subTest(
                    season=record["season"],
                    club=record["club"],
                    player=player["name"],
                ):
                    self.assertFalse("GK" in positions and positions != ["GK"])
                    self.assertNotEqual(set(positions), universal)
                    if positions == ["UNK"]:
                        self.assertFalse(player["draftEligible"])

    def test_every_legacy_or_supplemental_squad_can_field_default_xi(self) -> None:
        records = [
            record
            for record in self.payload["clubSeasons"]
            if record["id"].startswith(("hns-", "supplement-"))
        ]
        self.assertEqual(len(records), 18)
        for record in records:
            eligible = [
                player
                for player in record["players"]
                if player.get("draftEligible", True)
            ]
            counts = {
                group: sum(player["positionGroup"] == group for player in eligible)
                for group in ("GK", "DEF", "MID", "FWD")
            }
            with self.subTest(season=record["season"], club=record["club"]):
                self.assertGreaterEqual(counts["GK"], 1)
                self.assertGreaterEqual(counts["DEF"], 4)
                self.assertGreaterEqual(counts["MID"], 3)
                self.assertGreaterEqual(counts["FWD"], 3)

    def test_hajduk_supplement_is_checked_in_and_omissions_remain_explicit(self) -> None:
        matches = [
            record
            for record in self.payload["clubSeasons"]
            if record["club"] == "Hajduk Split" and record["season"] == "2001/02"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["seasonStart"], 2001)
        self.assertEqual(matches[0]["coverage"]["status"], "source-supplement")
        self.assertEqual(self.payload["coverage"]["clubSeasons"], 255)
        self.assertEqual(self.payload["coverage"]["players"], 8_196)
        self.assertEqual(self.payload["coverage"]["omittedClubSeasons"], 7)
        self.assertEqual(len(self.payload["omitted"]), 7)

    def test_every_playable_squad_has_eleven_players_and_all_formations(self) -> None:
        expected_formations = list(catalog.LEGAL_XI_FORMATIONS)
        for record in self.payload["clubSeasons"]:
            with self.subTest(season=record["season"], club=record["club"]):
                assessment = catalog.assess_club_season_playability(record)
                self.assertTrue(assessment["playable"])
                self.assertGreaterEqual(
                    assessment["draftEligibleUniquePlayers"],
                    11,
                )
                self.assertEqual(
                    assessment["legalFormations"],
                    expected_formations,
                )
                self.assertEqual(
                    record["coverage"]["playability"]["legalFormations"],
                    expected_formations,
                )

    def test_previously_underfilled_hajduk_and_osijek_are_restored(self) -> None:
        expected = {
            ("HNK Hajduk Split", "2005/06"),
            ("NK Osijek", "2005/06"),
        }
        restored = {
            (record["club"], record["season"]): record
            for record in self.payload["clubSeasons"]
            if (record["club"], record["season"]) in expected
        }
        self.assertEqual(set(restored), expected)
        for key, record in restored.items():
            with self.subTest(club=key[0], season=key[1]):
                self.assertGreaterEqual(len(record["players"]), 25)
                self.assertEqual(
                    record["coverage"]["status"],
                    "source-enriched",
                )

    def test_checked_in_enrichment_is_offline_and_source_cited(self) -> None:
        payload = json.loads(SQUAD_ENRICHMENT_PATH.read_text(encoding="utf-8"))
        self.assertFalse(payload["method"]["liveRuntimeDependency"])
        self.assertEqual(payload["method"]["groupCount"], 143)
        self.assertEqual(len(payload["clubSeasons"]), 143)
        for record in payload["clubSeasons"]:
            with self.subTest(season=record["season"], club=record["club"]):
                self.assertTrue(record["source"]["url"].startswith("https://"))
                self.assertGreaterEqual(len(record["players"]), 1)

    def test_api_loader_accepts_every_generated_player_row(self) -> None:
        emitted_player_rows = sum(
            len(record["players"]) for record in self.payload["clubSeasons"]
        )
        self.assertEqual(
            self.payload["coverage"]["players"],
            emitted_player_rows,
        )
        loaded = Catalog.load(CATALOG_PATH)
        self.assertEqual(loaded.player_count, emitted_player_rows)
        self.assertEqual(loaded.metadata["loaderSkippedPlayerRows"], 0)


if __name__ == "__main__":
    unittest.main()
