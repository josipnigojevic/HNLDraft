#!/usr/bin/env python3
"""Build the local HNL draft catalogue from public season-performance data.

The generated ratings are editorial game inputs. They are deliberately kept
separate from the factual player, club, season, appearance, goal, assist, and
discipline fields supplied by the source datasets.

Example:
    python3 scripts/build_hnl_draft_catalog.py \
      --performances /private/tmp/tm_player_performances.csv \
      --profiles /private/tmp/tm_player_profiles.csv \
      --player-index /private/tmp/hnl_players.csv.gz \
      --output data/hnl_draft_catalog.json
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


COMPETITION_ID = "KR1"
MIN_REQUESTED_SEASON = 1995
SOURCE_DATASET_URL = "https://github.com/salimt/football-datasets"
SOURCE_SCHEMA_URL = (
    "https://github.com/salimt/football-datasets"
    "#%EF%B8%8F-complete-data-schema--entity-relationships"
)
TRANSFERMARKT_COMPETITION_URL = (
    "https://www.transfermarkt.com/supersport-hnl/startseite/wettbewerb/KR1"
)
HNS_CURRENT_COMPETITION_URL = (
    "https://semafor.hns.family/en/competitions/100391485/supersport-hnl/"
)
HNS_RIZNICA_URL = "https://riznica.hns.family/klubovi/"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSITION_OVERRIDES = (
    REPOSITORY_ROOT / "data" / "historical_position_overrides.json"
)
DEFAULT_SUPPLEMENTAL_CLUB_SEASONS = (
    REPOSITORY_ROOT / "data" / "supplemental_club_seasons.json"
)
DEFAULT_CLUB_SEASON_ENRICHMENTS = (
    REPOSITORY_ROOT / "data" / "transfermarkt_squad_supplements.json"
)

EXACT_POSITION_CODES = {
    "GK",
    "RB",
    "RWB",
    "CB",
    "LB",
    "LWB",
    "DM",
    "CM",
    "AM",
    "RM",
    "LM",
    "RW",
    "LW",
    "ST",
    "SS",
    "CF",
}
POSITION_GROUP_CODES = {"DEF", "MID", "FWD"}
VALID_POSITION_CODES = EXACT_POSITION_CODES | POSITION_GROUP_CODES | {"UNK"}

# These slot definitions mirror the formations exposed by the room API.  They
# live here as plain data so catalog validation does not need to import or boot
# the API service.  Each tuple is ``(unit, accepted exact roles)``.  A cited
# broad role (DEF/MID/FWD) is compatible with every slot in its unit, matching
# the runtime draft rules.
GK = ("GK", frozenset({"GK"}))
RB = ("DEF", frozenset({"RB", "RWB", "CB"}))
RCB = ("DEF", frozenset({"CB", "RB"}))
CB = ("DEF", frozenset({"CB"}))
LCB = ("DEF", frozenset({"CB", "LB"}))
LB = ("DEF", frozenset({"LB", "LWB", "CB"}))
RWB = ("DEF", frozenset({"RWB", "RB", "RW"}))
LWB = ("DEF", frozenset({"LWB", "LB", "LW"}))
DM = ("MID", frozenset({"DM", "CM"}))
CM = ("MID", frozenset({"CM", "DM", "AM"}))
AM = ("MID", frozenset({"AM", "CM", "SS"}))
RM = ("MID", frozenset({"RM", "RW", "CM"}))
LM = ("MID", frozenset({"LM", "LW", "CM"}))
WIDE_RM = ("MID", frozenset({"RM", "RW", "RWB", "CM"}))
WIDE_LM = ("MID", frozenset({"LM", "LW", "LWB", "CM"}))
RW = ("FWD", frozenset({"RW", "RM", "LW", "AM"}))
LW = ("FWD", frozenset({"LW", "LM", "RW", "AM"}))
NARROW_RW = ("FWD", frozenset({"RW", "RM", "AM"}))
NARROW_LW = ("FWD", frozenset({"LW", "LM", "AM"}))
ST = ("FWD", frozenset({"ST", "CF"}))
RST = ("FWD", frozenset({"ST", "CF", "RW"}))
LST = ("FWD", frozenset({"ST", "CF", "LW"}))
SS = ("FWD", frozenset({"SS", "AM", "ST", "CF"}))
RAM = ("MID", frozenset({"AM", "CM", "RW"}))
LAM = ("MID", frozenset({"AM", "CM", "LW"}))

LEGAL_XI_FORMATIONS = {
    "4-3-3": (GK, RB, RCB, LCB, LB, DM, CM, CM, RW, ST, LW),
    "4-4-2": (GK, RB, RCB, LCB, LB, RM, CM, CM, LM, RST, LST),
    "4-2-3-1": (GK, RB, RCB, LCB, LB, DM, DM, RW, AM, LW, ST),
    "4-5-1": (GK, RB, RCB, LCB, LB, RM, DM, CM, DM, LM, ST),
    "3-4-3": (
        GK,
        RCB,
        CB,
        LCB,
        WIDE_RM,
        CM,
        CM,
        WIDE_LM,
        NARROW_RW,
        ST,
        NARROW_LW,
    ),
    "3-5-2": (GK, RCB, CB, LCB, RWB, DM, CM, CM, LWB, RST, LST),
    "5-4-1": (GK, RWB, RCB, CB, LCB, LWB, RM, CM, CM, LM, ST),
    "4-1-2-1-2": (GK, RB, RCB, LCB, LB, DM, CM, CM, AM, RST, LST),
    "4-4-1-1": (GK, RB, RCB, LCB, LB, RM, CM, CM, LM, SS, ST),
    "5-3-2": (GK, RWB, RCB, CB, LCB, LWB, CM, CM, CM, RST, LST),
    "3-4-1-2": (
        GK,
        RCB,
        CB,
        LCB,
        WIDE_RM,
        CM,
        CM,
        WIDE_LM,
        AM,
        RST,
        LST,
    ),
    "4-2-2-2": (GK, RB, RCB, LCB, LB, DM, DM, RAM, LAM, RST, LST),
}

CLUB_ACCENTS = {
    "dinamo": "#1769ff",
    "hajduk": "#ef3f4b",
    "rijeka": "#6ac7ff",
    "osijek": "#3154d8",
    "istra": "#f1cf32",
    "slaven": "#dd2f39",
    "lokomotiva": "#4673b9",
    "gorica": "#d72c38",
    "varazdin": "#2367a7",
    "varaždin": "#2367a7",
    "vukovar": "#f2b52f",
    "sibenik": "#f36d24",
    "šibenik": "#f36d24",
    "rudes": "#d9ad1d",
    "rudeš": "#d9ad1d",
    "cibalia": "#3f7ddd",
    "inter": "#f2ce25",
    "zadar": "#3368c6",
    "zagreb": "#d52a35",
    "split": "#d33637",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--performances", required=True, type=Path)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--player-index", type=Path)
    parser.add_argument(
        "--hns-riznica-dir",
        type=Path,
        help=(
            "Optional directory of official HNS pages named "
            "hns_riznica_YYYY-YY.html. Champion squads are added for seasons "
            "before the secondary performance dataset begins."
        ),
    )
    parser.add_argument(
        "--position-overrides",
        type=Path,
        default=DEFAULT_POSITION_OVERRIDES,
        help=(
            "Source-cited historical position overrides. Broad source roles "
            "(DEF/MID/FWD) remain broad rather than inventing exact positions."
        ),
    )
    parser.add_argument(
        "--supplemental-club-seasons",
        type=Path,
        default=DEFAULT_SUPPLEMENTAL_CLUB_SEASONS,
        help=(
            "Source-cited club-season rosters that are absent from the "
            "performance input."
        ),
    )
    parser.add_argument(
        "--club-season-enrichments",
        type=Path,
        default=DEFAULT_CLUB_SEASON_ENRICHMENTS,
        help=(
            "Source-cited full squad pages merged into partial performance "
            "club-seasons before the playability gate."
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--minimum-squad-size",
        type=int,
        default=8,
        help="Keep source-backed club-seasons with at least this many players.",
    )
    return parser.parse_args()


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def as_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def optional_int(value: Any, *, context: str) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{context}: expected an integer or null") from error


def season_start_year(label: str) -> int:
    first = int(label.split("/", 1)[0])
    if first >= 1900:
        return first
    return 1900 + first if first >= 90 else 2000 + first


def long_season(label: str) -> str:
    start = season_start_year(label)
    return f"{start}/{str(start + 1)[-2:]}"


def clean_player_name(name: str, player_id: str) -> str:
    return re.sub(rf"\s+\({re.escape(player_id)}\)$", "", name).strip()


def resolve_performance_player_name(
    profile: dict[str, str],
    player_id: str,
    market_row: dict[str, str] | None = None,
) -> str | None:
    """Return a source-backed display name without manufacturing one."""
    profile_name = clean_player_name(profile.get("player_name", ""), player_id)
    if profile_name:
        return profile_name

    first_name = str(profile.get("first_name", "")).strip()
    last_name = str(profile.get("last_name", "")).strip()
    if first_name and last_name:
        return f"{first_name} {last_name}"

    if market_row:
        for field in ("full_name", "name"):
            market_name = clean_player_name(
                str(market_row.get(field, "")),
                player_id,
            )
            if market_name:
                return market_name
    return None


def normalized_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    without_marks = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def _slug(value: str) -> str:
    return normalized_name(value).replace(" ", "-") or "item"


def role_for(position: str, main_position: str) -> tuple[str, list[str]]:
    raw = position.lower()
    main = main_position.lower()
    detail = f"{raw} {main}"
    if "goalkeeper" in detail:
        return "GK", ["GK"]
    if "left wing-back" in detail or "left wingback" in detail:
        return "DEF", ["LWB"]
    if "right wing-back" in detail or "right wingback" in detail:
        return "DEF", ["RWB"]
    if "centre-back" in detail or "center-back" in detail:
        return "DEF", ["CB"]
    if "left-back" in detail or "left back" in detail:
        return "DEF", ["LB"]
    if "right-back" in detail or "right back" in detail:
        return "DEF", ["RB"]
    if "defensive midfield" in detail or "defensive midfielder" in detail:
        return "MID", ["DM"]
    if "attacking midfield" in detail or "attacking midfielder" in detail:
        return "MID", ["AM"]
    if "central midfield" in detail or "central midfielder" in detail:
        return "MID", ["CM"]
    if "left midfield" in detail or "left midfielder" in detail:
        return "MID", ["LM"]
    if "right midfield" in detail or "right midfielder" in detail:
        return "MID", ["RM"]
    if "left winger" in detail:
        return "FWD", ["LW"]
    if "right winger" in detail:
        return "FWD", ["RW"]
    if "second striker" in detail:
        return "FWD", ["SS"]
    if "centre-forward" in detail or "center-forward" in detail:
        return "FWD", ["CF"]
    if re.search(r"\bstriker\b", detail):
        return "FWD", ["ST"]
    if "defender" in detail or "defence" in detail or "defense" in detail:
        return "DEF", ["DEF"]
    if "midfield" in detail:
        return "MID", ["MID"]
    if "forward" in detail or "attack" in detail or "winger" in detail:
        return "FWD", ["FWD"]
    return "UNVERIFIED", ["UNK"]


def validate_position_assignment(
    position_group: str,
    positions: Iterable[str],
    *,
    context: str,
) -> list[str]:
    normalized = list(dict.fromkeys(str(position).upper() for position in positions))
    if not normalized:
        raise ValueError(f"{context}: positions must not be empty")
    invalid = set(normalized) - VALID_POSITION_CODES
    if invalid:
        raise ValueError(
            f"{context}: unsupported position code(s): {', '.join(sorted(invalid))}"
        )
    if "GK" in normalized and normalized != ["GK"]:
        raise ValueError(f"{context}: GK cannot be combined with an outfield role")
    if "UNK" in normalized and normalized != ["UNK"]:
        raise ValueError(f"{context}: UNK cannot be combined with another role")
    if position_group == "GK" and normalized != ["GK"]:
        raise ValueError(f"{context}: GK group must contain only GK")
    if position_group == "UNVERIFIED" and normalized != ["UNK"]:
        raise ValueError(f"{context}: unresolved roles must contain only UNK")
    if position_group not in {"GK", "DEF", "MID", "FWD", "UNVERIFIED"}:
        raise ValueError(f"{context}: unsupported position group {position_group!r}")
    if position_group != "GK" and "GK" in normalized:
        raise ValueError(f"{context}: outfield group cannot contain GK")
    return normalized


def load_position_overrides(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    overrides: dict[str, dict[str, Any]] = {}
    for row in payload.get("players", []):
        name = str(row.get("name", "")).strip()
        if not name:
            raise ValueError(f"{path}: position override is missing a player name")
        key = normalized_name(name)
        if key in overrides:
            raise ValueError(f"{path}: duplicate position override for {name}")
        group = str(row.get("positionGroup", "")).upper()
        positions = validate_position_assignment(
            group,
            row.get("positions", []),
            context=f"{path}:{name}",
        )
        source = row.get("source")
        if not isinstance(source, dict) or not source.get("url"):
            raise ValueError(f"{path}:{name}: a cited position source is required")
        overrides[key] = {
            **row,
            "name": name,
            "positionGroup": group,
            "positions": positions,
        }
    return overrides


def profiles_indexed_by_name(
    profiles: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for profile in profiles.values():
        player_id = profile["player_id"]
        name = resolve_performance_player_name(profile, player_id)
        if not name:
            continue
        result.setdefault(normalized_name(name), profile)
    return result


def resolve_historical_position(
    name: str,
    profiles_by_name: dict[str, dict[str, str]],
    market_rows_by_name: dict[str, dict[str, str]],
    position_overrides: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    name_key = normalized_name(name)
    profile = profiles_by_name.get(name_key)
    market_row = market_rows_by_name.get(name_key)
    override = position_overrides.get(name_key)
    if profile:
        group, positions = role_for(
            profile.get("position", ""), profile.get("main_position", "")
        )
        positions = validate_position_assignment(
            group,
            positions,
            context=f"profile:{name}",
        )
        return {
            "positionGroup": group,
            "positions": positions,
            "sourcePlayerId": str(profile["player_id"]),
            "nationality": profile.get("citizenship") or "Unknown",
            "highestMarketValue": (
                as_int(market_row.get("highest_market_value_in_eur"))
                if market_row
                else 0
            ),
            "positionConfidence": 0.72,
            "positionSource": {
                "name": "Transfermarkt-derived player profile",
                "url": SOURCE_DATASET_URL,
            },
            "draftEligible": group != "UNVERIFIED",
            "positionDisclosure": "Profile-backed position.",
        }
    if market_row:
        group, positions = role_for(
            market_row.get("sub_position", ""),
            market_row.get("position", ""),
        )
        positions = validate_position_assignment(
            group,
            positions,
            context=f"player-index:{name}",
        )
        return {
            "positionGroup": group,
            "positions": positions,
            "sourcePlayerId": str(market_row["player_id"]),
            "nationality": market_row.get("country_of_citizenship") or "Unknown",
            "highestMarketValue": as_int(
                market_row.get("highest_market_value_in_eur")
            ),
            "positionConfidence": 0.7,
            "positionSource": {
                "name": "Transfermarkt-derived player index",
                "url": market_row.get("url") or SOURCE_DATASET_URL,
            },
            "draftEligible": group != "UNVERIFIED",
            "positionDisclosure": "Player-index-backed position.",
        }
    if override:
        group = override["positionGroup"]
        positions = validate_position_assignment(
            group,
            override["positions"],
            context=f"position-override:{name}",
        )
        role_scope = (
            "broad position group"
            if positions in (["DEF"], ["MID"], ["FWD"])
            else "exact position"
        )
        return {
            "positionGroup": group,
            "positions": positions,
            "sourcePlayerId": str(
                override.get("sourcePlayerId") or f"source-{_slug(name)}"
            ),
            "nationality": override.get("nationality") or "Unknown",
            "highestMarketValue": 0,
            "positionConfidence": as_float(override.get("confidence")) or 0.8,
            "positionSource": override["source"],
            "draftEligible": True,
            "positionDisclosure": (
                f"Curated, cited {role_scope}; no other role is implied."
            ),
        }
    return {
        "positionGroup": "UNVERIFIED",
        "positions": ["UNK"],
        "sourcePlayerId": f"hns-{_slug(name)}",
        "nationality": "Unknown",
        "highestMarketValue": 0,
        "positionConfidence": 0.2,
        "positionSource": None,
        "draftEligible": False,
        "positionDisclosure": (
            "Position is absent from the available source cache. The player is "
            "retained as a roster fact but is not draft-selectable."
        ),
    }


def assert_catalog_position_integrity(
    club_seasons: Iterable[dict[str, Any]],
) -> None:
    for club_season in club_seasons:
        for player in club_season["players"]:
            if not str(player.get("name", "")).strip():
                raise ValueError(
                    f"{club_season['club']} {club_season['season']}: "
                    "player name must not be empty"
                )
            positions = validate_position_assignment(
                player["positionGroup"],
                player["positions"],
                context=(
                    f"{club_season['club']} {club_season['season']} "
                    f"{player['name']}"
                ),
            )
            if player.get("draftEligible", True) and positions == ["UNK"]:
                raise ValueError(
                    f"{club_season['club']} {club_season['season']} "
                    f"{player['name']}: UNK player cannot be draft-eligible"
                )


def _player_identity(player: dict[str, Any]) -> str:
    """Return the strongest available within-squad person identity."""
    source_player_id = str(player.get("sourcePlayerId") or "").strip()
    if source_player_id:
        return f"source:{source_player_id}"
    name = normalized_name(str(player.get("name") or ""))
    if name:
        return f"name:{name}"
    return f"row:{player.get('id')}"


def _slot_compatible(
    player: dict[str, Any],
    slot: tuple[str, frozenset[str]],
) -> bool:
    unit, accepted = slot
    positions = frozenset(
        str(position).upper() for position in player.get("positions", [])
    )
    return unit in positions or bool(accepted.intersection(positions))


def _can_field_formation(
    players: list[dict[str, Any]],
    slots: tuple[tuple[str, frozenset[str]], ...],
) -> bool:
    """Use maximum bipartite matching; one player may fill only one slot."""
    if len(players) < len(slots):
        return False
    slot_to_player: dict[int, int] = {}

    def assign(player_index: int, visited_slots: set[int]) -> bool:
        for slot_index, slot in enumerate(slots):
            if (
                slot_index in visited_slots
                or not _slot_compatible(players[player_index], slot)
            ):
                continue
            visited_slots.add(slot_index)
            current_player = slot_to_player.get(slot_index)
            if current_player is None or assign(current_player, visited_slots):
                slot_to_player[slot_index] = player_index
                return True
        return False

    for player_index in range(len(players)):
        assign(player_index, set())
        if len(slot_to_player) == len(slots):
            return True
    return False


def assess_club_season_playability(
    club_season: dict[str, Any],
) -> dict[str, Any]:
    """Describe whether a source squad is complete enough to enter the reel."""
    players = list(club_season.get("players") or [])
    unique_players: dict[str, dict[str, Any]] = {}
    eligible_players: dict[str, dict[str, Any]] = {}
    for player in players:
        identity = _player_identity(player)
        unique_players.setdefault(identity, player)
        if (
            player.get("draftEligible", True)
            and player.get("positions") != ["UNK"]
        ):
            eligible_players.setdefault(identity, player)

    eligible = list(eligible_players.values())
    legal_formations = [
        name
        for name, slots in LEGAL_XI_FORMATIONS.items()
        if _can_field_formation(eligible, slots)
    ]
    missing_formations = [
        name for name in LEGAL_XI_FORMATIONS if name not in legal_formations
    ]
    reasons: list[str] = []
    if len(unique_players) < 11:
        reasons.append("fewer-than-11-unique-players")
    if len(eligible_players) < 11:
        reasons.append("fewer-than-11-draft-eligible-players")
    if not legal_formations:
        reasons.append("no-legal-xi")
    if missing_formations:
        reasons.append("missing-supported-formations")

    position_groups = {
        group: sum(
            player.get("positionGroup") == group for player in eligible
        )
        for group in ("GK", "DEF", "MID", "FWD")
    }
    return {
        "playable": not reasons,
        "playerRows": len(players),
        "uniquePlayers": len(unique_players),
        "draftEligibleUniquePlayers": len(eligible_players),
        "duplicatePlayerRows": max(0, len(players) - len(unique_players)),
        "eligiblePositionGroups": position_groups,
        "legalFormations": legal_formations,
        "missingSupportedFormations": missing_formations,
        "reasons": reasons,
        "method": (
            "Eleven distinct, draft-eligible people assigned to eleven slots "
            "with maximum bipartite matching under the runtime role rules; "
            "the squad must satisfy every formation selectable before a spin."
        ),
    }


def partition_playable_club_seasons(
    club_seasons: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Annotate every candidate and quarantine squads that cannot field an XI."""
    playable: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    for club_season in club_seasons:
        assessment = assess_club_season_playability(club_season)
        coverage = dict(club_season.get("coverage") or {})
        coverage["playability"] = assessment
        annotated = {**club_season, "coverage": coverage}
        (playable if assessment["playable"] else incomplete).append(annotated)
    return playable, incomplete


