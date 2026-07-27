#!/usr/bin/env python3
"""Fetch source-backed historical Transfermarkt squad supplements.

The checked-in performance archive is intentionally treated as immutable.  This
script finds catalog club-seasons whose current players cannot fill every game
formation, adds every catalog ``omitted`` candidate, and downloads the public
Transfermarkt historical squad page for each target.

Only HTTP GET requests are made.  HTML cache files default to the operating
system temporary directory and are never stored in the repository.

Examples:
    # Inspect the default target set without importing BeautifulSoup or using
    # the network.
    python3 scripts/fetch_transfermarkt_squad_supplements.py --dry-run

    # Fetch every incomplete/omitted target.
    python3 scripts/fetch_transfermarkt_squad_supplements.py

    # Fetch one club-season and merge it into an existing output.
    python3 scripts/fetch_transfermarkt_squad_supplements.py \
      --target 447:2004

    # Deliberately acquire every playable club-season, plus omitted candidates.
    python3 scripts/fetch_transfermarkt_squad_supplements.py --all

Parsing requires BeautifulSoup:
    python3 -m pip install beautifulsoup4
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from scripts.build_hnl_draft_catalog import LEGAL_XI_FORMATIONS
except ModuleNotFoundError:
    # Direct execution makes ``scripts/`` sys.path[0], while package imports
    # resolve through the repository root.
    from build_hnl_draft_catalog import LEGAL_XI_FORMATIONS


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = REPOSITORY_ROOT / "data" / "hnl_draft_catalog.json"
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT / "data" / "transfermarkt_squad_supplements.json"
)
DEFAULT_CACHE_DIR = (
    Path(tempfile.gettempdir()) / "hnl-transfermarkt-squad-cache"
)
SOURCE_NAME = "Transfermarkt historical squad page"
SOURCE_BASE_URL = "https://www.transfermarkt.com"
SCHEMA_VERSION = "1.0.0"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# The current catalog omits clubId from its ``omitted`` rows.  These IDs come
# from the same Transfermarkt-derived KR1 performance input used by the catalog
# generator.  Name normalization below also covers accents and punctuation.
KNOWN_CLUB_IDS = {
    "gnk dinamo zagreb": "419",
    "hnk cibalia vinkovci": "314",
    "hnk sibenik": "223",
    "nk croatia sesvete": "5111",
    "nk inter zapresic": "918",
    "nk kamen ingrad velika": "2776",
    "nk karlovac 1919": "10314",
    "nk medjimurje cakovec": "6087",
    "nk osijek": "327",
    "nk pula 1856": "999",
    "nk pula staro cesko": "999",
    "nk varazdin": "599",
    "nk varteks varazdin": "599",
    "nk zadar": "2566",
    "nk zagreb": "5107",
    "rnk split": "420",
    "slaven belupo koprivnica": "2362",
}

# FootballSquads starts its Croatian archive in 2005/06.  Its broad G/D/M/F
# roster tables are used only when a Transfermarkt page is absent or cannot
# cover every selectable formation.  Combining the two sources keeps the
# detailed Transfermarkt role while adding a cited same-unit fallback; it
# never makes a goalkeeper eligible outfield or crosses DEF/MID/FWD units.
FOOTBALLSQUADS_SLUGS = {
    "144": "rijeka",
    "223": "sibenik",
    "2362": "slaven",
    "2566": "zadar",
    "2776": "kamen",
    "314": "cibalia",
    "327": "osijek",
    "419": "dinamo",
    "420": "rnksplit",
    "447": "hajduk",
    "485": "dragovoljac",
    "599": "varteks",
    "6087": "medji",
    "918": "interzap",
    "999": "pulasc",
    "5107": "zagreb",
    "10314": "karlovac",
    "11194": "lokozagr",
    "12109": "lucko",
}

POSITION_ALIASES: dict[str, tuple[str, str]] = {
    "goalkeeper": ("GK", "GK"),
    "keeper": ("GK", "GK"),
    "torwart": ("GK", "GK"),
    "vratar": ("GK", "GK"),
    "defender": ("DEF", "DEF"),
    "defence": ("DEF", "DEF"),
    "abwehr": ("DEF", "DEF"),
    "centre back": ("CB", "DEF"),
    "center back": ("CB", "DEF"),
    "central defender": ("CB", "DEF"),
    "sweeper": ("CB", "DEF"),
    "innenverteidiger": ("CB", "DEF"),
    "right back": ("RB", "DEF"),
    "rechter verteidiger": ("RB", "DEF"),
    "left back": ("LB", "DEF"),
    "linker verteidiger": ("LB", "DEF"),
    "right wing back": ("RWB", "DEF"),
    "right wingback": ("RWB", "DEF"),
    "left wing back": ("LWB", "DEF"),
    "left wingback": ("LWB", "DEF"),
    "midfield": ("MID", "MID"),
    "midfielder": ("MID", "MID"),
    "mittelfeld": ("MID", "MID"),
    "defensive midfield": ("DM", "MID"),
    "defensive midfielder": ("DM", "MID"),
    "defensives mittelfeld": ("DM", "MID"),
    "central midfield": ("CM", "MID"),
    "central midfielder": ("CM", "MID"),
    "zentrales mittelfeld": ("CM", "MID"),
    "attacking midfield": ("AM", "MID"),
    "attacking midfielder": ("AM", "MID"),
    "offensives mittelfeld": ("AM", "MID"),
    "right midfield": ("RM", "MID"),
    "right midfielder": ("RM", "MID"),
    "rechtes mittelfeld": ("RM", "MID"),
    "left midfield": ("LM", "MID"),
    "left midfielder": ("LM", "MID"),
    "linkes mittelfeld": ("LM", "MID"),
    "attack": ("FWD", "FWD"),
    "attacker": ("FWD", "FWD"),
    "forward": ("FWD", "FWD"),
    "sturm": ("FWD", "FWD"),
    "right winger": ("RW", "FWD"),
    "right wing": ("RW", "FWD"),
    "rechtsaussen": ("RW", "FWD"),
    "left winger": ("LW", "FWD"),
    "left wing": ("LW", "FWD"),
    "linksaussen": ("LW", "FWD"),
    "centre forward": ("CF", "FWD"),
    "center forward": ("CF", "FWD"),
    "central forward": ("CF", "FWD"),
    "mittelsturmer": ("CF", "FWD"),
    "striker": ("ST", "FWD"),
    "second striker": ("SS", "FWD"),
    "hangende spitze": ("SS", "FWD"),
}

RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
DATE_FORMATS = (
    "%b %d, %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%d %B %Y",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%d-%m-%y",
    "%d-%m-%Y",
    "%Y-%m-%d",
)


@dataclass
class Target:
    club_id: str
    club: str
    season: str
    season_start: int
    record_id: str
    current_player_rows: int | None
    reasons: set[str] = field(default_factory=set)
    failed_formations: list[str] = field(default_factory=list)
    omitted: bool = False

    @property
    def key(self) -> tuple[str, int]:
        return self.club_id, self.season_start

    @property
    def source_url(self) -> str:
        return (
            f"{SOURCE_BASE_URL}/{url_slug(self.club)}/kader/verein/{self.club_id}"
            f"/saison_id/{self.season_start}/plus/1"
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "recordId": self.record_id,
            "clubId": self.club_id,
            "club": self.club,
            "season": self.season,
            "seasonStart": self.season_start,
            "currentPlayerRows": self.current_player_rows,
            "omitted": self.omitted,
            "failedFormations": self.failed_formations,
            "reasons": sorted(self.reasons),
            "sourceUrl": self.source_url,
        }


@dataclass(frozen=True)
class SourceTarget:
    club_id: str
    season_start: int
    source_url: str


class AcquisitionError(RuntimeError):
    """Raised for a network response that cannot safely be used."""


class ParseError(RuntimeError):
    """Raised when a squad page does not contain a recognizable roster."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=(
            "HTML cache outside the repository "
            f"(default: {DEFAULT_CACHE_DIR})."
        ),
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--all",
        action="store_true",
        help="Fetch every catalog club-season, plus omitted candidates.",
    )
    scope.add_argument(
        "--target",
        action="append",
        default=[],
        metavar="RECORD_OR_CLUB:YEAR",
        help=(
            "Fetch a specific record id (tm-447-2004) or clubId:startYear "
            "(447:2004). May be repeated."
        ),
    )
    parser.add_argument(
        "--club-id",
        action="append",
        default=[],
        metavar="NORMALIZED_NAME=ID",
        help=(
            "Override an omitted club's Transfermarkt id. May be repeated."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved target report; make no network/file writes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the sorted target list, useful for an acquisition smoke test.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=3.0,
        help="Minimum delay between network requests (default: 3.0).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Per-request timeout (default: 30).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retries after a retryable error (default: 3).",
    )
    parser.add_argument(
        "--cache-max-age-hours",
        type=float,
        default=24 * 30,
        help="Reuse cached HTML younger than this many hours (default: 720).",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore existing cache entries and refresh them with HTTP GET.",
    )
    parser.add_argument(
        "--replace-output",
        action="store_true",
        help=(
            "Replace output with this run only. By default, successful fetched "
            "groups are merged into any existing supplement file."
        ),
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="Transparent User-Agent sent with each request.",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.delay_seconds < 0:
        parser.error("--delay-seconds cannot be negative")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    if args.retries < 0:
        parser.error("--retries cannot be negative")
    if args.cache_max_age_hours < 0:
        parser.error("--cache-max-age-hours cannot be negative")
    return args


def normalized_text(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.casefold()).strip()


def url_slug(value: str) -> str:
    """Return the canonical ASCII-style slug used in Transfermarkt routes."""
    return normalized_text(value).replace(" ", "-") or "club"


def parse_season_start(label: str) -> int:
    match = re.search(r"(\d{2,4})", label)
    if not match:
        raise ValueError(f"Cannot parse season start from {label!r}")
    year = int(match.group(1))
    return year if year >= 1900 else 1900 + year


def season_label(start: int) -> str:
    return f"{start}/{str(start + 1)[-2:]}"


def parse_club_id_overrides(values: Sequence[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(
                f"Invalid --club-id {value!r}; expected NORMALIZED_NAME=ID"
            )
        name, club_id = value.rsplit("=", 1)
        key = normalized_text(name)
        club_id = club_id.strip()
        if not key or not club_id.isdigit():
            raise ValueError(
                f"Invalid --club-id {value!r}; ID must contain only digits"
            )
        result[key] = club_id
    return result


def compatible(
    player: Mapping[str, Any],
    slot: tuple[str, frozenset[str]],
) -> bool:
    unit, accepted = slot
    positions = {
        str(position).strip().upper()
        for position in player.get("positions", [])
        if isinstance(position, str)
    }
    return unit in positions or bool(positions.intersection(accepted))


def can_field_formation(
    players: Iterable[Mapping[str, Any]],
    slots: Sequence[tuple[str, frozenset[str]]],
) -> bool:
    eligible = [
        player
        for player in players
        if player.get("draftEligible", True)
        and player.get("positions") != ["UNK"]
    ]
    candidates = [
        [
            player_index
            for player_index, player in enumerate(eligible)
            if compatible(player, slot)
        ]
        for slot in slots
    ]
    player_to_slot: dict[int, int] = {}

    def augment(slot_index: int, visited: set[int]) -> bool:
        for player_index in candidates[slot_index]:
            if player_index in visited:
                continue
            visited.add(player_index)
            previous_slot = player_to_slot.get(player_index)
            if previous_slot is None or augment(previous_slot, visited):
                player_to_slot[player_index] = slot_index
                return True
        return False

    matched = 0
    for slot_index in sorted(
        range(len(slots)),
        key=lambda index: (len(candidates[index]), index),
    ):
        matched += int(augment(slot_index, set()))
    return matched == len(slots)


def failed_formations(record: Mapping[str, Any]) -> list[str]:
    players = record.get("players")
    if not isinstance(players, list):
        return sorted(LEGAL_XI_FORMATIONS)
    return [
        name
        for name, slots in LEGAL_XI_FORMATIONS.items()
        if not can_field_formation(players, slots)
    ]


def load_catalog(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Catalog root must be an object")
    if not isinstance(payload.get("clubSeasons"), list):
        raise ValueError("Catalog must contain a clubSeasons array")
    if not isinstance(payload.get("omitted", []), list):
        raise ValueError("Catalog omitted value must be an array")
    return payload


def resolve_targets(
    payload: Mapping[str, Any],
    *,
    include_all: bool,
    selectors: Sequence[str],
    club_id_overrides: Mapping[str, str],
) -> tuple[list[Target], list[dict[str, Any]]]:
    known_ids = dict(KNOWN_CLUB_IDS)
    known_ids.update(club_id_overrides)
    for record in payload["clubSeasons"]:
        club = str(record.get("club") or "")
        club_id = str(record.get("clubId") or "")
        if club and club_id:
            known_ids.setdefault(normalized_text(club), club_id)

    targets_by_key: dict[tuple[str, int], Target] = {}
    all_current: list[Target] = []
    for record in payload["clubSeasons"]:
        club_id = str(record.get("clubId") or "").strip()
        club = str(record.get("club") or "").strip()
        start = int(record.get("seasonStart"))
        failures = failed_formations(record)
        target = Target(
            club_id=club_id,
            club=club,
            season=str(record.get("season") or season_label(start)),
            season_start=start,
            record_id=str(record.get("id") or f"tm-{club_id}-{start}"),
            current_player_rows=len(record.get("players") or []),
            failed_formations=failures,
        )
        if failures:
            target.reasons.add("cannot-field-all-formations")
        all_current.append(target)
        if include_all or failures:
            targets_by_key[target.key] = target

    unresolved: list[dict[str, Any]] = []
    omitted_targets: list[Target] = []
    for omitted in payload.get("omitted", []):
        club = str(omitted.get("club") or "").strip()
        season = str(omitted.get("season") or "").strip()
        start = parse_season_start(season)
        club_id = known_ids.get(normalized_text(club))
        if not club_id:
            unresolved.append(
                {
                    "club": club,
                    "season": season,
                    "reason": "club-id-unresolved",
                }
            )
            continue
        target = Target(
            club_id=club_id,
            club=club,
            season=season or season_label(start),
            season_start=start,
            record_id=f"omitted-{club_id}-{start}",
            current_player_rows=int(omitted.get("playerRows") or 0),
            reasons={"catalog-omitted"},
            failed_formations=sorted(LEGAL_XI_FORMATIONS),
            omitted=True,
        )
        omitted_targets.append(target)
        existing = targets_by_key.get(target.key)
        if existing:
            existing.reasons.add("catalog-omitted")
            existing.omitted = True
        else:
            targets_by_key[target.key] = target

    if selectors:
        universe = {
            target.key: target for target in [*all_current, *omitted_targets]
        }
        selected: dict[tuple[str, int], Target] = {}
        unmatched: list[str] = []
        for selector in selectors:
            compact = selector.strip()
            club_year = re.fullmatch(r"(\d+)[:@](\d{4})", compact)
            matches: list[Target]
            if club_year:
                key = (club_year.group(1), int(club_year.group(2)))
                matches = [universe[key]] if key in universe else []
            else:
                matches = [
                    target
                    for target in universe.values()
                    if target.record_id == compact
                ]
            if not matches:
                unmatched.append(selector)
            for target in matches:
                selected[target.key] = target
        if unmatched:
            raise ValueError(
                "Unmatched --target value(s): " + ", ".join(unmatched)
            )
        targets_by_key = selected

    targets = sorted(
        targets_by_key.values(),
        key=lambda target: (
            target.season_start,
            normalized_text(target.club),
            target.club_id,
        ),
    )
    return targets, unresolved


def path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


class FetchClient:
    def __init__(
        self,
        cache_dir: Path,
        *,
        delay_seconds: float,
        timeout_seconds: float,
        retries: int,
        max_cache_age_hours: float,
        refresh: bool,
        user_agent: str,
    ) -> None:
        if path_is_within(cache_dir, REPOSITORY_ROOT):
            raise ValueError(
                "--cache-dir must be outside the repository; use an OS temp "
                "directory or another external data directory"
            )
        self.cache_dir = cache_dir
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.max_cache_age_seconds = max_cache_age_hours * 3600
        self.refresh = refresh
        self.user_agent = user_agent
        self.last_network_request_at: float | None = None
        self.network_requests = 0
        self.cache_hits = 0

    def _cache_path(self, target: Target) -> Path:
        digest = hashlib.sha256(target.source_url.encode("utf-8")).hexdigest()[:12]
        return self.cache_dir / (
            f"transfermarkt-squad-{target.club_id}-{target.season_start}"
            f"-{digest}.html"
        )

    def _read_cache(self, path: Path) -> str | None:
        if self.refresh or not path.is_file():
            return None
        age = max(0.0, time.time() - path.stat().st_mtime)
        if age > self.max_cache_age_seconds:
            return None
        self.cache_hits += 1
        return path.read_text(encoding="utf-8")

    def _polite_wait(self) -> None:
        if self.last_network_request_at is None:
            return
        elapsed = time.monotonic() - self.last_network_request_at
        remaining = self.delay_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    @staticmethod
    def _retry_after_seconds(error: urllib.error.HTTPError) -> float | None:
        value = error.headers.get("Retry-After")
        if not value:
            return None
        if value.isdigit():
            return float(value)
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=UTC)
            return max(
                0.0,
                (retry_at - datetime.now(UTC)).total_seconds(),
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _decode(response: Any, body: bytes) -> str:
        if response.headers.get("Content-Encoding", "").casefold() == "gzip":
            body = gzip.decompress(body)
        charset = response.headers.get_content_charset() or "utf-8"
        return body.decode(charset, errors="replace")

    def _fetch_with_curl(self, target: Target) -> str:
        """Use curl's browser-compatible TLS transport when it is available."""
        curl = shutil.which("curl")
        if curl is None:
            raise FileNotFoundError("curl is not installed")
        result = subprocess.run(
            [
                curl,
                "--location",
                "--silent",
                "--show-error",
                "--compressed",
                "--max-time",
                str(self.timeout_seconds),
                "--user-agent",
                self.user_agent,
                "--header",
                "Accept: text/html,application/xhtml+xml",
                "--header",
                "Accept-Language: en-US,en;q=0.8",
                "--write-out",
                "\n%{http_code}",
                target.source_url,
            ],
            check=False,
            capture_output=True,
            timeout=self.timeout_seconds + 5,
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise AcquisitionError(
                f"curl exited {result.returncode}: {detail or 'unknown error'}"
            )
        try:
            body, status_raw = result.stdout.rsplit(b"\n", 1)
            status = int(status_raw)
        except (ValueError, TypeError) as error:
            raise AcquisitionError(
                "curl response did not include a valid HTTP status"
            ) from error
        if status != 200:
            raise AcquisitionError(
                f"Unexpected HTTP {status} for {target.source_url}"
            )
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError:
            # Older FootballSquads pages predate consistent UTF-8 headers and
            # use Western-European bytes alongside numeric HTML entities.
            return body.decode("windows-1252", errors="replace")

    def fetch(self, target: Target) -> tuple[str, bool]:
        cache_path = self._cache_path(target)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached, True

        last_error: BaseException | None = None
        for attempt in range(self.retries + 1):
            if attempt:
                backoff = min(60.0, (2**attempt) + random.random())
                time.sleep(backoff)
            self._polite_wait()
            request = urllib.request.Request(
                target.source_url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.8",
                    "Accept-Encoding": "gzip",
                    "Connection": "close",
                },
                method="GET",
            )
            self.last_network_request_at = time.monotonic()
            self.network_requests += 1
            try:
                if shutil.which("curl"):
                    text = self._fetch_with_curl(target)
                else:
                    with urllib.request.urlopen(
                        request,
                        timeout=self.timeout_seconds,
                    ) as response:
                        status = int(response.status)
                        if status != 200:
                            raise AcquisitionError(
                                f"Unexpected HTTP {status} for "
                                f"{target.source_url}"
                            )
                        text = self._decode(response, response.read())
                if len(text) < 2_000:
                    raise AcquisitionError(
                        f"Response is too short to be a squad page "
                        f"({len(text)} bytes): {target.source_url}"
                    )
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(text, encoding="utf-8")
                return text, False
            except urllib.error.HTTPError as error:
                last_error = error
                if error.code not in RETRYABLE_HTTP_STATUS:
                    raise AcquisitionError(
                        f"HTTP {error.code} for {target.source_url}"
                    ) from error
                retry_after = self._retry_after_seconds(error)
                if retry_after:
                    time.sleep(min(120.0, retry_after))
            except (
                urllib.error.URLError,
                TimeoutError,
                subprocess.TimeoutExpired,
                AcquisitionError,
            ) as error:
                last_error = error

        raise AcquisitionError(
            f"Failed after {self.retries + 1} attempt(s): "
            f"{target.source_url}: {last_error}"
        ) from last_error


def require_beautiful_soup() -> Any:
    try:
        from bs4 import BeautifulSoup
    except ImportError as error:
        raise RuntimeError(
            "BeautifulSoup is required for HTML parsing. Install it with "
            "`python3 -m pip install beautifulsoup4`, then rerun the command. "
            "`--dry-run` does not require it."
        ) from error
    return BeautifulSoup


def map_position(source_role: str) -> tuple[list[str], str]:
    mapped = POSITION_ALIASES.get(normalized_text(source_role))
    if mapped is None:
        return ["UNK"], "UNVERIFIED"
    position, group = mapped
    return [position], group


def parse_date_of_birth(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = re.sub(r"\s*\(\d+\)\s*$", "", raw).strip()
    for format_string in DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, format_string).date().isoformat()
        except ValueError:
            continue
    return None


def parse_market_value_eur(raw: str | None) -> int | None:
    if not raw or raw.strip() in {"-", "—", "N/A"}:
        return None
    normalized = (
        raw.casefold()
        .replace("\xa0", " ")
        .replace("€", "")
        .replace("eur", "")
        .strip()
    )
    match = re.search(
        r"([0-9]+(?:[.,][0-9]+)?)\s*(bn|b|m|mil|million|k|th|thousand)?",
        normalized,
    )
    if not match:
        return None
    numeric = match.group(1)
    if "," in numeric and "." not in numeric:
        numeric = numeric.replace(",", ".")
    try:
        value = float(numeric)
    except ValueError:
        return None
    suffix = match.group(2) or ""
    multiplier = {
        "bn": 1_000_000_000,
        "b": 1_000_000_000,
        "m": 1_000_000,
        "mil": 1_000_000,
        "million": 1_000_000,
        "k": 1_000,
        "th": 1_000,
        "thousand": 1_000,
        "": 1,
    }[suffix]
    return round(value * multiplier)


def source_role_from_row(row: Any, profile_link: Any) -> str:
    inline_table = profile_link.find_parent("table")
    if inline_table is not None:
        for nested_row in inline_table.find_all("tr"):
            text = nested_row.get_text(" ", strip=True)
            if normalized_text(text) in POSITION_ALIASES:
                return text
    for text in row.stripped_strings:
        candidate = str(text).strip()
        if normalized_text(candidate) in POSITION_ALIASES:
            return candidate
    return ""


def date_raw_from_cells(cells: Sequence[Any]) -> str | None:
    patterns = (
        r"\b[A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4}(?:\s+\(\d+\))?\b",
        r"\b\d{1,2}[./]\d{1,2}[./]\d{4}(?:\s+\(\d+\))?\b",
        r"\b\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4}(?:\s+\(\d+\))?\b",
        r"\b\d{4}-\d{2}-\d{2}(?:\s+\(\d+\))?\b",
    )
    for cell in cells:
        text = cell.get_text(" ", strip=True)
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
    return None


def market_value_raw_from_row(row: Any, cells: Sequence[Any]) -> str | None:
    likely_cells = [
        cell
        for cell in cells
        if {"rechts", "hauptlink"}.issubset(set(cell.get("class") or []))
    ]
    for cell in [*reversed(likely_cells), *reversed(cells)]:
        text = cell.get_text(" ", strip=True)
        if "€" in text or re.fullmatch(
            r"[0-9]+(?:[.,][0-9]+)?\s*(?:bn|b|m|mil|k|th)",
            text.casefold(),
        ):
            return text
    link = row.select_one('a[href*="/marktwertverlauf/spieler/"]')
    return link.get_text(" ", strip=True) if link else None


def parse_squad(html_text: str, target: Target) -> dict[str, Any]:
    BeautifulSoup = require_beautiful_soup()
    soup = BeautifulSoup(html_text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    normalized_title = normalized_text(title)
    if "just a moment" in normalized_title or "access denied" in normalized_title:
        raise ParseError(
            f"Received an anti-bot/interstitial page for {target.source_url}"
        )

    tables = soup.select("table.items")
    if not tables:
        raise ParseError(
            f"No Transfermarkt squad table found: {target.source_url}"
        )
    table = max(
        tables,
        key=lambda candidate: len(
            candidate.select('a[href*="/profil/spieler/"]')
        ),
    )
    tbody = table.find("tbody", recursive=False) or table.find("tbody")
    if tbody is None:
        raise ParseError(f"Squad table has no tbody: {target.source_url}")

    players_by_id: dict[str, dict[str, Any]] = {}
    for row in tbody.find_all("tr", recursive=False):
        links = row.select('a[href*="/profil/spieler/"]')
        profile_link = next(
            (
                link
                for link in links
                if re.search(r"/spieler/\d+", str(link.get("href") or ""))
            ),
            None,
        )
        if profile_link is None:
            continue
        href = str(profile_link.get("href") or "")
        player_id_match = re.search(r"/spieler/(\d+)", href)
        if not player_id_match:
            continue
        player_id = player_id_match.group(1)
        name = (
            profile_link.get_text(" ", strip=True)
            or str(profile_link.get("title") or "").strip()
        )
        if not name:
            image = row.select_one('img[alt]:not([alt=""])')
            name = str(image.get("alt") or "").strip() if image else ""
        if not name:
            continue

        source_role = source_role_from_row(row, profile_link)
        positions, position_group = map_position(source_role)
        cells = row.find_all("td", recursive=False)
        nationality_images = row.select(
            "img.flaggenrahmen[title], img.flaggenrahmen[alt]"
        )
        nationalities: list[str] = []
        for image in nationality_images:
            value = str(image.get("title") or image.get("alt") or "").strip()
            if value and value not in nationalities:
                nationalities.append(value)
        dob_raw = date_raw_from_cells(cells)
        market_value_raw = market_value_raw_from_row(row, cells)
        player = {
            "sourcePlayerId": player_id,
            "name": name,
            "sourceRole": source_role or None,
            "positionGroup": position_group,
            "positions": positions,
            "draftEligible": position_group != "UNVERIFIED",
            "nationality": nationalities[0] if nationalities else None,
            "nationalities": nationalities,
            "dateOfBirth": parse_date_of_birth(dob_raw),
            "dateOfBirthRaw": dob_raw,
            "marketValueRaw": market_value_raw,
            "marketValueEur": parse_market_value_eur(market_value_raw),
            "profileUrl": (
                href if href.startswith("http") else f"{SOURCE_BASE_URL}{href}"
            ),
            "confidence": 0.92 if position_group != "UNVERIFIED" else 0.62,
        }
        previous = players_by_id.get(player_id)
        if previous is None:
            players_by_id[player_id] = player
        else:
            # Duplicate markup occasionally exposes the same player twice.  A
            # row with a recognized role and DOB carries more useful evidence.
            previous_score = int(previous["draftEligible"]) + int(
                previous["dateOfBirth"] is not None
            )
            new_score = int(player["draftEligible"]) + int(
                player["dateOfBirth"] is not None
            )
            if new_score > previous_score:
                players_by_id[player_id] = player

    players = sorted(
        players_by_id.values(),
        key=lambda player: (
            player["positionGroup"],
            normalized_text(player["name"]),
            int(player["sourcePlayerId"]),
        ),
    )
    if not players:
        raise ParseError(
            f"Squad table contains no recognizable player rows: "
            f"{target.source_url}"
        )
    verified_roles = sum(player["draftEligible"] for player in players)
    with_nationality = sum(bool(player["nationalities"]) for player in players)
    with_dob = sum(bool(player["dateOfBirth"]) for player in players)
    with_market_value = sum(
        player["marketValueEur"] is not None for player in players
    )
    completeness = verified_roles / len(players)
    confidence = (
        0.94
        if len(players) >= 18 and completeness >= 0.95
        else 0.88
        if len(players) >= 11 and completeness >= 0.85
        else 0.78
    )
    return {
        "id": f"tm-squad-{target.club_id}-{target.season_start}",
        "clubId": target.club_id,
        "club": target.club,
        "season": target.season,
        "seasonStart": target.season_start,
        "confidence": confidence,
        "coverage": {
            "playerRows": len(players),
            "positionVerifiedRows": verified_roles,
            "nationalityRows": with_nationality,
            "dateOfBirthRows": with_dob,
            "marketValueRows": with_market_value,
            "status": "historical-squad-page",
            "targetReasons": sorted(target.reasons),
            "previousCatalogPlayerRows": target.current_player_rows,
            "previousFailedFormations": target.failed_formations,
        },
        "source": {
            "name": SOURCE_NAME,
            "url": target.source_url,
            "priority": "secondary",
            "retrievedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        },
        "players": players,
    }


def footballsquads_url(target: Target) -> str | None:
    slug = FOOTBALLSQUADS_SLUGS.get(target.club_id)
    if target.season_start < 2005 or not slug:
        return None
    return (
        "https://www.footballsquads.co.uk/croatia/"
        f"{target.season_start}-{target.season_start + 1}/1hnl/{slug}.htm"
    )


def parse_footballsquads(
    html_text: str,
    target: Target,
    source_url: str,
) -> dict[str, Any]:
    BeautifulSoup = require_beautiful_soup()
    soup = BeautifulSoup(html_text, "html.parser")
    players_by_name: dict[str, dict[str, Any]] = {}
    broad_roles = {
        "G": ("GK", "GK"),
        "GK": ("GK", "GK"),
        "D": ("DEF", "DEF"),
        "DF": ("DEF", "DEF"),
        "M": ("MID", "MID"),
        "MF": ("MID", "MID"),
        "F": ("FWD", "FWD"),
        "FW": ("FWD", "FWD"),
    }
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [
            cell.get_text(" ", strip=True).casefold()
            for cell in rows[0].find_all(["th", "td"])
        ]
        if "name" not in headers or "pos" not in headers:
            continue
        name_index = headers.index("name")
        position_index = headers.index("pos")
        dob_index = (
            headers.index("date of birth")
            if "date of birth" in headers
            else None
        )
        nationality_index = (
            headers.index("nat") if "nat" in headers else None
        )
        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            required_index = max(name_index, position_index)
            if len(cells) <= required_index:
                continue
            name = cells[name_index].get_text(" ", strip=True)
            raw_role = cells[position_index].get_text(" ", strip=True).upper()
            mapped = broad_roles.get(raw_role)
            name_key = normalized_text(name)
            if not name_key or mapped is None:
                continue
            position, group = mapped
            dob_raw = (
                cells[dob_index].get_text(" ", strip=True)
                if dob_index is not None and len(cells) > dob_index
                else None
            )
            nationality = (
                cells[nationality_index].get_text(" ", strip=True)
                if nationality_index is not None
                and len(cells) > nationality_index
                else None
            )
            players_by_name.setdefault(
                name_key,
                {
                    "sourcePlayerId": (
                        f"footballsquads-{target.club_id}-{name_key.replace(' ', '-')}"
                    ),
                    "name": name,
                    "sourceRole": raw_role,
                    "positionGroup": group,
                    "positions": [position],
                    "draftEligible": True,
                    "nationality": nationality or None,
                    "dateOfBirth": parse_date_of_birth(dob_raw),
                    "dateOfBirthRaw": dob_raw,
                    "confidence": 0.86,
                },
            )
    players = sorted(
        players_by_name.values(),
        key=lambda player: (
            player["positionGroup"],
            normalized_text(player["name"]),
        ),
    )
    if not players:
        raise ParseError(f"No FootballSquads roster table found: {source_url}")
    return {
        "id": f"footballsquads-{target.club_id}-{target.season_start}",
        "clubId": target.club_id,
        "club": target.club,
        "season": target.season,
        "seasonStart": target.season_start,
        "confidence": 0.86,
        "coverage": {
            "playerRows": len(players),
            "positionVerifiedRows": len(players),
            "status": "historical-squad-page",
            "targetReasons": sorted(target.reasons),
            "previousCatalogPlayerRows": target.current_player_rows,
            "previousFailedFormations": target.failed_formations,
        },
        "source": {
            "name": "FootballSquads historical roster",
            "url": source_url,
            "priority": "secondary",
            "retrievedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        },
        "players": players,
    }


def covers_every_formation(group: Mapping[str, Any]) -> bool:
    players = group.get("players")
    return isinstance(players, list) and all(
        can_field_formation(players, slots)
        for slots in LEGAL_XI_FORMATIONS.values()
    )


def combine_squad_groups(
    detailed: Mapping[str, Any] | None,
    broad: Mapping[str, Any],
) -> dict[str, Any]:
    """Preserve exact roles and add only a cited fallback in the same unit."""
    if detailed is None:
        return dict(broad)
    combined = [dict(player) for player in detailed.get("players", [])]
    by_name = {
        normalized_text(str(player.get("name") or "")): player
        for player in combined
    }
    same_unit_fallbacks = 0
    appended_rows = 0
    for broad_player in broad.get("players", []):
        key = normalized_text(str(broad_player.get("name") or ""))
        existing = by_name.get(key)
        if existing is None:
            appended = dict(broad_player)
            combined.append(appended)
            by_name[key] = appended
            appended_rows += 1
            continue
        broad_group = str(broad_player.get("positionGroup") or "")
        if broad_group != str(existing.get("positionGroup") or ""):
            continue
        positions = list(existing.get("positions") or [])
        broad_position = str((broad_player.get("positions") or [""])[0])
        if broad_position and broad_position not in positions:
            positions.append(broad_position)
            existing["positions"] = positions
            existing["broadRoleSource"] = broad.get("source")
            same_unit_fallbacks += 1
        if not existing.get("dateOfBirth") and broad_player.get("dateOfBirth"):
            existing["dateOfBirth"] = broad_player["dateOfBirth"]

    source = {
        "name": "Transfermarkt + FootballSquads historical squad sources",
        "url": str(broad.get("source", {}).get("url") or ""),
        "priority": "secondary",
        "components": [detailed.get("source"), broad.get("source")],
        "retrievedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }
    coverage = dict(detailed.get("coverage") or {})
    coverage.update(
        {
            "playerRows": len(combined),
            "status": "historical-squad-page-combined",
            "sameUnitFallbackRows": same_unit_fallbacks,
            "appendedFallbackRows": appended_rows,
        }
    )
    return {
        **detailed,
        "confidence": max(
            float(detailed.get("confidence") or 0),
            float(broad.get("confidence") or 0),
        ),
        "coverage": coverage,
        "source": source,
        "players": combined,
    }


def load_existing_groups(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    groups = payload.get("clubSeasons", []) if isinstance(payload, dict) else []
    if not isinstance(groups, list):
        raise ValueError(
            f"Existing output {path} has a non-array clubSeasons value"
        )
    return [group for group in groups if isinstance(group, dict)]


def merge_groups(
    previous: Iterable[Mapping[str, Any]],
    fetched: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[tuple[str, int], dict[str, Any]] = {}
    for group in [*previous, *fetched]:
        key = (str(group.get("clubId")), int(group.get("seasonStart")))
        merged[key] = dict(group)
    return sorted(
        merged.values(),
        key=lambda group: (
            int(group["seasonStart"]),
            normalized_text(str(group.get("club") or "")),
            str(group["clubId"]),
        ),
    )


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary_path = Path(handle.name)
    temporary_path.replace(path)


def main() -> int:
    args = parse_args()
    try:
        club_id_overrides = parse_club_id_overrides(args.club_id)
        catalog = load_catalog(args.catalog)
        targets, unresolved = resolve_targets(
            catalog,
            include_all=args.all,
            selectors=args.target,
            club_id_overrides=club_id_overrides,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Target resolution failed: {error}", file=sys.stderr)
        return 2

    if args.limit is not None:
        targets = targets[: args.limit]

    dry_run_payload = {
        "catalog": str(args.catalog),
        "mode": (
            "all"
            if args.all
            else "explicit-targets"
            if args.target
            else "formation-failures-plus-omitted"
        ),
        "targetCount": len(targets),
        "unresolvedOmittedCount": len(unresolved),
        "unresolvedOmitted": unresolved,
        "targets": [target.public_dict() for target in targets],
    }
    if args.dry_run:
        print(json.dumps(dry_run_payload, ensure_ascii=False, indent=2))
        return 1 if unresolved else 0
    if unresolved:
        print(
            "Cannot fetch every omitted candidate because one or more club IDs "
            "are unresolved. Supply --club-id NAME=ID and inspect --dry-run.",
            file=sys.stderr,
        )
        print(json.dumps(unresolved, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    if not targets:
        print("No targets matched; no output written.", file=sys.stderr)
        return 2

    try:
        client = FetchClient(
            args.cache_dir,
            delay_seconds=args.delay_seconds,
            timeout_seconds=args.timeout_seconds,
            retries=args.retries,
            max_cache_age_hours=args.cache_max_age_hours,
            refresh=args.refresh,
            user_agent=args.user_agent,
        )
        require_beautiful_soup()
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2

    fetched_groups: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, target in enumerate(targets, start=1):
        print(
            f"[{index}/{len(targets)}] {target.club} {target.season}",
            file=sys.stderr,
        )
        detailed_group: dict[str, Any] | None = None
        primary_error: BaseException | None = None
        try:
            html_text, from_cache = client.fetch(target)
            detailed_group = parse_squad(html_text, target)
            detailed_group["source"]["cacheHit"] = from_cache
        except (AcquisitionError, ParseError, OSError, ValueError) as error:
            primary_error = error

        group = detailed_group
        needs_fallback = (
            detailed_group is None
            or not covers_every_formation(detailed_group)
        )
        fallback_url = footballsquads_url(target) if needs_fallback else None
        fallback_error: BaseException | None = None
        if fallback_url:
            fallback_target = SourceTarget(
                club_id=target.club_id,
                season_start=target.season_start,
                source_url=fallback_url,
            )
            try:
                fallback_html, fallback_cache = client.fetch(fallback_target)
                broad_group = parse_footballsquads(
                    fallback_html,
                    target,
                    fallback_url,
                )
                broad_group["source"]["cacheHit"] = fallback_cache
                group = combine_squad_groups(detailed_group, broad_group)
                print(
                    "  used FootballSquads same-unit fallback",
                    file=sys.stderr,
                )
            except (AcquisitionError, ParseError, OSError, ValueError) as error:
                fallback_error = error

        if group is None:
            combined_error = str(primary_error or "primary source unavailable")
            if fallback_error is not None:
                combined_error += f"; fallback failed: {fallback_error}"
            failures.append(
                {
                    "recordId": target.record_id,
                    "clubId": target.club_id,
                    "club": target.club,
                    "season": target.season,
                    "sourceUrl": target.source_url,
                    "fallbackUrl": fallback_url,
                    "error": combined_error,
                }
            )
            print(f"  failed: {combined_error}", file=sys.stderr)
            continue

        fetched_groups.append(group)
        source_cache_hit = bool(group.get("source", {}).get("cacheHit"))
        print(
            f"  parsed {len(group['players'])} players "
            f"({'cache' if source_cache_hit else 'network/source merge'})",
            file=sys.stderr,
        )

    if not fetched_groups:
        print(
            "No squad pages were successfully parsed; existing output was not "
            "changed.",
            file=sys.stderr,
        )
        return 1

    previous_groups = (
        [] if args.replace_output else load_existing_groups(args.output)
    )
    groups = merge_groups(previous_groups, fetched_groups)
    source_group_counts: dict[str, int] = {}
    for group in groups:
        source_name = str(
            group.get("source", {}).get("name") or "Unknown source"
        )
        source_group_counts[source_name] = (
            source_group_counts.get(source_name, 0) + 1
        )
    output_payload = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "method": {
            "name": "historical-squad-acquisition",
            "description": (
                "Public Transfermarkt detailed squad HTML, with FootballSquads "
                "broad-unit fallback where necessary, parsed into source-backed "
                "player identity and position fields. No missing player, "
                "cross-unit position, performance statistic, or rating is "
                "inferred."
            ),
            "networkMethod": "GET",
            "politeDelaySeconds": args.delay_seconds,
            "checkedInSnapshot": True,
            "liveRuntimeDependency": False,
            "groupCount": len(groups),
            "sourceGroupCounts": source_group_counts,
            "sources": [
                SOURCE_BASE_URL,
                "https://www.footballsquads.co.uk/croatia/",
            ],
            "latestRun": {
                "targetMode": dry_run_payload["mode"],
                "targetCount": len(targets),
                "successfulTargets": len(fetched_groups),
                "failedTargets": failures,
                "cacheHits": client.cache_hits,
                "networkRequests": client.network_requests,
            },
        },
        "clubSeasons": groups,
    }
    try:
        write_json_atomic(args.output, output_payload)
    except OSError as error:
        print(f"Could not write {args.output}: {error}", file=sys.stderr)
        return 2
    print(
        f"Wrote {len(groups)} club-season supplement group(s) to {args.output}",
        file=sys.stderr,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
