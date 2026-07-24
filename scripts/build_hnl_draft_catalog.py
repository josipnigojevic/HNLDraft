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


def season_start_year(label: str) -> int:
    first = int(label.split("/", 1)[0])
    return 1900 + first if first >= 90 else 2000 + first


def long_season(label: str) -> str:
    start = season_start_year(label)
    return f"{start}/{str(start + 1)[-2:]}"


def clean_player_name(name: str, player_id: str) -> str:
    return re.sub(rf"\s+\({re.escape(player_id)}\)$", "", name).strip()


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
    if "goalkeeper" in raw or main == "goalkeeper":
        return "GK", ["GK"]
    if "centre-back" in raw or "center-back" in raw:
        return "DEF", ["CB"]
    if "left-back" in raw:
        return "DEF", ["LB", "LWB"]
    if "right-back" in raw:
        return "DEF", ["RB", "RWB"]
    if "defender" in raw or main == "defender":
        return "DEF", ["CB"]
    if "defensive midfield" in raw:
        return "MID", ["DM", "CM"]
    if "attacking midfield" in raw:
        return "MID", ["AM", "CM"]
    if "left midfield" in raw:
        return "MID", ["LM", "LW", "CM"]
    if "right midfield" in raw:
        return "MID", ["RM", "RW", "CM"]
    if "central midfield" in raw or "midfield" in raw or main == "midfield":
        return "MID", ["CM", "DM", "AM"]
    if "left winger" in raw:
        return "FWD", ["LW", "RW", "ST"]
    if "right winger" in raw:
        return "FWD", ["RW", "LW", "ST"]
    if "second striker" in raw:
        return "FWD", ["ST", "AM"]
    if "centre-forward" in raw or "center-forward" in raw:
        return "FWD", ["ST"]
    if "attack" in raw or main == "attack":
        return "FWD", ["ST", "LW", "RW"]
    return "MID", ["CM"]


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
) -> tuple[dict[str, int], dict[str, dict[str, str]]]:
    if path is None or not path.exists():
        return {}, {}
    values: dict[str, int] = {}
    rows: dict[str, dict[str, str]] = {}
    with open_text(path) as handle:
        for row in csv.DictReader(handle):
            values[row["player_id"]] = as_int(row.get("highest_market_value_in_eur"))
            rows[normalized_name(row.get("name", ""))] = row
    return values, rows


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
) -> list[dict[str, Any]]:
    if directory is None or not directory.is_dir():
        return []
    profiles_by_name: dict[str, dict[str, str]] = {}
    for profile in profiles.values():
        player_id = profile["player_id"]
        name = clean_player_name(profile.get("player_name", ""), player_id)
        profiles_by_name.setdefault(normalized_name(name), profile)
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
            name_key = normalized_name(name)
            profile = profiles_by_name.get(name_key)
            market_row = market_rows_by_name.get(name_key)
            if profile:
                group, positions = role_for(
                    profile.get("position", ""), profile.get("main_position", "")
                )
                source_player_id = profile["player_id"]
                nationality = profile.get("citizenship") or "Unknown"
                position_confidence = 0.72
            elif market_row:
                group, positions = role_for(
                    market_row.get("sub_position", ""),
                    market_row.get("position", ""),
                )
                source_player_id = market_row["player_id"]
                nationality = market_row.get("country_of_citizenship") or "Unknown"
                position_confidence = 0.7
            else:
                # The official archive establishes membership and totals but
                # does not publish positions. Universal eligibility keeps the
                # archived champion squad playable without pretending a role
                # was verified.
                group = "UNVERIFIED"
                positions = [
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
                ]
                source_player_id = f"hns-{_slug(name)}"
                nationality = "Unknown"
                position_confidence = 0.2
            highest_market_value = (
                as_int(market_row.get("highest_market_value_in_eur"))
                if market_row
                else 0
            )
            effective_group = "FWD" if goals / max(1, appearances) >= 0.25 else group
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
                    "positionDisclosure": (
                        "Profile-backed position."
                        if position_confidence >= 0.7
                        else "Position unavailable in HNS archive; universal draft "
                        "eligibility is a clearly marked game fallback."
                    ),
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
                        "appearances and goals. Some player positions are "
                        "unverified and explicitly use universal eligibility."
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


def build_catalog(args: argparse.Namespace) -> dict[str, Any]:
    profiles = load_profiles(args.profiles)
    market_values, market_rows_by_name = load_market_values(args.player_index)
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    skipped_without_profile = 0

    for row in iter_hnl_performances(args.performances):
        player_id = row["player_id"]
        profile = profiles.get(player_id)
        if not profile:
            skipped_without_profile += 1
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
            "name": clean_player_name(profile.get("player_name", ""), player_id),
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
    )
    club_seasons.extend(hns_legacy_records)
    club_seasons.sort(key=lambda item: (item["seasonStart"], item["club"]))
    seasons = sorted({item["season"] for item in club_seasons})
    return {
        "schemaVersion": "1.0.0",
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
                "meeting the minimum player-row threshold."
            ),
        },
        "playableRange": {
            "from": seasons[0] if seasons else None,
            "to": seasons[-1] if seasons else None,
            "seasons": seasons,
        },
        "coverage": {
            "clubSeasons": len(club_seasons),
            "players": sum(len(item["players"]) for item in club_seasons),
            "omittedClubSeasons": len(omitted),
            "skippedRowsWithoutProfile": skipped_without_profile,
            "completeHistoricalRosterArchive": False,
            "confidence": 0.68,
            "officialLegacyChampionSquads": len(hns_legacy_records),
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
        },
        "clubSeasons": club_seasons,
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
        f"{payload['coverage']['players']} player rows to {args.output}"
    )


if __name__ == "__main__":
    main()