def club_accent(name: str) -> str:
    lowered = name.lower()
    for key, accent in CLUB_ACCENTS.items():
        if key in lowered:
            return accent
    hue = int(hashlib.sha256(name.encode("utf-8")).hexdigest()[:4], 16) % 360
    return f"hsl({hue} 68% 54%)"


def market_value_score(value: int) -> float:
    if value <= 0:
        return 2.0
    return max(0.0, min(15.0, (math.log10(max(value, 100_000)) - 5.0) * 5.0))


def editorial_rating(
    *,
    position_group: str,
    appearances: int,
    minutes: int,
    goals: int,
    assists: int,
    clean_sheets: int,
    goals_conceded: int,
    highest_market_value: int,
) -> int:
    effective_minutes = minutes or appearances * 60
    nineties = max(1.0, effective_minutes / 90.0)
    appearance_score = min(5.0, math.log1p(max(0, appearances)) * 1.45)
    if position_group == "GK":
        performance = min(
            8.0,
            clean_sheets / max(1.0, appearances) * 10.0
            + max(0.0, 1.5 - goals_conceded / max(1.0, appearances)) * 1.5,
        )
    elif position_group == "DEF":
        performance = min(8.0, (goals * 1.7 + assists * 1.8) / nineties * 8.0)
    elif position_group == "MID":
        performance = min(8.0, (goals * 2.0 + assists * 2.5) / nineties * 5.0)
    else:
        performance = min(8.0, (goals * 2.7 + assists * 1.8) / nineties * 4.0)
    result = 62.0 + market_value_score(highest_market_value)
    result += appearance_score + performance
    return int(round(max(60.0, min(92.0, result))))


def load_profiles(path: Path) -> dict[str, dict[str, str]]:
    profiles: dict[str, dict[str, str]] = {}
    with open_text(path) as handle:
        for row in csv.DictReader(handle):
            profiles[row["player_id"]] = row
    return profiles


def load_market_values(
    path: Path | None,
) -> tuple[
    dict[str, int],
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
]:
    if path is None or not path.exists():
        return {}, {}, {}
    values: dict[str, int] = {}
    rows_by_name: dict[str, dict[str, str]] = {}
    rows_by_player_id: dict[str, dict[str, str]] = {}
    with open_text(path) as handle:
        for row in csv.DictReader(handle):
            player_id = row["player_id"]
            values[player_id] = as_int(row.get("highest_market_value_in_eur"))
            rows_by_player_id[player_id] = row
            indexed_name = str(row.get("full_name") or row.get("name") or "")
            if indexed_name.strip():
                rows_by_name[normalized_name(indexed_name)] = row
    return values, rows_by_name, rows_by_player_id


def iter_hnl_performances(path: Path) -> Iterable[dict[str, str]]:
    with open_text(path) as handle:
        for row in csv.DictReader(handle):
            if row.get("competition_id") != COMPETITION_ID:
                continue
            label = row.get("season_name", "")
            if not label or season_start_year(label) < MIN_REQUESTED_SEASON:
                continue
            yield row


def _strip_tags(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def load_hns_champion_squads(
    directory: Path | None,
    profiles: dict[str, dict[str, str]],
    market_rows_by_name: dict[str, dict[str, str]],
    position_overrides: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if directory is None or not directory.is_dir():
        return []
    profiles_by_name = profiles_indexed_by_name(profiles)
    records: list[dict[str, Any]] = []
    club_ids = {
        "croatia zagreb": "419",
        "dinamo zagreb": "419",
        "hajduk split": "447",
        "zagreb": "5107",
    }
    for path in sorted(directory.glob("hns_riznica_*.html")):
        filename_match = re.search(r"(\d{4})-(\d{2})", path.name)
        if not filename_match:
            continue
        start_year = int(filename_match.group(1))
        if start_year >= 2004:
            continue
        season = f"{start_year}/{filename_match.group(2)}"
        source_text = path.read_text(encoding="utf-8")
        match = re.search(
            r"riznica_klubovi_pobjednici_prvenstava.*?"
            r"<h2>(.*?)</h2>.*?"
            r"<h3>Šampionska momčad:</h3><p>(.*?)</p>",
            source_text,
            re.DOTALL,
        )
        if not match:
            continue
        club_name = _strip_tags(match.group(1))
        squad_text = _strip_tags(match.group(2))
        players: list[dict[str, Any]] = []
        for raw_entry in squad_text.split(","):
            entry = " ".join(raw_entry.split())
            if "trener" in entry.casefold():
                break
            player_match = re.match(
                r"(.+?)\s*\((\d+)(?:/(\d+))?\)\s*$",
                entry,
            )
            if not player_match:
                continue
            name = player_match.group(1).strip()
            appearances = int(player_match.group(2))
            goals = int(player_match.group(3) or 0)
            resolved = resolve_historical_position(
                name,
                profiles_by_name,
                market_rows_by_name,
                position_overrides,
            )
            group = resolved["positionGroup"]
            positions = resolved["positions"]
            source_player_id = resolved["sourcePlayerId"]
            nationality = resolved["nationality"]
            position_confidence = resolved["positionConfidence"]
            highest_market_value = resolved["highestMarketValue"]
            effective_group = "FWD" if goals / max(1, appearances) >= 0.25 else group
            if effective_group == "UNVERIFIED":
                effective_group = "MID"
            rating = min(
                91,
                editorial_rating(
                    position_group=effective_group,
                    appearances=appearances,
                    minutes=appearances * 75,
                    goals=goals,
                    assists=0,
                    clean_sheets=0,
                    goals_conceded=0,
                    highest_market_value=highest_market_value,
                )
                + 4,
            )
            players.append(
                {
                    "id": f"hns-{_slug(name)}-{start_year}",
                    "sourcePlayerId": str(source_player_id),
                    "name": name,
                    "nationality": nationality,
                    "positionGroup": group,
                    "positions": positions,
                    "seasonRating": rating,
                    "primeRating": rating,
                    "appearances": appearances,
                    "starts": None,
                    "minutes": None,
                    "goals": goals,
                    "assists": None,
                    "yellowCards": None,
                    "redCards": None,
                    "marketValuePeakEur": highest_market_value or None,
                    "ratingKind": "editorial-derived",
                    "statsSource": (
                        f"{HNS_RIZNICA_URL}?sezona={season.replace('/', '%2F')}"
                    ),
                    "confidence": round(0.65 * position_confidence, 2),
                    "draftEligible": resolved["draftEligible"],
                    "positionSource": resolved["positionSource"],
                    "positionDisclosure": resolved["positionDisclosure"],
                }
            )
        if not players:
            continue
        club_key = normalized_name(club_name)
        club_id = club_ids.get(club_key, f"hns-{_slug(club_name)}")
        records.append(
            {
                "id": f"hns-{club_id}-{start_year}",
                "clubId": club_id,
                "club": club_name,
                "season": season,
                "seasonStart": start_year,
                "accent": club_accent(club_name),
                "sourceBacked": True,
                "confidence": 0.62,
                "coverage": {
                    "playerRows": len(players),
                    "status": "official-champion-squad",
                    "note": (
                        "HNS Riznica supplies champion-squad membership, "
                        "appearances and goals. Cited position sources supply "
                        "exact or unit-level eligibility; unresolved players "
                        "remain visible as UNK and are not draft-selectable."
                    ),
                },
                "source": {
                    "name": "HNS Riznica",
                    "url": f"{HNS_RIZNICA_URL}?sezona={season.replace('/', '%2F')}",
                    "priority": "official",
                },
                "players": sorted(
                    players,
                    key=lambda player: (
                        -player["seasonRating"],
                        player["name"],
                    ),
                ),
            }
        )
    return records


def load_supplemental_club_seasons(
    path: Path | None,
    profiles: dict[str, dict[str, str]],
    market_rows_by_name: dict[str, dict[str, str]],
    position_overrides: dict[str, dict[str, Any]],
    *,
    id_prefix: str = "supplement",
) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    profiles_by_name = profiles_indexed_by_name(profiles)
    records: list[dict[str, Any]] = []
    for source_record in payload.get("clubSeasons", []):
        club = str(source_record.get("club", "")).strip()
        season = str(source_record.get("season", "")).strip()
        source = source_record.get("source")
        if not club or not season:
            raise ValueError(f"{path}: supplemental record needs club and season")
        if not isinstance(source, dict) or not source.get("url"):
            raise ValueError(f"{path}:{club} {season}: cited source is required")
        start_year = season_start_year(season)
        record_confidence = as_float(source_record.get("confidence")) or 0.72
        players: list[dict[str, Any]] = []
        for row in source_record.get("players", []):
            name = str(row.get("name", "")).strip()
            if not name:
                raise ValueError(f"{path}:{club} {season}: player name is required")
            row_group = str(row.get("positionGroup", "")).upper()
            row_positions = row.get("positions")
            if row_group or row_positions is not None:
                if not row_group or row_positions is None:
                    raise ValueError(
                        f"{path}:{club} {season}:{name}: source-table position "
                        "requires both positionGroup and positions"
                    )
                source_positions = validate_position_assignment(
                    row_group,
                    row_positions,
                    context=f"{path}:{club} {season}:{name}",
                )
                role_scope = (
                    "exact position"
                    if EXACT_POSITION_CODES.intersection(source_positions)
                    else "broad position"
                )
                resolved = {
                    "positionGroup": row_group,
                    "positions": source_positions,
                    "sourcePlayerId": str(
                        row.get("sourcePlayerId")
                        or row.get("playerId")
                        or f"source-{_slug(name)}"
                    ),
                    "nationality": row.get("nationality") or "Unknown",
                    "highestMarketValue": 0,
                    "positionConfidence": record_confidence,
                    "positionSource": {
                        "name": source["name"],
                        "url": source["url"],
                    },
                    "draftEligible": True,
                    "positionDisclosure": (
                        f"Source-backed {role_scope} is transcribed from the "
                        "cited club-season squad table; no additional role is "
                        "implied."
                    ),
                }
            else:
                resolved = resolve_historical_position(
                    name,
                    profiles_by_name,
                    market_rows_by_name,
                    position_overrides,
                )
            appearances = optional_int(
                row.get("appearances"),
                context=f"{path}:{club} {season}:{name}:appearances",
            )
            starts = optional_int(
                row.get("starts"),
                context=f"{path}:{club} {season}:{name}:starts",
            )
            substitute_appearances = optional_int(
                row.get("substituteAppearances"),
                context=(
                    f"{path}:{club} {season}:{name}:substituteAppearances"
                ),
            )
            if appearances is None and (
                starts is not None and substitute_appearances is not None
            ):
                appearances = starts + substitute_appearances
            if (
                appearances is not None
                and starts is not None
                and substitute_appearances is not None
                and appearances != starts + substitute_appearances
            ):
                raise ValueError(
                    f"{path}:{club} {season}:{name}: appearances must equal "
                    "starts plus substituteAppearances"
                )
            goals = optional_int(
                row.get("goals"),
                context=f"{path}:{club} {season}:{name}:goals",
            )
            season_market_value = optional_int(
                row.get("marketValueEur"),
                context=f"{path}:{club} {season}:{name}:marketValueEur",
            )
            date_of_birth = str(
                row.get("dateOfBirth") or row.get("birthDate") or ""
            ).strip() or None
            rating_appearances = appearances or 0
            rating_goals = goals or 0
            group = resolved["positionGroup"]
            rating_group = (
                "FWD"
                if appearances is not None
                and rating_goals / max(1, rating_appearances) >= 0.25
                else ("MID" if group == "UNVERIFIED" else group)
            )
            rating = min(
                91,
                editorial_rating(
                    position_group=rating_group,
                    appearances=rating_appearances,
                    minutes=rating_appearances * 75,
                    goals=rating_goals,
                    assists=0,
                    clean_sheets=0,
                    goals_conceded=0,
                    highest_market_value=(
                        season_market_value
                        if season_market_value is not None
                        else resolved["highestMarketValue"]
                    ),
                )
                + 4,
            )
            players.append(
                {
                    "id": (
                        f"{id_prefix}-{_slug(club)}-{_slug(name)}-{start_year}"
                    ),
                    "sourcePlayerId": resolved["sourcePlayerId"],
                    "name": name,
                    "nationality": resolved["nationality"],
                    "dateOfBirth": date_of_birth,
                    "positionGroup": group,
                    "positions": resolved["positions"],
                    "seasonRating": rating,
                    "primeRating": rating,
                    "appearances": appearances,
                    "starts": starts,
                    "substituteAppearances": substitute_appearances,
                    "minutes": None,
                    "goals": goals,
                    "assists": None,
                    "yellowCards": None,
                    "redCards": None,
                    "marketValuePeakEur": (
                        resolved["highestMarketValue"] or None
                    ),
                    "marketValueSeasonEur": season_market_value,
                    "ratingKind": (
                        "editorial-derived"
                        if appearances is not None and goals is not None
                        else "editorial-derived-partial-stats"
                    ),
                    "statsSource": source["url"],
                    "confidence": round(
                        record_confidence
                        * resolved["positionConfidence"]
                        * (
                            1.0
                            if appearances is not None and goals is not None
                            else 0.8
                        ),
                        2,
                    ),
                    "draftEligible": resolved["draftEligible"],
                    "positionSource": resolved["positionSource"],
                    "positionDisclosure": resolved["positionDisclosure"],
                    "statsDisclosure": (
                        "League appearances and goals are source-backed."
                        if appearances is not None and goals is not None
                        else (
                            "Null statistics are not reported by the cited "
                            "season page and were not inferred."
                        )
                    ),
                }
            )
        if not players:
            raise ValueError(f"{path}:{club} {season}: player list is empty")
        players.sort(
            key=lambda player: (
                -player["seasonRating"],
                player["positionGroup"],
                player["name"],
            )
        )
        club_id = str(
            source_record.get("clubId") or f"{id_prefix}-{_slug(club)}"
        )
        draft_eligible = sum(
            bool(player["draftEligible"]) for player in players
        )
        records.append(
            {
                "id": f"{id_prefix}-{club_id}-{start_year}",
                "clubId": club_id,
                "club": club,
                "season": season,
                "seasonStart": start_year,
                "accent": club_accent(club),
                "sourceBacked": True,
                "confidence": round(record_confidence, 2),
                "coverage": {
                    "playerRows": len(players),
                    "draftEligibleRows": draft_eligible,
                    "status": "source-supplement",
                    "note": source_record.get("note")
                    or (
                        "Named player-season rows are transcribed from the "
                        "cited season source. Positions are resolved separately "
                        "and unresolved players remain UNK/non-selectable."
                    ),
                },
                "source": source,
                "players": players,
            }
        )
    return records


def _has_exact_position(player: dict[str, Any]) -> bool:
    return bool(
        EXACT_POSITION_CODES.intersection(
            str(position).upper()
            for position in player.get("positions", [])
        )
    )


def merge_club_season_enrichment(
    base_record: dict[str, Any],
    enrichment_record: dict[str, Any],
) -> dict[str, Any]:
    """Union a full squad page with an existing partial performance record."""
    players = [dict(player) for player in base_record.get("players", [])]
    by_source_player_id = {
        str(player.get("sourcePlayerId")): index
        for index, player in enumerate(players)
        if player.get("sourcePlayerId")
    }
    by_name = {
        normalized_name(str(player.get("name") or "")): index
        for index, player in enumerate(players)
        if str(player.get("name") or "").strip()
    }
    existing_ids = {
        str(player.get("id")) for player in players if player.get("id")
    }
    matched_rows = 0
    appended_rows = 0
    position_repairs = 0

    for enrichment_player in enrichment_record.get("players", []):
        source_player_id = str(
            enrichment_player.get("sourcePlayerId") or ""
        ).strip()
        name_key = normalized_name(str(enrichment_player.get("name") or ""))
        player_index = (
            by_source_player_id.get(source_player_id)
            if source_player_id
            else None
        )
        if player_index is None and name_key:
            player_index = by_name.get(name_key)
        if player_index is not None:
            matched_rows += 1
            existing = players[player_index]
            if (
                _has_exact_position(enrichment_player)
                and not _has_exact_position(existing)
            ):
                for key in (
                    "positionGroup",
                    "positions",
                    "draftEligible",
                    "positionSource",
                    "positionDisclosure",
                ):
                    existing[key] = enrichment_player.get(key)
                existing["confidence"] = max(
                    as_float(existing.get("confidence")),
                    as_float(enrichment_player.get("confidence")),
                )
                position_repairs += 1
            if (
                existing.get("nationality") in (None, "", "Unknown")
                and enrichment_player.get("nationality")
                not in (None, "", "Unknown")
            ):
                existing["nationality"] = enrichment_player["nationality"]
            for factual_key in ("dateOfBirth", "marketValueSeasonEur"):
                if (
                    existing.get(factual_key) in (None, "")
                    and enrichment_player.get(factual_key) not in (None, "")
                ):
                    existing[factual_key] = enrichment_player[factual_key]
            continue

        appended = dict(enrichment_player)
        candidate_id = str(appended.get("id") or "")
        if not candidate_id or candidate_id in existing_ids:
            base_id = (
                f"enrichment-{_slug(str(base_record.get('club') or 'club'))}-"
                f"{_slug(str(appended.get('name') or 'player'))}-"
                f"{base_record.get('seasonStart')}"
            )
            candidate_id = base_id
            suffix = 2
            while candidate_id in existing_ids:
                candidate_id = f"{base_id}-{suffix}"
                suffix += 1
            appended["id"] = candidate_id
        players.append(appended)
        appended_index = len(players) - 1
        existing_ids.add(candidate_id)
        if source_player_id:
            by_source_player_id[source_player_id] = appended_index
        if name_key:
            by_name[name_key] = appended_index
        appended_rows += 1

    players.sort(
        key=lambda player: (
            -as_int(player.get("seasonRating")),
            str(player.get("positionGroup") or ""),
            str(player.get("name") or ""),
        )
    )
    base_coverage = dict(base_record.get("coverage") or {})
    enrichment_source = dict(enrichment_record.get("source") or {})
    base_source = base_record.get("source") or {
        "name": "Transfermarkt-derived football-datasets",
        "url": SOURCE_DATASET_URL,
        "priority": "secondary",
    }
    base_coverage.update(
        {
            "playerRows": len(players),
            "draftEligibleRows": sum(
                bool(player.get("draftEligible", True))
                for player in players
            ),
            "status": "source-enriched",
            "enrichment": {
                "source": enrichment_source,
                "sourcePlayerRows": len(
                    enrichment_record.get("players", [])
                ),
                "matchedRows": matched_rows,
                "appendedRows": appended_rows,
                "positionRepairs": position_repairs,
                "note": enrichment_record.get("coverage", {}).get("note"),
            },
        }
    )
    return {
        **base_record,
        "players": players,
        "confidence": round(
            max(
                as_float(base_record.get("confidence")),
                as_float(enrichment_record.get("confidence")),
            ),
            2,
        ),
        "coverage": base_coverage,
        "source": {
            "name": "Merged performance and full-squad sources",
            "url": enrichment_source.get("url") or SOURCE_DATASET_URL,
            "priority": enrichment_source.get("priority") or "secondary",
            "components": [base_source, enrichment_source],
        },
    }


def _club_season_matches(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    if left.get("season") != right.get("season"):
        return False
    left_club_id = str(left.get("clubId") or "").strip()
    right_club_id = str(right.get("clubId") or "").strip()
    if left_club_id and right_club_id and left_club_id == right_club_id:
        return True
    return normalized_name(str(left.get("club") or "")) == normalized_name(
        str(right.get("club") or "")
    )


def merge_club_season_enrichments(
    playable_candidates: list[dict[str, Any]],
    below_threshold_records: list[dict[str, Any]],
    enrichment_records: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[tuple[str, str]]]:
    """Merge enrichments, promoting partial fragments for later validation."""
    candidates = list(playable_candidates)
    partials = list(below_threshold_records)
    enriched_keys: set[tuple[str, str]] = set()
    for enrichment in enrichment_records:
        candidate_index = next(
            (
                index
                for index, candidate in enumerate(candidates)
                if _club_season_matches(candidate, enrichment)
            ),
            None,
        )
        if candidate_index is not None:
            candidates[candidate_index] = merge_club_season_enrichment(
                candidates[candidate_index],
                enrichment,
            )
        else:
            partial_index = next(
                (
                    index
                    for index, partial in enumerate(partials)
                    if _club_season_matches(partial, enrichment)
                ),
                None,
            )
            if partial_index is None:
                candidates.append(enrichment)
            else:
                candidates.append(
                    merge_club_season_enrichment(
                        partials.pop(partial_index),
                        enrichment,
                    )
                )
        enriched_keys.add(
            (
                normalized_name(str(enrichment["club"])),
                str(enrichment["season"]),
            )
        )
    return candidates, enriched_keys


def build_catalog(args: argparse.Namespace) -> dict[str, Any]:
    profiles = load_profiles(args.profiles)
    (
        market_values,
        market_rows_by_name,
        market_rows_by_player_id,
    ) = load_market_values(args.player_index)
    position_overrides_path = getattr(
        args,
        "position_overrides",
        DEFAULT_POSITION_OVERRIDES,
    )
    supplemental_path = getattr(
        args,
        "supplemental_club_seasons",
        DEFAULT_SUPPLEMENTAL_CLUB_SEASONS,
    )
    enrichment_path = getattr(
        args,
        "club_season_enrichments",
        DEFAULT_CLUB_SEASON_ENRICHMENTS,
    )
    position_overrides = load_position_overrides(position_overrides_path)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    skipped_without_profile = 0
    skipped_without_name = 0

    for row in iter_hnl_performances(args.performances):
        player_id = row["player_id"]
        profile = profiles.get(player_id)
        if not profile:
            skipped_without_profile += 1
            continue
        player_name = resolve_performance_player_name(
            profile,
            player_id,
            market_rows_by_player_id.get(player_id),
        )
        if not player_name:
            skipped_without_name += 1
            continue
        position_group, positions = role_for(
            profile.get("position", ""), profile.get("main_position", "")
        )
        appearances = as_int(row.get("nb_on_pitch"))
        starts = max(0, appearances - as_int(row.get("subed_in")))
        minutes = as_int(row.get("minutes_played"))
        goals = as_int(row.get("goals"))
        assists = as_int(row.get("assists"))
        yellow_cards = as_int(row.get("yellow_cards"))
        red_cards = as_int(row.get("direct_red_cards")) + as_int(
            row.get("second_yellow_cards")
        )
        clean_sheets = as_int(row.get("clean_sheets"))
        goals_conceded = as_int(row.get("goals_conceded"))
        highest_market_value = market_values.get(player_id, 0)
        rating = editorial_rating(
            position_group=position_group,
            appearances=appearances,
            minutes=minutes,
            goals=goals,
            assists=assists,
            clean_sheets=clean_sheets,
            goals_conceded=goals_conceded,
            highest_market_value=highest_market_value,
        )
        player = {
            "id": f"tm-{player_id}-{row['season_name'].replace('/', '-')}",
            "sourcePlayerId": player_id,
            "name": player_name,
            "nationality": profile.get("citizenship") or "Unknown",
            "positionGroup": position_group,
            "positions": positions,
            "seasonRating": rating,
            "primeRating": rating,
            "appearances": appearances,
            "starts": starts,
            "minutes": minutes,
            "goals": goals,
            "assists": assists,
            "yellowCards": yellow_cards,
            "redCards": red_cards,
            "marketValuePeakEur": highest_market_value or None,
            "ratingKind": "editorial-derived",
            "statsSource": SOURCE_DATASET_URL,
            "draftEligible": position_group != "UNVERIFIED",
            "positionSource": {
                "name": "Transfermarkt-derived player profile",
                "url": SOURCE_DATASET_URL,
            },
            "positionDisclosure": "Profile-backed position.",
        }
        key = (row["team_id"], row["team_name"], row["season_name"])
        grouped[key].append(player)

    player_primes: dict[str, int] = defaultdict(int)
    for players in grouped.values():
        for player in players:
            player_primes[player["sourcePlayerId"]] = max(
                player_primes[player["sourcePlayerId"]], player["seasonRating"]
            )

    club_seasons: list[dict[str, Any]] = []
    below_threshold_records: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    for (club_id, club_name, short_season), players in grouped.items():
        for player in players:
            player["primeRating"] = player_primes[player["sourcePlayerId"]]
        players.sort(
            key=lambda player: (
                -player["seasonRating"],
                player["positionGroup"],
                player["name"],
            )
        )
        season = long_season(short_season)
        record = {
            "id": f"tm-{club_id}-{season_start_year(short_season)}",
            "clubId": club_id,
            "club": club_name,
            "season": season,
            "seasonStart": season_start_year(short_season),
            "accent": club_accent(club_name),
            "sourceBacked": True,
            "confidence": 0.74 if len(players) >= 18 else 0.58,
            "coverage": {
                "playerRows": len(players),
                "status": "source-partial",
                "note": (
                    "Roster is the source dataset's recorded KR1 player-season "
                    "set; it may omit registered players with no captured row."
                ),
            },
            "players": players,
        }
        if len(players) >= args.minimum_squad_size:
            club_seasons.append(record)
        else:
            below_threshold_records.append(record)
            omitted.append(
                {
                    "club": club_name,
                    "season": season,
                    "playerRows": len(players),
                    "reason": "below-minimum-squad-size",
                }
            )

    hns_legacy_records = load_hns_champion_squads(
        args.hns_riznica_dir,
        profiles,
        market_rows_by_name,
        position_overrides,
    )
    club_seasons.extend(hns_legacy_records)
    supplemental_records = load_supplemental_club_seasons(
        supplemental_path,
        profiles,
        market_rows_by_name,
        position_overrides,
    )
    existing_keys = {
        (normalized_name(record["club"]), record["season"])
        for record in club_seasons
    }
    for record in supplemental_records:
        key = (normalized_name(record["club"]), record["season"])
        if key in existing_keys:
            raise ValueError(
                "Supplement duplicates an existing club-season: "
                f"{record['club']} {record['season']}"
            )
        existing_keys.add(key)
        club_seasons.append(record)
    supplemental_keys = {
        (normalized_name(record["club"]), record["season"])
        for record in supplemental_records
    }
    omitted = [
        row
        for row in omitted
        if (normalized_name(row["club"]), row["season"]) not in supplemental_keys
    ]
    enrichment_records = load_supplemental_club_seasons(
        enrichment_path,
        profiles,
        market_rows_by_name,
        position_overrides,
        id_prefix="enrichment",
    )
    club_seasons, enriched_keys = merge_club_season_enrichments(
        club_seasons,
        below_threshold_records,
        enrichment_records,
    )
    omitted = [
        row
        for row in omitted
        if (normalized_name(row["club"]), row["season"]) not in enriched_keys
    ]
    club_seasons.sort(key=lambda item: (item["seasonStart"], item["club"]))
    assert_catalog_position_integrity(club_seasons)
    candidate_club_seasons = len(club_seasons)
    club_seasons, incomplete_club_seasons = (
        partition_playable_club_seasons(club_seasons)
    )
    for record in incomplete_club_seasons:
        assessment = record["coverage"]["playability"]
        omitted.append(
            {
                "club": record["club"],
                "season": record["season"],
                "playerRows": len(record["players"]),
                "uniquePlayers": assessment["uniquePlayers"],
                "draftEligibleUniquePlayers": assessment[
                    "draftEligibleUniquePlayers"
                ],
                "reason": "playability-gate",
                "reasons": assessment["reasons"],
                "legalFormations": assessment["legalFormations"],
                "missingSupportedFormations": assessment[
                    "missingSupportedFormations"
                ],
                "recordId": record["id"],
            }
        )
    omitted.sort(key=lambda item: (item["season"], item["club"]))
    seasons = sorted({item["season"] for item in club_seasons})
    unresolved_position_players = sum(
        player["positionGroup"] == "UNVERIFIED"
        for record in club_seasons
        for player in record["players"]
    )
    return {
        "schemaVersion": "1.2.0",
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "competition": {
            "id": COMPETITION_ID,
            "name": "Hrvatska nogometna liga",
            "country": "Croatia",
        },
        "requestedRange": {
            "from": "1995/96",
            "to": "2025/26",
            "note": (
                "The game is architected for the full requested range. This "
                "generated playable pack only includes source-backed squads "
                "with at least eleven distinct eligible players that can be "
                "assigned to all eleven slots of every supported formation."
            ),
        },
        "playableRange": {
            "from": seasons[0] if seasons else None,
            "to": seasons[-1] if seasons else None,
            "seasons": seasons,
        },
        "coverage": {
            "clubSeasons": len(club_seasons),
            "candidateClubSeasons": candidate_club_seasons,
            "incompleteClubSeasons": len(incomplete_club_seasons),
            "players": sum(len(item["players"]) for item in club_seasons),
            "incompletePlayerRows": sum(
                len(item["players"]) for item in incomplete_club_seasons
            ),
            "omittedClubSeasons": len(omitted),
            "skippedRowsWithoutProfile": skipped_without_profile,
            "skippedRowsWithoutUsableName": skipped_without_name,
            "completeHistoricalRosterArchive": False,
            "confidence": 0.86 if enrichment_records else 0.68,
            "officialLegacyChampionSquads": len(hns_legacy_records),
            "supplementalClubSeasons": len(supplemental_records),
            "clubSeasonEnrichments": len(enrichment_records),
            "unresolvedPositionPlayers": unresolved_position_players,
            "positionOverrides": len(position_overrides),
            "playabilityGate": {
                "minimumUniquePlayers": 11,
                "minimumDraftEligibleUniquePlayers": 11,
                "requiresLegalXi": True,
                "requiresEverySupportedFormation": True,
                "formations": list(LEGAL_XI_FORMATIONS),
                "assignment": "maximum-bipartite-matching",
                "failedCandidates": len(incomplete_club_seasons),
            },
        },
        "sources": [
            {
                "name": "HNS COMET Semafor",
                "url": HNS_CURRENT_COMPETITION_URL,
                "use": "Official current competition, fixtures and eligibility check.",
                "priority": "official",
            },
            {
                "name": "HNS Riznica",
                "url": HNS_RIZNICA_URL,
                "use": (
                    "Official champion-squad membership, appearances and goals "
                    "for playable legacy seasons."
                ),
                "priority": "official",
            },
            {
                "name": "Transfermarkt-derived football-datasets",
                "url": SOURCE_DATASET_URL,
                "schema": SOURCE_SCHEMA_URL,
                "use": "Player-season team membership and performance fields.",
                "priority": "secondary",
                "licenseNote": (
                    "Repository license link was unavailable when generated; "
                    "verify reuse terms before public or commercial deployment."
                ),
            },
            {
                "name": "Transfermarkt KR1",
                "url": TRANSFERMARKT_COMPETITION_URL,
                "use": "Underlying descriptive competition and squad source.",
                "priority": "secondary",
            },
            {
                "name": "Transfermarkt historical squad pages",
                "url": TRANSFERMARKT_COMPETITION_URL,
                "use": (
                    "Season-specific full roster identity, detailed primary "
                    "position, nationality, birth date and market value. Every "
                    "enriched club-season retains its direct page URL."
                ),
                "priority": "secondary",
            },
            {
                "name": "FootballSquads Croatian archive",
                "url": "https://www.footballsquads.co.uk/croatia/",
                "use": (
                    "Season-specific roster and broad G/D/M/F fallback where "
                    "a detailed page is absent or its single primary roles do "
                    "not cover a selectable formation. Fallbacks never cross "
                    "goalkeeper, defence, midfield or forward units."
                ),
                "priority": "secondary-fallback",
            },
            {
                "name": "Croatian Wikipedia season supplements",
                "url": (
                    "https://hr.wikipedia.org/wiki/"
                    "Dodatak:HNK_Hajduk_Split_2001./02."
                ),
                "use": (
                    "Named supplemental player-season appearances and goals "
                    "where the main performance input has no club-season rows."
                ),
                "priority": "supplemental",
                "license": "CC BY-SA",
            },
        ],
        "ratingDisclosure": (
            "Season and prime ratings are original editorial game values derived "
            "from appearances, minutes, goals, assists, clean sheets and career "
            "peak market-value bands. They are not HNS or Transfermarkt ratings."
        ),
        "inputChecksums": {
            "performancesSha256": sha256(args.performances),
            "profilesSha256": sha256(args.profiles),
            "playerIndexSha256": (
                sha256(args.player_index)
                if args.player_index and args.player_index.exists()
                else None
            ),
            "positionOverridesSha256": (
                sha256(position_overrides_path)
                if position_overrides_path and position_overrides_path.exists()
                else None
            ),
            "supplementalClubSeasonsSha256": (
                sha256(supplemental_path)
                if supplemental_path and supplemental_path.exists()
                else None
            ),
            "clubSeasonEnrichmentsSha256": (
                sha256(enrichment_path)
                if enrichment_path and enrichment_path.exists()
                else None
            ),
        },
        "clubSeasons": club_seasons,
        "incompleteClubSeasons": incomplete_club_seasons,
        "omitted": omitted,
    }


def main() -> None:
    args = parse_args()
    payload = build_catalog(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {payload['coverage']['clubSeasons']} club-seasons and "
        f"{payload['coverage']['players']} player rows to {args.output}; "
        f"quarantined {payload['coverage']['incompleteClubSeasons']} "
        "incomplete candidates"
    )


if __name__ == "__main__":
    main()
