#!/usr/bin/env python3
"""Server-authoritative room and live-draft API for the HNL draft game.

The implementation deliberately uses only Python's standard library and
SQLite, so it can run locally or in the existing Docker stack without a
dependency install.

Default HTTP contract (JSON request/response bodies):

    POST /rooms
      {"mode":"live","name":"Josip","seed":380,
       "settings":{"formation":"4-3-3","seasonStart":1995,
                   "seasonEnd":2026,"difficulty":"normal"}}

    POST /rooms/{code}/join
      {"name":"Ana"}

    GET /rooms/{code}?token={participantToken}

    POST /rooms/{code}/start
      {"participantToken":"...","expectedVersion":2}

    POST /rooms/{code}/spin
      {"participantToken":"...","expectedVersion":3,"expectedTurn":0}

    POST /rooms/{code}/pick
      {"participantToken":"...","expectedVersion":4,"expectedTurn":0,
       "playerSeasonId":"...","slotId":"gk"}

The participant token can instead be sent as ``Authorization: Bearer ...`` or
``X-Participant-Token``. Every state-changing draft action validates both the
room version and that manager's turn. Random club-season spins are derived
from the room seed, seat number, draft turn, and spin number, making them
reproducible without trusting the browser.

If ``data/hnl_draft_catalog.json`` exists, it is loaded at startup. Set
``HNL_CATALOG_PATH`` to override that location. The loader accepts either a
top-level array or an object containing ``clubSeasons``/``club_seasons``. The
small embedded catalog is explicitly demonstration-only and is never
represented as a complete historical HNL database.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping
from urllib.parse import parse_qs, urlsplit


API_VERSION = "2.0.0"
CATALOG_SCHEMA_VERSION = "1.0"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_MAX_BODY_BYTES = 1_000_000
DEFAULT_ROOM_TTL_SECONDS = 6 * 60 * 60
MAX_ROOM_TTL_SECONDS = 24 * 60 * 60
ROOM_CODE_LENGTH = 6
ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOM_MODES = {"solo", "live"}
ROOM_STATUSES = {"lobby", "drafting", "complete", "expired"}
DIFFICULTY_REROLLS = {"easy": 3, "normal": 1, "hard": 0}
RATINGS_MODES = {"season", "prime"}
DRAFT_MODES = {"squad-first", "position-first"}
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


class RequestError(ValueError):
    """Expected API error with a stable HTTP status and machine-readable code."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = code
        self.message = message
        self.details = dict(details or {})


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _as_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if not _is_int(value):
        raise RequestError(400, "invalid_setting", f"'{name}' must be an integer.")
    if not minimum <= value <= maximum:
        raise RequestError(
            400,
            "invalid_setting",
            f"'{name}' must be between {minimum} and {maximum}.",
        )
    return value


def _clean_name(value: Any) -> str:
    if not isinstance(value, str):
        raise RequestError(400, "invalid_name", "Manager name must be a string.")
    name = " ".join(value.strip().split())
    if not name or len(name) > 40 or CONTROL_CHARACTERS.search(name):
        raise RequestError(
            400,
            "invalid_name",
            "Manager name must contain 1–40 printable characters.",
        )
    return name


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    return json.loads(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc_timestamp(now: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-") or "item"


def _first(mapping: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return default


def _position(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Player position must be a non-empty string.")
    compact = value.strip().upper().replace("-", "").replace(" ", "")
    aliases = {
        "GOALKEEPER": "GK",
        "KEEPER": "GK",
        "RIGHTBACK": "RB",
        "LEFTBACK": "LB",
        "CENTREBACK": "CB",
        "CENTERBACK": "CB",
        "RIGHTWINGBACK": "RWB",
        "LEFTWINGBACK": "LWB",
        "DEFENSIVEMIDFIELD": "DM",
        "CENTRALMIDFIELD": "CM",
        "ATTACKINGMIDFIELD": "AM",
        "RIGHTMIDFIELD": "RM",
        "LEFTMIDFIELD": "LM",
        "RIGHTWING": "RW",
        "LEFTWING": "LW",
        "CENTREFORWARD": "ST",
        "CENTERFORWARD": "ST",
        "FORWARD": "FWD",
        "DEFENDER": "DEF",
        "MIDFIELDER": "MID",
    }
    return aliases.get(compact, compact)


@dataclass(frozen=True)
class Slot:
    id: str
    label: str
    category: str
    accepted: frozenset[str]


def _slot(
    slot_id: str,
    label: str,
    category: str,
    *accepted: str,
) -> Slot:
    return Slot(slot_id, label, category, frozenset(accepted))


# Slot IDs are stable API values. Labels are presentation hints only.
FORMATIONS: dict[str, tuple[Slot, ...]] = {
    "4-3-3": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rb", "RB", "DEF", "RB", "RWB", "CB"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("lb", "LB", "DEF", "LB", "LWB", "CB"),
        _slot("dm", "DM", "MID", "DM", "CM"),
        _slot("rcm", "RCM", "MID", "CM", "DM", "AM"),
        _slot("lcm", "LCM", "MID", "CM", "DM", "AM"),
        _slot("rw", "RW", "FWD", "RW", "RM", "LW", "AM"),
        _slot("st", "ST", "FWD", "ST", "CF"),
        _slot("lw", "LW", "FWD", "LW", "LM", "RW", "AM"),
    ),
    "4-4-2": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rb", "RB", "DEF", "RB", "RWB", "CB"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("lb", "LB", "DEF", "LB", "LWB", "CB"),
        _slot("rm", "RM", "MID", "RM", "RW", "CM"),
        _slot("rcm", "RCM", "MID", "CM", "DM", "AM"),
        _slot("lcm", "LCM", "MID", "CM", "DM", "AM"),
        _slot("lm", "LM", "MID", "LM", "LW", "CM"),
        _slot("rst", "RST", "FWD", "ST", "CF", "RW"),
        _slot("lst", "LST", "FWD", "ST", "CF", "LW"),
    ),
    "4-2-3-1": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rb", "RB", "DEF", "RB", "RWB", "CB"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("lb", "LB", "DEF", "LB", "LWB", "CB"),
        _slot("rdm", "RDM", "MID", "DM", "CM"),
        _slot("ldm", "LDM", "MID", "DM", "CM"),
        _slot("rw", "RW", "FWD", "RW", "RM", "LW", "AM"),
        _slot("am", "AM", "MID", "AM", "CM", "SS"),
        _slot("lw", "LW", "FWD", "LW", "LM", "RW", "AM"),
        _slot("st", "ST", "FWD", "ST", "CF"),
    ),
    "4-5-1": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rb", "RB", "DEF", "RB", "RWB", "CB"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("lb", "LB", "DEF", "LB", "LWB", "CB"),
        _slot("rm", "RM", "MID", "RM", "RW", "CM"),
        _slot("rdm", "RDM", "MID", "DM", "CM"),
        _slot("cm", "CM", "MID", "CM", "DM", "AM"),
        _slot("ldm", "LDM", "MID", "DM", "CM"),
        _slot("lm", "LM", "MID", "LM", "LW", "CM"),
        _slot("st", "ST", "FWD", "ST", "CF"),
    ),
    "3-4-3": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("cb", "CB", "DEF", "CB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("rm", "RM", "MID", "RM", "RW", "RWB", "CM"),
        _slot("rcm", "RCM", "MID", "CM", "DM", "AM"),
        _slot("lcm", "LCM", "MID", "CM", "DM", "AM"),
        _slot("lm", "LM", "MID", "LM", "LW", "LWB", "CM"),
        _slot("rw", "RW", "FWD", "RW", "RM", "AM"),
        _slot("st", "ST", "FWD", "ST", "CF"),
        _slot("lw", "LW", "FWD", "LW", "LM", "AM"),
    ),
    "3-5-2": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("cb", "CB", "DEF", "CB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("rwb", "RWB", "DEF", "RWB", "RB", "RW"),
        _slot("dm", "DM", "MID", "DM", "CM"),
        _slot("rcm", "RCM", "MID", "CM", "DM", "AM"),
        _slot("lcm", "LCM", "MID", "CM", "DM", "AM"),
        _slot("lwb", "LWB", "DEF", "LWB", "LB", "LW"),
        _slot("rst", "RST", "FWD", "ST", "CF", "RW"),
        _slot("lst", "LST", "FWD", "ST", "CF", "LW"),
    ),
    "5-4-1": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rwb", "RWB", "DEF", "RWB", "RB", "RW"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("cb", "CB", "DEF", "CB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("lwb", "LWB", "DEF", "LWB", "LB", "LW"),
        _slot("rm", "RM", "MID", "RM", "RW", "CM"),
        _slot("rcm", "RCM", "MID", "CM", "DM", "AM"),
        _slot("lcm", "LCM", "MID", "CM", "DM", "AM"),
        _slot("lm", "LM", "MID", "LM", "LW", "CM"),
        _slot("st", "ST", "FWD", "ST", "CF"),
    ),
    "4-1-2-1-2": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rb", "RB", "DEF", "RB", "RWB", "CB"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("lb", "LB", "DEF", "LB", "LWB", "CB"),
        _slot("dm", "DM", "MID", "DM", "CM"),
        _slot("rcm", "RCM", "MID", "CM", "DM", "AM"),
        _slot("lcm", "LCM", "MID", "CM", "DM", "AM"),
        _slot("am", "AM", "MID", "AM", "CM", "SS"),
        _slot("rst", "RST", "FWD", "ST", "CF", "RW"),
        _slot("lst", "LST", "FWD", "ST", "CF", "LW"),
    ),
    "4-4-1-1": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rb", "RB", "DEF", "RB", "RWB", "CB"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("lb", "LB", "DEF", "LB", "LWB", "CB"),
        _slot("rm", "RM", "MID", "RM", "RW", "CM"),
        _slot("rcm", "RCM", "MID", "CM", "DM", "AM"),
        _slot("lcm", "LCM", "MID", "CM", "DM", "AM"),
        _slot("lm", "LM", "MID", "LM", "LW", "CM"),
        _slot("ss", "SS", "FWD", "SS", "AM", "ST", "CF"),
        _slot("st", "ST", "FWD", "ST", "CF"),
    ),
    "5-3-2": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rwb", "RWB", "DEF", "RWB", "RB", "RW"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("cb", "CB", "DEF", "CB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("lwb", "LWB", "DEF", "LWB", "LB", "LW"),
        _slot("rcm", "RCM", "MID", "CM", "DM", "AM"),
        _slot("cm", "CM", "MID", "CM", "DM", "AM"),
        _slot("lcm", "LCM", "MID", "CM", "DM", "AM"),
        _slot("rst", "RST", "FWD", "ST", "CF", "RW"),
        _slot("lst", "LST", "FWD", "ST", "CF", "LW"),
    ),
    "3-4-1-2": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("cb", "CB", "DEF", "CB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("rm", "RM", "MID", "RM", "RW", "RWB", "CM"),
        _slot("rcm", "RCM", "MID", "CM", "DM", "AM"),
        _slot("lcm", "LCM", "MID", "CM", "DM", "AM"),
        _slot("lm", "LM", "MID", "LM", "LW", "LWB", "CM"),
        _slot("am", "AM", "MID", "AM", "CM", "SS"),
        _slot("rst", "RST", "FWD", "ST", "CF", "RW"),
        _slot("lst", "LST", "FWD", "ST", "CF", "LW"),
    ),
    "4-2-2-2": (
        _slot("gk", "GK", "GK", "GK"),
        _slot("rb", "RB", "DEF", "RB", "RWB", "CB"),
        _slot("rcb", "RCB", "DEF", "CB", "RB"),
        _slot("lcb", "LCB", "DEF", "CB", "LB"),
        _slot("lb", "LB", "DEF", "LB", "LWB", "CB"),
        _slot("rdm", "RDM", "MID", "DM", "CM"),
        _slot("ldm", "LDM", "MID", "DM", "CM"),
        _slot("ram", "RAM", "MID", "AM", "CM", "RW"),
        _slot("lam", "LAM", "MID", "AM", "CM", "LW"),
        _slot("rst", "RST", "FWD", "ST", "CF", "RW"),
        _slot("lst", "LST", "FWD", "ST", "CF", "LW"),
    ),
}


# Stable editorial opponents for the post-draft 10-team, 36-match game season.
# These strengths are transparent simulation inputs, not official HNS ratings
# and not a claim about a particular real-world season's participants.
HNL_SIMULATION_OPPONENTS: tuple[dict[str, Any], ...] = (
    {
        "id": "gnk-dinamo",
        "name": "GNK Dinamo",
        "shortName": "Dinamo",
        "rating": 83.0,
        "accent": "#0057b8",
    },
    {
        "id": "hnk-hajduk",
        "name": "HNK Hajduk",
        "shortName": "Hajduk",
        "rating": 80.5,
        "accent": "#ef3340",
    },
    {
        "id": "hnk-rijeka",
        "name": "HNK Rijeka",
        "shortName": "Rijeka",
        "rating": 79.5,
        "accent": "#75c8f0",
    },
    {
        "id": "nk-osijek",
        "name": "NK Osijek",
        "shortName": "Osijek",
        "rating": 76.5,
        "accent": "#174ea6",
    },
    {
        "id": "nk-varazdin",
        "name": "NK Varaždin",
        "shortName": "Varaždin",
        "rating": 74.5,
        "accent": "#1d4d92",
    },
    {
        "id": "nk-istra-1961",
        "name": "NK Istra 1961",
        "shortName": "Istra",
        "rating": 74.0,
        "accent": "#e5c529",
    },
    {
        "id": "nk-lokomotiva",
        "name": "NK Lokomotiva",
        "shortName": "Lokomotiva",
        "rating": 73.5,
        "accent": "#315d9b",
    },
    {
        "id": "hnk-gorica",
        "name": "HNK Gorica",
        "shortName": "Gorica",
        "rating": 73.0,
        "accent": "#d7192d",
    },
    {
        "id": "nk-slaven-belupo",
        "name": "NK Slaven Belupo",
        "shortName": "Slaven",
        "rating": 72.5,
        "accent": "#d51f2b",
    },
)


def _compatible(player: Mapping[str, Any], slot: Slot) -> bool:
    positions = frozenset(player["positions"])
    return bool(slot.accepted.intersection(positions)) or slot.category in positions


def _embedded_catalog() -> dict[str, Any]:
    """Return a small, transparent fallback catalog for local smoke testing."""

    def player(
        player_id: str,
        name: str,
        positions: Iterable[str],
        rating: int,
        nationality: str = "Croatia",
        prime_rating: int | None = None,
    ) -> dict[str, Any]:
        return {
            "id": player_id,
            "personId": _slug(name),
            "name": name,
            "positions": list(positions),
            "nationality": nationality,
            "seasonRating": rating,
            "primeRating": prime_rating if prime_rating is not None else rating,
            "ratingKind": "editorial-demo",
        }

    def record(
        record_id: str,
        club_id: str,
        club_name: str,
        season: str,
        start_year: int,
        accent: str,
        players: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "id": record_id,
            "club": {
                "id": club_id,
                "name": club_name,
                "shortName": club_name.replace("GNK ", "").replace("HNK ", ""),
                "accent": accent,
            },
            "season": {
                "id": season.replace("/", "-"),
                "label": season,
                "startYear": start_year,
                "endYear": start_year + 1,
            },
            "players": players,
            "source": {
                "kind": "editorial-demo",
                "confidence": 0.35,
                "note": "Fallback smoke-test data; verify membership before production use.",
            },
        }

    blue = "#0057B8"
    red = "#E32636"
    sky = "#6CBFEF"
    return {
        "schemaVersion": CATALOG_SCHEMA_VERSION,
        "metadata": {
            "name": "Embedded HNL draft fallback",
            "completeness": "demonstration-only",
            "sourceTier": "editorial-demo",
            "confidence": 0.35,
            "limitations": [
                "Not a complete historical squad database.",
                "Ratings are editorial demo values, not official HNS ratings.",
                "Use data/hnl_draft_catalog.json for the production catalog.",
            ],
        },
        "clubSeasons": [
            record(
                "croatia-zagreb-1997-98",
                "croatia-zagreb",
                "Croatia Zagreb",
                "1997/98",
                1997,
                blue,
                [
                    player("ladic-croatia-zagreb-1997-98", "Dražen Ladić", ["GK"], 88),
                    player("simic-croatia-zagreb-1997-98", "Dario Šimić", ["CB", "RB"], 87),
                ],
            ),
            record(
                "hajduk-2001-02",
                "hnk-hajduk",
                "HNK Hajduk",
                "2001/02",
                2001,
                red,
                [player("pletikosa-hajduk-2001-02", "Stipe Pletikosa", ["GK"], 86)],
            ),
            record(
                "hajduk-2002-03",
                "hnk-hajduk",
                "HNK Hajduk",
                "2002/03",
                2002,
                red,
                [player("srna-hajduk-2002-03", "Darijo Srna", ["RB", "RWB", "CM"], 88)],
            ),
            record(
                "osijek-2003-04",
                "nk-osijek",
                "NK Osijek",
                "2003/04",
                2003,
                "#174EA6",
                [player("pranjic-osijek-2003-04", "Danijel Pranjić", ["LB", "LWB", "CM", "LW"], 84)],
            ),
            record(
                "hajduk-2004-05",
                "hnk-hajduk",
                "HNK Hajduk",
                "2004/05",
                2004,
                red,
                [player("kranjcar-hajduk-2004-05", "Niko Kranjčar", ["AM", "CM", "LW"], 87)],
            ),
            record(
                "dinamo-2006-07",
                "gnk-dinamo",
                "GNK Dinamo",
                "2006/07",
                2006,
                blue,
                [
                    player("corluka-dinamo-2006-07", "Vedran Ćorluka", ["RB", "CB"], 86),
                    player("eduardo-dinamo-2006-07", "Eduardo da Silva", ["ST", "LW"], 90),
                ],
            ),
            record(
                "dinamo-2007-08",
                "gnk-dinamo",
                "GNK Dinamo",
                "2007/08",
                2007,
                blue,
                [
                    player("modric-dinamo-2007-08", "Luka Modrić", ["CM", "AM", "DM"], 91),
                    player("drpic-dinamo-2007-08", "Dino Drpić", ["CB"], 81),
                ],
            ),
            record(
                "dinamo-2008-09",
                "gnk-dinamo",
                "GNK Dinamo",
                "2008/09",
                2008,
                blue,
                [player("mandzukic-dinamo-2008-09", "Mario Mandžukić", ["ST"], 88)],
            ),
            record(
                "dinamo-2010-11",
                "gnk-dinamo",
                "GNK Dinamo",
                "2010/11",
                2010,
                blue,
                [player("sammir-dinamo-2010-11", "Sammir", ["AM", "CM", "LW"], 88, "Brazil")],
            ),
            record(
                "dinamo-2011-12",
                "gnk-dinamo",
                "GNK Dinamo",
                "2011/12",
                2011,
                blue,
                [
                    player("badelj-dinamo-2011-12", "Milan Badelj", ["CM", "DM", "AM"], 85),
                    player("vrsaljko-dinamo-2011-12", "Šime Vrsaljko", ["RB", "RWB", "LB"], 84),
                ],
            ),
            record(
                "dinamo-2012-13",
                "gnk-dinamo",
                "GNK Dinamo",
                "2012/13",
                2012,
                blue,
                [player("simunic-dinamo-2012-13", "Josip Šimunić", ["CB"], 87)],
            ),
            record(
                "rijeka-2013-14",
                "hnk-rijeka",
                "HNK Rijeka",
                "2013/14",
                2013,
                sky,
                [player("kramaric-rijeka-2013-14", "Andrej Kramarić", ["ST", "LW", "RW"], 88)],
            ),
            record(
                "dinamo-2013-14",
                "gnk-dinamo",
                "GNK Dinamo",
                "2013/14",
                2013,
                blue,
                [player("brozovic-dinamo-2013-14", "Marcelo Brozović", ["DM", "CM"], 87)],
            ),
            record(
                "dinamo-2015-16",
                "gnk-dinamo",
                "GNK Dinamo",
                "2015/16",
                2015,
                blue,
                [player("pjaca-dinamo-2015-16", "Marko Pjaca", ["RW", "LW", "ST"], 85)],
            ),
            record(
                "rijeka-2015-16",
                "hnk-rijeka",
                "HNK Rijeka",
                "2015/16",
                2015,
                sky,
                [player("vargic-rijeka-2015-16", "Ivan Vargić", ["GK"], 83)],
            ),
            record(
                "hajduk-2016-17",
                "hnk-hajduk",
                "HNK Hajduk",
                "2016/17",
                2016,
                red,
                [player("vlasic-hajduk-2016-17", "Nikola Vlašić", ["AM", "CM", "RW"], 85)],
            ),
            record(
                "dinamo-2016-17",
                "gnk-dinamo",
                "GNK Dinamo",
                "2016/17",
                2016,
                blue,
                [player("soudani-dinamo-2016-17", "El Arbi Hillel Soudani", ["RW", "ST", "LW"], 86, "Algeria")],
            ),
            record(
                "dinamo-2017-18",
                "gnk-dinamo",
                "GNK Dinamo",
                "2017/18",
                2017,
                blue,
                [player("sosa-dinamo-2017-18", "Borna Sosa", ["LB", "LWB"], 82)],
            ),
            record(
                "dinamo-2018-19",
                "gnk-dinamo",
                "GNK Dinamo",
                "2018/19",
                2018,
                blue,
                [player("olmo-dinamo-2018-19", "Dani Olmo", ["AM", "CM", "RW", "LW"], 89, "Spain")],
            ),
            record(
                "dinamo-2019-20",
                "gnk-dinamo",
                "GNK Dinamo",
                "2019/20",
                2019,
                blue,
                [player("ademi-dinamo-2019-20", "Arijan Ademi", ["DM", "CM"], 85, "North Macedonia")],
            ),
            record(
                "dinamo-2020-21",
                "gnk-dinamo",
                "GNK Dinamo",
                "2020/21",
                2020,
                blue,
                [
                    player("livakovic-dinamo-2020-21", "Dominik Livaković", ["GK"], 87),
                    player("gvardiol-dinamo-2020-21", "Joško Gvardiol", ["CB", "LB"], 88),
                    player("majer-dinamo-2020-21", "Lovro Majer", ["AM", "CM", "RW"], 86),
                    player("orsic-dinamo-2020-21", "Mislav Oršić", ["LW", "RW", "ST"], 87),
                ],
            ),
            record(
                "hajduk-2021-22",
                "hnk-hajduk",
                "HNK Hajduk",
                "2021/22",
                2021,
                red,
                [player("livaja-hajduk-2021-22", "Marko Livaja", ["ST", "AM"], 89)],
            ),
            record(
                "rijeka-2023-24",
                "hnk-rijeka",
                "HNK Rijeka",
                "2023/24",
                2023,
                sky,
                [
                    player("labrovic-rijeka-2023-24", "Nediljko Labrović", ["GK"], 82),
                    player("fruk-rijeka-2023-24", "Toni Fruk", ["AM", "CM", "RW"], 82),
                ],
            ),
        ],
    }


class Catalog:
    """Validated, immutable in-memory club-season/player-season catalog."""

    def __init__(
        self,
        club_seasons: Iterable[Mapping[str, Any]],
        metadata: Mapping[str, Any] | None = None,
        source_path: str | None = None,
    ) -> None:
        records: list[dict[str, Any]] = []
        record_ids: set[str] = set()
        player_ids: set[str] = set()
        for raw in club_seasons:
            record = self._normalize_record(raw)
            if record["id"] in record_ids:
                raise ValueError(f"Duplicate club-season id: {record['id']}")
            record_ids.add(record["id"])
            for player in record["players"]:
                if player["id"] in player_ids:
                    # A mid-season transfer can produce the same source
                    # player-season identifier under two club-seasons. Scope
                    # only the colliding API id while retaining its source id.
                    source_id = player["id"]
                    player["sourcePlayerSeasonId"] = source_id
                    player["id"] = f"{source_id}@{record['id']}"
                    suffix = 2
                    while player["id"] in player_ids:
                        player["id"] = f"{source_id}@{record['id']}:{suffix}"
                        suffix += 1
                player_ids.add(player["id"])
            records.append(record)
        if not records:
            raise ValueError("Draft catalog must contain at least one club-season.")
        self.records = tuple(sorted(records, key=lambda item: item["id"]))
        self.by_id = {item["id"]: item for item in self.records}
        self.player_count = sum(len(item["players"]) for item in self.records)
        years = [item["season"]["startYear"] for item in self.records]
        base_metadata = dict(metadata or {})
        base_metadata.setdefault("completeness", "unspecified")
        base_metadata.setdefault("confidence", None)
        base_metadata.update(
            {
                "schemaVersion": CATALOG_SCHEMA_VERSION,
                "sourcePath": source_path,
                "clubSeasonCount": len(self.records),
                "playerSeasonCount": self.player_count,
                "loaderSkippedPlayerRows": sum(
                    item.get("loaderSkippedPlayerRows", 0)
                    for item in self.records
                ),
                "normalizedCoverage": {
                    "earliestStartYear": min(years),
                    "latestStartYear": max(years),
                },
            }
        )
        self.metadata = base_metadata

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> "Catalog":
        candidate = Path(path) if path else Path("data/hnl_draft_catalog.json")
        if candidate.is_file():
            with candidate.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, list):
                return cls(payload, {"completeness": "unspecified"}, str(candidate))
            if not isinstance(payload, dict):
                raise ValueError("Catalog root must be an object or array.")
            records = _first(
                payload,
                "clubSeasons",
                "club_seasons",
                "catalog",
                "records",
            )
            if not isinstance(records, list):
                raise ValueError(
                    "Catalog object requires a clubSeasons/club_seasons array."
                )
            metadata = payload.get("metadata")
            if not isinstance(metadata, dict):
                # Preserve every top-level provenance/coverage field. This
                # makes GET /catalog honest about exactly what the generator
                # did and did not include.
                metadata = {
                    key: value
                    for key, value in payload.items()
                    if key
                    not in {
                        "clubSeasons",
                        "club_seasons",
                        "catalog",
                        "records",
                    }
                }
            coverage = metadata.get("coverage")
            if isinstance(coverage, dict):
                metadata.setdefault("confidence", coverage.get("confidence"))
                metadata.setdefault(
                    "completeness",
                    "complete"
                    if coverage.get("completeHistoricalRosterArchive") is True
                    else "source-partial",
                )
            return cls(records, metadata, str(candidate))
        embedded = _embedded_catalog()
        return cls(
            embedded["clubSeasons"],
            embedded["metadata"],
            source_path="embedded://api_rooms",
        )

    @staticmethod
    def _normalize_record(raw: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            raise ValueError("Each catalog club-season must be an object.")
        club_value = raw.get("club")
        club = dict(club_value) if isinstance(club_value, Mapping) else {}
        club_name = _first(
            club,
            "name",
            "clubName",
            default=(
                club_value.strip()
                if isinstance(club_value, str) and club_value.strip()
                else _first(raw, "clubName", "club_name", "team")
            ),
        )
        if not isinstance(club_name, str) or not club_name.strip():
            raise ValueError("Catalog club-season is missing a club name.")
        club_name = club_name.strip()
        club_id = _first(
            club,
            "id",
            "clubId",
            default=_first(raw, "clubId", "club_id"),
        )
        club_id = str(club_id or _slug(club_name))
        season_value = raw.get("season")
        season = dict(season_value) if isinstance(season_value, Mapping) else {}
        if isinstance(season_value, str):
            season["label"] = season_value
        season_label = _first(
            season,
            "label",
            "name",
            default=_first(raw, "seasonLabel", "season_label"),
        )
        start_year = _first(
            season,
            "startYear",
            "start_year",
            default=_first(raw, "startYear", "start_year", "seasonStart"),
        )
        if start_year is None and isinstance(season_label, str):
            match = re.search(r"(19|20)\d{2}", season_label)
            if match:
                start_year = int(match.group(0))
        if not _is_int(start_year) or not 1990 <= start_year <= 2100:
            raise ValueError(f"Invalid start year for {club_name!r}.")
        end_year = _first(
            season,
            "endYear",
            "end_year",
            default=_first(raw, "endYear", "end_year", default=start_year + 1),
        )
        if not _is_int(end_year):
            end_year = start_year + 1
        season_label = (
            season_label
            if isinstance(season_label, str) and season_label.strip()
            else f"{start_year}/{str(end_year)[-2:]}"
        )
        record_id = _first(raw, "id", "clubSeasonId", "club_season_id")
        record_id = str(record_id or f"{club_id}-{start_year}-{str(end_year)[-2:]}")
        raw_players = _first(raw, "players", "squad", "playerSeasons", "player_seasons")
        if not isinstance(raw_players, list) or not raw_players:
            raise ValueError(f"Club-season {record_id!r} requires a non-empty squad.")
        players = []
        skipped_player_rows = 0
        for item in raw_players:
            if (
                not isinstance(item, Mapping)
                or not isinstance(
                    _first(item, "name", "playerName", "player_name"), str
                )
                or not str(
                    _first(item, "name", "playerName", "player_name")
                ).strip()
            ):
                # Some secondary-source rows identify a profile id but omit
                # the display name. Such a card is not safely selectable.
                skipped_player_rows += 1
                continue
            players.append(
                Catalog._normalize_player(item, record_id, club_id, season_label)
            )
        if not players:
            raise ValueError(
                f"Club-season {record_id!r} has no selectable named players."
            )
        return {
            "id": record_id,
            "club": {
                "id": club_id,
                "name": club_name,
                "shortName": str(
                    _first(
                        club,
                        "shortName",
                        "short_name",
                        default=_first(raw, "clubShortName", "club_short_name", default=club_name),
                    )
                ),
                "city": _first(club, "city", default=raw.get("city")),
                "accent": _first(
                    club,
                    "accent",
                    "color",
                    default=_first(raw, "accent", "color"),
                ),
            },
            "season": {
                "id": str(_first(season, "id", default=season_label.replace("/", "-"))),
                "label": season_label.strip(),
                "startYear": start_year,
                "endYear": end_year,
            },
            "players": players,
            "source": raw.get("source")
            or raw.get("sources")
            or {
                key: raw[key]
                for key in ("sourceBacked", "coverage")
                if key in raw
            }
            or None,
            "confidence": raw.get("confidence"),
            "loaderSkippedPlayerRows": skipped_player_rows,
        }

    @staticmethod
    def _normalize_player(
        raw: Mapping[str, Any],
        record_id: str,
        club_id: str,
        season_label: str,
    ) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            raise ValueError(f"Player in {record_id!r} must be an object.")
        name = _first(raw, "name", "playerName", "player_name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Player in {record_id!r} is missing a name.")
        name = name.strip()
        positions_value = _first(
            raw,
            "positions",
            "eligiblePositions",
            "eligible_positions",
            default=_first(raw, "position", "Position"),
        )
        if isinstance(positions_value, str):
            positions_value = re.split(r"[,/;|]", positions_value)
        if not isinstance(positions_value, list) or not positions_value:
            raise ValueError(f"Player {name!r} is missing positions.")
        positions = list(dict.fromkeys(_position(item) for item in positions_value))
        player_id = _first(raw, "id", "playerSeasonId", "player_season_id")
        player_id = str(player_id or f"{_slug(name)}-{record_id}")
        person_id = str(
            _first(
                raw,
                "personId",
                "person_id",
                "playerId",
                "player_id",
                "sourcePlayerId",
            )
            or _slug(name)
        )

        def rating(*keys: str) -> float | None:
            value = _first(raw, *keys)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"Rating for player {name!r} must be numeric.")
            number = float(value)
            if not 0 <= number <= 100:
                raise ValueError(f"Rating for player {name!r} must be 0–100.")
            return round(number, 2)

        base_rating = rating("seasonRating", "season_rating", "rating", "ovr", "OVR_Rating")
        prime_rating = rating("primeRating", "prime_rating")
        raw_stats = raw.get("stats")
        stats = dict(raw_stats) if isinstance(raw_stats, dict) else {}
        for source_key, target_key in (
            ("appearances", "appearances"),
            ("starts", "starts"),
            ("minutes", "minutes"),
            ("goals", "goals"),
            ("assists", "assists"),
            ("yellowCards", "yellowCards"),
            ("yellow_cards", "yellowCards"),
            ("redCards", "redCards"),
            ("red_cards", "redCards"),
            ("marketValuePeakEur", "marketValuePeakEur"),
            ("market_value", "marketValue"),
        ):
            if source_key in raw:
                stats[target_key] = raw[source_key]
        return {
            "id": player_id,
            "personId": person_id,
            "name": name,
            "positions": positions,
            "nationality": _first(raw, "nationality", "Nationality"),
            "age": _first(raw, "age", "Age"),
            "seasonRating": base_rating,
            "primeRating": prime_rating if prime_rating is not None else base_rating,
            "ratingKind": _first(
                raw,
                "ratingKind",
                "rating_kind",
                default="unspecified",
            ),
            "clubId": club_id,
            "clubSeasonId": record_id,
            "season": season_label,
            "stats": stats,
            "source": raw.get("source")
            or raw.get("sources")
            or raw.get("statsSource"),
            "confidence": raw.get("confidence"),
        }

    def eligible(self, settings: Mapping[str, Any]) -> list[dict[str, Any]]:
        start = settings["seasonStart"]
        end = settings["seasonEnd"]
        selected = settings.get("clubSeasonIds")
        selected_set = set(selected) if isinstance(selected, list) else None
        return [
            record
            for record in self.records
            if start <= record["season"]["startYear"] <= end
            and (selected_set is None or record["id"] in selected_set)
        ]

    def public_inventory(self, include_players: bool = False) -> dict[str, Any]:
        records = []
        for item in self.records:
            record = {
                "id": item["id"],
                "club": item["club"],
                "season": item["season"],
                "playerCount": len(item["players"]),
                "source": item["source"],
                "confidence": item["confidence"],
                "loaderSkippedPlayerRows": item.get(
                    "loaderSkippedPlayerRows", 0
                ),
            }
            if include_players:
                record["players"] = item["players"]
            records.append(record)
        return {
            "schemaVersion": CATALOG_SCHEMA_VERSION,
            "metadata": self.metadata,
            "clubSeasons": records,
        }


def _normalize_settings(
    value: Any,
    mode: str,
    catalog: Catalog,
) -> dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise RequestError(400, "invalid_settings", "'settings' must be an object.")
    formation = value.get("formation", "4-3-3")
    if formation not in FORMATIONS:
        raise RequestError(
            400,
            "invalid_formation",
            f"Unsupported formation. Choose one of: {', '.join(FORMATIONS)}.",
        )
    difficulty = value.get("difficulty", "normal")
    if difficulty not in DIFFICULTY_REROLLS:
        raise RequestError(400, "invalid_difficulty", "Invalid difficulty.")
    ratings_mode = value.get("ratingsMode", "season")
    if ratings_mode not in RATINGS_MODES:
        raise RequestError(400, "invalid_ratings_mode", "Invalid ratingsMode.")
    draft_mode = value.get("draftMode", "squad-first")
    if draft_mode not in DRAFT_MODES:
        raise RequestError(400, "invalid_draft_mode", "Invalid draftMode.")
    coverage = catalog.metadata["normalizedCoverage"]
    season_start = _as_int(
        value.get("seasonStart", max(1995, coverage["earliestStartYear"])),
        "seasonStart",
        1990,
        2100,
    )
    season_end = _as_int(
        value.get("seasonEnd", coverage["latestStartYear"]),
        "seasonEnd",
        1990,
        2100,
    )
    if season_start > season_end:
        raise RequestError(
            400,
            "invalid_season_range",
            "seasonStart cannot be later than seasonEnd.",
        )
    target_picks = _as_int(
        value.get("targetPicks", len(FORMATIONS[formation])),
        "targetPicks",
        1,
        len(FORMATIONS[formation]),
    )
    max_players = _as_int(
        value.get("maxPlayers", 1 if mode == "solo" else 4),
        "maxPlayers",
        1,
        1 if mode == "solo" else 4,
    )
    club_season_ids = value.get("clubSeasonIds")
    if club_season_ids is not None:
        if (
            not isinstance(club_season_ids, list)
            or not club_season_ids
            or not all(isinstance(item, str) for item in club_season_ids)
        ):
            raise RequestError(
                400,
                "invalid_catalog_filter",
                "clubSeasonIds must be a non-empty string array.",
            )
        unknown = sorted(set(club_season_ids).difference(catalog.by_id))
        if unknown:
            raise RequestError(
                400,
                "invalid_catalog_filter",
                "clubSeasonIds contains unknown records.",
                {"unknownIds": unknown},
            )
    settings = {
        "formation": formation,
        "slots": [
            {
                "id": slot.id,
                "label": slot.label,
                "category": slot.category,
                "acceptedPositions": sorted(slot.accepted),
            }
            for slot in FORMATIONS[formation]
        ],
        "targetPicks": target_picks,
        "difficulty": difficulty,
        "rerolls": DIFFICULTY_REROLLS[difficulty],
        "showRatings": False
        if difficulty == "hard"
        else bool(value.get("showRatings", True)),
        "ratingsMode": ratings_mode,
        "draftMode": draft_mode,
        "seasonStart": season_start,
        "seasonEnd": season_end,
        "maxPlayers": max_players,
        "allowDuplicatePeople": bool(value.get("allowDuplicatePeople", False)),
        "clubSeasonIds": club_season_ids,
    }
    if not catalog.eligible(settings):
        raise RequestError(
            400,
            "empty_catalog_range",
            "No player squads are available for the selected season range.",
        )
    return settings


class RoomStore:
    """Concurrency-safe SQLite persistence and authoritative draft state."""

    def __init__(
        self,
        database_path: str | os.PathLike[str],
        catalog: Catalog | None = None,
        *,
        room_ttl_seconds: int = DEFAULT_ROOM_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not 1 <= room_ttl_seconds <= MAX_ROOM_TTL_SECONDS:
            raise ValueError("room_ttl_seconds is outside the supported range.")
        self.database_path = str(database_path)
        self.catalog = catalog or Catalog.load(os.getenv("HNL_CATALOG_PATH"))
        self.room_ttl_seconds = room_ttl_seconds
        self.clock = clock
        self._lock = threading.RLock()
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=10,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._lock:
            connection = self._connect()
            try:
                if self.database_path != ":memory:":
                    connection.execute("PRAGMA journal_mode = WAL")
                connection.executescript(
                    """
                CREATE TABLE IF NOT EXISTS rooms (
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

                CREATE TABLE IF NOT EXISTS participants (
                    id TEXT PRIMARY KEY,
                    room_code TEXT NOT NULL REFERENCES rooms(code) ON DELETE CASCADE,
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

                CREATE TABLE IF NOT EXISTS picks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_code TEXT NOT NULL REFERENCES rooms(code) ON DELETE CASCADE,
                    participant_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
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

                CREATE INDEX IF NOT EXISTS participants_room_idx
                    ON participants(room_code, seat);
                CREATE INDEX IF NOT EXISTS picks_participant_idx
                    ON picks(participant_id, turn_index);
                """
                )
            finally:
                connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def _new_code(self, connection: sqlite3.Connection) -> str:
        for _ in range(100):
            code = "".join(
                secrets.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH)
            )
            exists = connection.execute(
                "SELECT 1 FROM rooms WHERE code = ?", (code,)
            ).fetchone()
            if not exists:
                return code
        raise RuntimeError("Unable to allocate a unique room code.")

    @staticmethod
    def _normalize_code(code: str) -> str:
        normalized = code.strip().upper()
        if (
            len(normalized) != ROOM_CODE_LENGTH
            or any(character not in ROOM_CODE_ALPHABET for character in normalized)
        ):
            raise RequestError(400, "invalid_room_code", "Room code is invalid.")
        return normalized

    def _expire_if_needed(
        self,
        connection: sqlite3.Connection,
        room: sqlite3.Row,
    ) -> sqlite3.Row:
        if room["status"] != "expired" and self.clock() >= room["expires_at"]:
            connection.execute(
                "UPDATE rooms SET status = 'expired', updated_at = ?, version = version + 1 "
                "WHERE code = ?",
                (self.clock(), room["code"]),
            )
            room = connection.execute(
                "SELECT * FROM rooms WHERE code = ?", (room["code"],)
            ).fetchone()
        return room

    def _room_row(
        self,
        connection: sqlite3.Connection,
        code: str,
        *,
        mutation: bool,
    ) -> sqlite3.Row:
        normalized = self._normalize_code(code)
        room = connection.execute(
            "SELECT * FROM rooms WHERE code = ?", (normalized,)
        ).fetchone()
        if not room:
            raise RequestError(404, "room_not_found", "Room was not found.")
        room = self._expire_if_needed(connection, room)
        if mutation and room["status"] == "expired":
            raise RequestError(410, "room_expired", "This room has expired.")
        return room

    @staticmethod
    def _check_version(room: sqlite3.Row, expected_version: Any) -> int:
        if not _is_int(expected_version):
            raise RequestError(
                400,
                "expected_version_required",
                "expectedVersion must be the latest integer room version.",
            )
        if expected_version != room["version"]:
            raise RequestError(
                409,
                "version_conflict",
                "Room state changed; refresh and retry.",
                {
                    "expectedVersion": expected_version,
                    "currentVersion": room["version"],
                },
            )
        return expected_version

    @staticmethod
    def _check_turn(participant: sqlite3.Row, expected_turn: Any) -> int:
        if not _is_int(expected_turn):
            raise RequestError(
                400,
                "expected_turn_required",
                "expectedTurn must be the manager's latest integer turn.",
            )
        if expected_turn != participant["turn_index"]:
            raise RequestError(
                409,
                "turn_conflict",
                "Manager turn changed; refresh and retry.",
                {
                    "expectedTurn": expected_turn,
                    "currentTurn": participant["turn_index"],
                },
            )
        return expected_turn

    @staticmethod
    def _participant_by_token(
        connection: sqlite3.Connection,
        room_code: str,
        token: Any,
    ) -> sqlite3.Row:
        if not isinstance(token, str) or len(token) < 20:
            raise RequestError(
                401,
                "participant_token_required",
                "A valid participant token is required.",
            )
        participant = connection.execute(
            "SELECT * FROM participants WHERE room_code = ? AND token_hash = ?",
            (room_code, _sha256(token)),
        ).fetchone()
        if not participant:
            raise RequestError(
                401,
                "invalid_participant_token",
                "Participant token is not valid for this room.",
            )
        return participant

    def _touch_room(self, connection: sqlite3.Connection, code: str) -> None:
        now = self.clock()
        connection.execute(
            "UPDATE rooms SET version = version + 1, updated_at = ?, expires_at = ? "
            "WHERE code = ?",
            (now, now + self.room_ttl_seconds, code),
        )

    @staticmethod
    def _picks(
        connection: sqlite3.Connection,
        participant_id: str,
    ) -> list[dict[str, Any]]:
        rows = connection.execute(
            "SELECT payload_json FROM picks WHERE participant_id = ? "
            "ORDER BY turn_index",
            (participant_id,),
        ).fetchall()
        return [_json_loads(row["payload_json"], {}) for row in rows]

    def _available_slots(
        self,
        settings: Mapping[str, Any],
        picks: Iterable[Mapping[str, Any]],
    ) -> list[Slot]:
        filled = {pick["slotId"] for pick in picks}
        return [
            slot
            for slot in FORMATIONS[settings["formation"]]
            if slot.id not in filled
        ]

    @staticmethod
    def _selected_person_ids(picks: Iterable[Mapping[str, Any]]) -> set[str]:
        return {str(pick["player"]["personId"]) for pick in picks}

    @staticmethod
    def _selected_player_ids(picks: Iterable[Mapping[str, Any]]) -> set[str]:
        return {str(pick["player"]["id"]) for pick in picks}

    def _player_options(
        self,
        record: Mapping[str, Any],
        slots: Iterable[Slot],
        picks: Iterable[Mapping[str, Any]],
        settings: Mapping[str, Any],
    ) -> list[tuple[dict[str, Any], list[Slot]]]:
        slots_list = list(slots)
        picks_list = list(picks)
        player_ids = self._selected_player_ids(picks_list)
        person_ids = self._selected_person_ids(picks_list)
        options: list[tuple[dict[str, Any], list[Slot]]] = []
        for player in record["players"]:
            if player["id"] in player_ids:
                continue
            if (
                not settings["allowDuplicatePeople"]
                and player["personId"] in person_ids
            ):
                continue
            eligible_slots = [slot for slot in slots_list if _compatible(player, slot)]
            if eligible_slots:
                options.append((player, eligible_slots))
        return options

    def _public_player(
        self,
        player: Mapping[str, Any],
        settings: Mapping[str, Any],
        *,
        reveal_rating: bool,
    ) -> dict[str, Any]:
        result = {
            key: player.get(key)
            for key in (
                "id",
                "personId",
                "name",
                "positions",
                "nationality",
                "age",
                "ratingKind",
                "stats",
                "source",
                "confidence",
            )
        }
        selected_rating = (
            player.get("primeRating")
            if settings["ratingsMode"] == "prime"
            else player.get("seasonRating")
        )
        result["rating"] = selected_rating if reveal_rating else None
        result["ratingHidden"] = not reveal_rating
        return result

    def _current_spin_view(
        self,
        participant: sqlite3.Row,
        picks: list[dict[str, Any]],
        settings: Mapping[str, Any],
        *,
        viewer_is_owner: bool,
        room_complete: bool,
    ) -> dict[str, Any] | None:
        spin = _json_loads(participant["current_spin_json"], None)
        if not spin:
            return None
        record = self.catalog.by_id.get(spin["clubSeasonId"])
        if not record:
            return {
                "clubSeasonId": spin["clubSeasonId"],
                "turn": spin["turn"],
                "catalogRecordMissing": True,
            }
        base = {
            "clubSeasonId": record["id"],
            "club": record["club"],
            "season": record["season"],
            "turn": spin["turn"],
            "spinNumber": spin["spinNumber"],
            "lockedSlotId": spin.get("lockedSlotId"),
        }
        if not viewer_is_owner:
            base["players"] = None
            base["squadHidden"] = True
            return base
        slots = self._available_slots(settings, picks)
        if spin.get("lockedSlotId"):
            slots = [slot for slot in slots if slot.id == spin["lockedSlotId"]]
        reveal = settings["showRatings"] or room_complete
        public_players = []
        options = {
            player["id"]: eligible_slots
            for player, eligible_slots in self._player_options(
                record, slots, picks, settings
            )
        }
        for player in record["players"]:
            public = self._public_player(
                player,
                settings,
                reveal_rating=reveal,
            )
            eligible = options.get(player["id"], [])
            public["available"] = bool(eligible)
            public["eligibleSlotIds"] = [slot.id for slot in eligible]
            public_players.append(public)
        base["players"] = public_players
        base["squadHidden"] = False
        return base

    @staticmethod
    def _sample_poisson(rng: random.Random, expected: float) -> int:
        threshold = math.exp(-max(0.05, min(6.0, expected)))
        product = 1.0
        count = 0
        while product > threshold:
            count += 1
            product *= rng.random()
        return count - 1

    @staticmethod
    def _league_schedule(
        team_ids: list[str],
    ) -> list[list[tuple[str, str]]]:
        """Build a four-cycle round robin: 36 matchweeks for ten teams."""
        if len(team_ids) < 2 or len(team_ids) % 2:
            raise ValueError("League schedule requires an even number of teams.")
        rotating = list(team_ids)
        first_cycle: list[list[tuple[str, str]]] = []
        for round_index in range(len(rotating) - 1):
            pairings: list[tuple[str, str]] = []
            half = len(rotating) // 2
            for pair_index in range(half):
                left = rotating[pair_index]
                right = rotating[-1 - pair_index]
                if pair_index == 0:
                    home, away = (
                        (left, right)
                        if round_index % 2 == 0
                        else (right, left)
                    )
                elif (round_index + pair_index) % 2 == 0:
                    home, away = left, right
                else:
                    home, away = right, left
                pairings.append((home, away))
            first_cycle.append(pairings)
            rotating = [rotating[0], rotating[-1], *rotating[1:-1]]
        reverse_cycle = [
            [(away, home) for home, away in matchweek]
            for matchweek in first_cycle
        ]
        return first_cycle + reverse_cycle + first_cycle + reverse_cycle

    @staticmethod
    def _weighted_pick(
        rng: random.Random,
        candidates: list[Mapping[str, Any]],
        weights: list[float],
    ) -> Mapping[str, Any]:
        total = sum(max(0.001, weight) for weight in weights)
        threshold = rng.random() * total
        cumulative = 0.0
        for candidate, weight in zip(candidates, weights):
            cumulative += max(0.001, weight)
            if threshold <= cumulative:
                return candidate
        return candidates[-1]

    @staticmethod
    def _scorer_weight(pick: Mapping[str, Any]) -> float:
        positions = set(pick.get("player", {}).get("positions") or [])
        role_weights = {
            "GK": 0.03,
            "CB": 0.55,
            "RB": 0.8,
            "LB": 0.8,
            "RWB": 1.1,
            "LWB": 1.1,
            "DM": 1.1,
            "CM": 1.8,
            "RM": 2.2,
            "LM": 2.2,
            "AM": 3.2,
            "SS": 4.2,
            "RW": 4.4,
            "LW": 4.4,
            "CF": 5.7,
            "ST": 6.0,
            "DEF": 0.65,
            "MID": 1.8,
            "FWD": 4.8,
        }
        positional = max((role_weights.get(role, 1.0) for role in positions), default=1.0)
        rating = pick.get("selectedRating")
        rating_factor = (
            max(0.65, 1.0 + (float(rating) - 75.0) * 0.025)
            if isinstance(rating, (int, float))
            else 1.0
        )
        return positional * rating_factor

    @staticmethod
    def _assist_weight(pick: Mapping[str, Any]) -> float:
        positions = set(pick.get("player", {}).get("positions") or [])
        role_weights = {
            "GK": 0.05,
            "CB": 0.45,
            "RB": 1.2,
            "LB": 1.2,
            "RWB": 1.8,
            "LWB": 1.8,
            "DM": 1.5,
            "CM": 2.7,
            "RM": 2.8,
            "LM": 2.8,
            "AM": 4.0,
            "SS": 3.2,
            "RW": 3.6,
            "LW": 3.6,
            "CF": 2.3,
            "ST": 1.8,
            "DEF": 0.7,
            "MID": 2.6,
            "FWD": 2.5,
        }
        return max(
            (role_weights.get(role, 1.0) for role in positions),
            default=1.0,
        )

    @classmethod
    def _goal_events(
        cls,
        rng: random.Random,
        picks: list[Mapping[str, Any]],
        goal_count: int,
        player_stats: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not picks or goal_count <= 0:
            return []
        minutes = sorted(rng.randint(1, 90) for _ in range(goal_count))
        scorer_weights = [cls._scorer_weight(pick) for pick in picks]
        events: list[dict[str, Any]] = []
        for minute in minutes:
            scorer = cls._weighted_pick(rng, picks, scorer_weights)
            scorer_player = scorer["player"]
            scorer_id = str(scorer_player["id"])
            event: dict[str, Any] = {
                "playerId": scorer_id,
                "playerName": scorer_player["name"],
                "minute": minute,
            }
            player_stats[scorer_id]["goals"] += 1
            assist_candidates = [
                pick
                for pick in picks
                if str(pick["player"]["id"]) != scorer_id
            ]
            if assist_candidates and rng.random() < 0.72:
                assister = cls._weighted_pick(
                    rng,
                    assist_candidates,
                    [cls._assist_weight(pick) for pick in assist_candidates],
                )
                assist_player = assister["player"]
                assist_id = str(assist_player["id"])
                event["assistPlayerId"] = assist_id
                event["assistPlayerName"] = assist_player["name"]
                player_stats[assist_id]["assists"] += 1
            events.append(event)
        return events

    @staticmethod
    def _projection(average_rating: float) -> dict[str, Any]:
        opponent_ratings = [
            float(opponent["rating"]) for opponent in HNL_SIMULATION_OPPONENTS
        ]
        projected_position = (
            1
            + sum(
                opponent_rating > average_rating
                for opponent_rating in opponent_ratings
            )
        )
        expected_points = max(
            22.0,
            min(104.0, 48.0 + (average_rating - 74.0) * 2.15),
        )

        def logistic(value: float) -> float:
            return 1.0 / (1.0 + math.exp(-value))

        title_probability = logistic((average_rating - 81.0) / 2.8)
        top_four_probability = logistic((average_rating - 75.0) / 2.5)
        perfect_probability = 0.05 * logistic(
            (average_rating - 95.0) / 1.7
        )
        return {
            "model": "editorial-preseason-odds-v1",
            "projectedPosition": projected_position,
            "expectedPoints": round(expected_points, 1),
            "titleProbability": round(title_probability, 4),
            "topFourProbability": round(top_four_probability, 4),
            "perfectProbability": round(perfect_probability, 6),
            "disclosure": (
                "In-game probabilities only; not official forecasts or "
                "betting odds."
            ),
        }

    @staticmethod
    def _longest_streak(
        matches: Iterable[Mapping[str, Any]],
        predicate: Callable[[Mapping[str, Any]], bool],
    ) -> int:
        longest = current = 0
        for match in matches:
            if predicate(match):
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        return longest

    @staticmethod
    def _match_record(
        match: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        if match is None:
            return None
        return {
            "matchweek": match["matchweek"],
            "opponent": match["opponent"],
            "venue": match["venue"],
            "goalsFor": match["goalsFor"],
            "goalsAgainst": match["goalsAgainst"],
            "outcome": match["outcome"],
            "score": f"{match['goalsFor']}–{match['goalsAgainst']}",
        }

    @classmethod
    def _season_result(
        cls,
        room_seed: int,
        seat: int,
        picks: Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Simulate one deterministic ten-team, 36-match HNL-style season.

        The full fixture list, table, player events, records and awards are
        derived server-side from the committed XI, room seed and manager seat.
        The model remains an editorial game mechanic rather than a forecast.
        """
        picks_list = list(picks)
        ratings = [
            float(pick["selectedRating"])
            for pick in picks_list
            if isinstance(pick.get("selectedRating"), (int, float))
        ]
        average = sum(ratings) / len(ratings) if ratings else 70.0
        material = f"{room_seed}|seat:{seat}|season-result:v2"
        result_seed = int.from_bytes(
            hashlib.sha256(material.encode("utf-8")).digest()[:8],
            "big",
        )
        rng = random.Random(result_seed)
        drafted_id = "drafted-xi"
        teams: list[dict[str, Any]] = [
            {
                "id": drafted_id,
                "name": "Draft XI",
                "shortName": "XI",
                "rating": average,
                "accent": "#f2c94c",
                "isDraftedXI": True,
            },
            *[
                {**opponent, "isDraftedXI": False}
                for opponent in HNL_SIMULATION_OPPONENTS
            ],
        ]
        teams_by_id = {team["id"]: team for team in teams}
        table_stats: dict[str, dict[str, int]] = {
            team["id"]: {
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "goalsFor": 0,
                "goalsAgainst": 0,
                "goalDifference": 0,
                "points": 0,
            }
            for team in teams
        }
        player_stats_by_id: dict[str, dict[str, Any]] = {}
        for pick in picks_list:
            player = pick["player"]
            player_id = str(player["id"])
            player_stats_by_id[player_id] = {
                "playerId": player_id,
                "playerName": player["name"],
                "slotId": pick.get("slotId"),
                "positions": list(player.get("positions") or []),
                "rating": pick.get("selectedRating"),
                "appearances": 36,
                "starts": 36,
                "goals": 0,
                "assists": 0,
                "cleanSheets": 0,
            }

        schedule = cls._league_schedule([team["id"] for team in teams])
        matches: list[dict[str, Any]] = []
        running = {
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "points": 0,
            "goalsFor": 0,
            "goalsAgainst": 0,
            "goalDifference": 0,
        }

        def apply_table_result(
            home_id: str,
            away_id: str,
            home_goals: int,
            away_goals: int,
        ) -> None:
            home_stats = table_stats[home_id]
            away_stats = table_stats[away_id]
            home_stats["played"] += 1
            away_stats["played"] += 1
            home_stats["goalsFor"] += home_goals
            home_stats["goalsAgainst"] += away_goals
            away_stats["goalsFor"] += away_goals
            away_stats["goalsAgainst"] += home_goals
            if home_goals > away_goals:
                home_stats["wins"] += 1
                home_stats["points"] += 3
                away_stats["losses"] += 1
            elif home_goals < away_goals:
                away_stats["wins"] += 1
                away_stats["points"] += 3
                home_stats["losses"] += 1
            else:
                home_stats["draws"] += 1
                away_stats["draws"] += 1
                home_stats["points"] += 1
                away_stats["points"] += 1
            home_stats["goalDifference"] = (
                home_stats["goalsFor"] - home_stats["goalsAgainst"]
            )
            away_stats["goalDifference"] = (
                away_stats["goalsFor"] - away_stats["goalsAgainst"]
            )

        for matchweek, pairings in enumerate(schedule, start=1):
            drafted_match: dict[str, Any] | None = None
            for home_id, away_id in pairings:
                home = teams_by_id[home_id]
                away = teams_by_id[away_id]
                rating_difference = float(home["rating"]) - float(away["rating"])
                expected_home = max(
                    0.08,
                    min(5.8, 1.43 * math.exp(0.041 * rating_difference)),
                )
                expected_away = max(
                    0.08,
                    min(5.8, 1.13 * math.exp(-0.039 * rating_difference)),
                )
                home_goals = cls._sample_poisson(rng, expected_home)
                away_goals = cls._sample_poisson(rng, expected_away)
                apply_table_result(home_id, away_id, home_goals, away_goals)
                if drafted_id not in {home_id, away_id}:
                    continue
                at_home = home_id == drafted_id
                opponent = away if at_home else home
                goals_for = home_goals if at_home else away_goals
                goals_against = away_goals if at_home else home_goals
                expected_for = expected_home if at_home else expected_away
                expected_against = expected_away if at_home else expected_home
                if goals_for > goals_against:
                    outcome = "W"
                    points_earned = 3
                elif goals_for == goals_against:
                    outcome = "D"
                    points_earned = 1
                else:
                    outcome = "L"
                    points_earned = 0
                running["played"] += 1
                running["goalsFor"] += goals_for
                running["goalsAgainst"] += goals_against
                running["points"] += points_earned
                if outcome == "W":
                    running["wins"] += 1
                elif outcome == "D":
                    running["draws"] += 1
                else:
                    running["losses"] += 1
                running["goalDifference"] = (
                    running["goalsFor"] - running["goalsAgainst"]
                )
                scorers = cls._goal_events(
                    rng,
                    picks_list,
                    goals_for,
                    player_stats_by_id,
                )
                if goals_against == 0:
                    for player_stat in player_stats_by_id.values():
                        if "GK" in player_stat["positions"]:
                            player_stat["cleanSheets"] += 1
                opponent_goal_minutes = sorted(
                    rng.randint(1, 90) for _ in range(goals_against)
                )
                drafted_match = {
                    "matchweek": matchweek,
                    "opponent": {
                        key: opponent[key]
                        for key in ("id", "name", "shortName", "accent")
                    },
                    "venue": "H" if at_home else "A",
                    "homeTeamId": home_id,
                    "awayTeamId": away_id,
                    "homeGoals": home_goals,
                    "awayGoals": away_goals,
                    "goalsFor": goals_for,
                    "goalsAgainst": goals_against,
                    "outcome": outcome,
                    "pointsEarned": points_earned,
                    "expectedGoalsFor": round(expected_for, 2),
                    "expectedGoalsAgainst": round(expected_against, 2),
                    "scorers": scorers,
                    "opponentGoalMinutes": opponent_goal_minutes,
                    "running": dict(running),
                }
            if drafted_match is None:
                raise RuntimeError(
                    f"Drafted XI is missing from matchweek {matchweek}."
                )
            matches.append(drafted_match)

        table_rows: list[dict[str, Any]] = []
        for team in teams:
            table_rows.append(
                {
                    "teamId": team["id"],
                    "name": team["name"],
                    "shortName": team["shortName"],
                    "accent": team["accent"],
                    "isDraftedXI": team["isDraftedXI"],
                    **table_stats[team["id"]],
                }
            )
        table_rows.sort(
            key=lambda row: (
                -row["points"],
                -row["goalDifference"],
                -row["goalsFor"],
                row["name"].casefold(),
            )
        )
        for position, row in enumerate(table_rows, start=1):
            row["position"] = position
        drafted_row = next(row for row in table_rows if row["isDraftedXI"])
        player_stats = list(player_stats_by_id.values())
        for player_stat in player_stats:
            player_stat["goalContributions"] = (
                player_stat["goals"] + player_stat["assists"]
            )

        def best_player(
            key: Callable[[Mapping[str, Any]], tuple[Any, ...]],
        ) -> dict[str, Any] | None:
            if not player_stats:
                return None
            player = max(player_stats, key=key)
            return {
                "playerId": player["playerId"],
                "playerName": player["playerName"],
                "goals": player["goals"],
                "assists": player["assists"],
            }

        top_scorer = best_player(
            lambda player: (
                player["goals"],
                player["assists"],
                player["rating"] or 0,
                player["playerName"],
            )
        )
        top_creator = best_player(
            lambda player: (
                player["assists"],
                player["goals"],
                player["rating"] or 0,
                player["playerName"],
            )
        )
        player_of_season = best_player(
            lambda player: (
                player["goals"] * 4 + player["assists"] * 3,
                player["rating"] or 0,
                player["goals"],
                player["playerName"],
            )
        )
        best_attack = drafted_row["goalsFor"] == max(
            row["goalsFor"] for row in table_rows
        )
        best_defence = drafted_row["goalsAgainst"] == min(
            row["goalsAgainst"] for row in table_rows
        )
        earned_awards: list[dict[str, str]] = []
        for won, code, name in (
            (drafted_row["position"] == 1, "league-title", "Prvak HNL-a"),
            (drafted_row["losses"] == 0, "invincible", "Neporaženi"),
            (drafted_row["wins"] == 36, "perfect-season", "36–0"),
            (drafted_row["points"] >= 100, "centurions", "100+ bodova"),
            (best_attack, "best-attack", "Najbolji napad"),
            (best_defence, "best-defence", "Najbolja obrana"),
        ):
            if won:
                earned_awards.append({"code": code, "name": name})

        streaks = {
            "longestWinning": cls._longest_streak(
                matches, lambda match: match["outcome"] == "W"
            ),
            "longestUnbeaten": cls._longest_streak(
                matches, lambda match: match["outcome"] != "L"
            ),
            "longestScoring": cls._longest_streak(
                matches, lambda match: match["goalsFor"] > 0
            ),
            "longestCleanSheet": cls._longest_streak(
                matches, lambda match: match["goalsAgainst"] == 0
            ),
            "longestLosing": cls._longest_streak(
                matches, lambda match: match["outcome"] == "L"
            ),
        }
        winning_matches = [
            match for match in matches if match["outcome"] == "W"
        ]
        biggest_win_match = (
            max(
                winning_matches,
                key=lambda match: (
                    match["goalsFor"] - match["goalsAgainst"],
                    match["goalsFor"],
                    -match["matchweek"],
                ),
            )
            if winning_matches
            else None
        )
        highest_scoring_match = max(
            matches,
            key=lambda match: (
                match["goalsFor"] + match["goalsAgainst"],
                abs(match["goalsFor"] - match["goalsAgainst"]),
                -match["matchweek"],
            ),
        )
        biggest_win = cls._match_record(biggest_win_match)
        highest_scoring = cls._match_record(highest_scoring_match)
        projection = cls._projection(average)
        records = {
            **streaks,
            "longestWinningStreak": streaks["longestWinning"],
            "longestUnbeatenStreak": streaks["longestUnbeaten"],
            "longestScoringStreak": streaks["longestScoring"],
            "longestCleanSheetStreak": streaks["longestCleanSheet"],
            "biggestWin": biggest_win,
            "highestScoringMatch": highest_scoring,
        }
        awards = {
            "leagueTitle": drafted_row["position"] == 1,
            "invincible": drafted_row["losses"] == 0,
            "perfectSeason": drafted_row["wins"] == 36,
            "bestAttack": best_attack,
            "bestDefence": best_defence,
            "earned": earned_awards,
            "topScorer": top_scorer,
            "topCreator": top_creator,
            "playerOfSeason": player_of_season,
        }
        return {
            "model": "editorial-rating-poisson-v2",
            "confidence": 0.35,
            "disclosure": "Game output, not an official forecast or betting model.",
            "seed": result_seed,
            "played": drafted_row["played"],
            "wins": drafted_row["wins"],
            "draws": drafted_row["draws"],
            "losses": drafted_row["losses"],
            "points": drafted_row["points"],
            "goalsFor": drafted_row["goalsFor"],
            "goalsAgainst": drafted_row["goalsAgainst"],
            "goalDifference": drafted_row["goalDifference"],
            "averageRating": round(average, 2),
            "finalPosition": drafted_row["position"],
            "projection": projection,
            "matches": matches,
            "playerStats": player_stats,
            "awards": awards,
            "records": records,
            "streaks": streaks,
            "biggestWin": biggest_win,
            "highestScoringMatch": highest_scoring,
            "leagueTable": table_rows,
            "tieBreakOrder": [
                "points",
                "goalDifference",
                "goalsFor",
                "name",
            ],
        }

    def _room_view(
        self,
        connection: sqlite3.Connection,
        room: sqlite3.Row,
        viewer: sqlite3.Row | None,
    ) -> dict[str, Any]:
        settings = _json_loads(room["settings_json"], {})
        participant_rows = connection.execute(
            "SELECT * FROM participants WHERE room_code = ? ORDER BY seat",
            (room["code"],),
        ).fetchall()
        participants = []
        room_complete = room["status"] == "complete"
        for row in participant_rows:
            picks = self._picks(connection, row["id"])
            reveal = settings["showRatings"] or room_complete
            visible_picks = []
            for pick in picks:
                public_pick = dict(pick)
                if not reveal:
                    public_pick["player"] = dict(public_pick["player"])
                    public_pick["player"]["rating"] = None
                    public_pick["player"]["ratingHidden"] = True
                    public_pick["selectedRating"] = None
                visible_picks.append(public_pick)
            numeric_ratings = [
                pick.get("selectedRating")
                for pick in picks
                if isinstance(pick.get("selectedRating"), (int, float))
            ]
            result = (
                self._season_result(room["seed"], row["seat"], picks)
                if room_complete
                else None
            )
            participants.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "seat": row["seat"],
                    "isHost": row["id"] == room["host_participant_id"],
                    "status": row["status"],
                    "turn": row["turn_index"],
                    "rerollsRemaining": row["rerolls_remaining"],
                    "picks": visible_picks,
                    "filledSlotIds": [pick["slotId"] for pick in picks],
                    "squadRating": round(
                        sum(numeric_ratings) / len(numeric_ratings), 2
                    )
                    if numeric_ratings and reveal
                    else None,
                    "result": result,
                    "currentSpin": self._current_spin_view(
                        row,
                        picks,
                        settings,
                        viewer_is_owner=viewer is not None and viewer["id"] == row["id"],
                        room_complete=room_complete,
                    ),
                }
            )
        leaderboard = None
        if room_complete:
            leaderboard = sorted(
                [
                    {
                        "participantId": item["id"],
                        "name": item["name"],
                        "squadRating": item["squadRating"],
                        "points": item["result"]["points"],
                        "goalDifference": item["result"]["goalDifference"],
                        "goalsFor": item["result"]["goalsFor"],
                        "record": {
                            "wins": item["result"]["wins"],
                            "draws": item["result"]["draws"],
                            "losses": item["result"]["losses"],
                        },
                    }
                    for item in participants
                ],
                key=lambda item: (
                    -item["points"],
                    -item["goalDifference"],
                    -item["goalsFor"],
                    -(item["squadRating"] or 0),
                    item["name"].casefold(),
                ),
            )
            for rank, item in enumerate(leaderboard, start=1):
                item["rank"] = rank
        return {
            "apiVersion": API_VERSION,
            "code": room["code"],
            "mode": room["mode"],
            "status": room["status"],
            "version": room["version"],
            "seed": room["seed"],
            "hostParticipantId": room["host_participant_id"],
            "viewerParticipantId": viewer["id"] if viewer else None,
            "settings": settings,
            "participants": participants,
            "leaderboard": leaderboard,
            "catalog": {
                "completeness": self.catalog.metadata.get("completeness"),
                "confidence": self.catalog.metadata.get("confidence"),
                "sourcePath": self.catalog.metadata.get("sourcePath"),
            },
            "createdAt": _utc_timestamp(room["created_at"]),
            "updatedAt": _utc_timestamp(room["updated_at"]),
            "expiresAt": _utc_timestamp(room["expires_at"]),
        }

    def create_room(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise RequestError(400, "invalid_payload", "JSON object required.")
        mode = payload.get("mode", "solo")
        if mode not in ROOM_MODES:
            raise RequestError(400, "invalid_mode", "mode must be solo or live.")
        name = _clean_name(payload.get("name"))
        seed_value = payload.get("seed")
        if seed_value is None:
            seed = secrets.randbits(63)
        else:
            seed = _as_int(seed_value, "seed", 0, (1 << 63) - 1)
        settings = _normalize_settings(payload.get("settings"), mode, self.catalog)
        token = secrets.token_urlsafe(32)
        participant_id = uuid.uuid4().hex
        now = self.clock()
        with self._transaction() as connection:
            code = self._new_code(connection)
            connection.execute(
                "INSERT INTO rooms "
                "(code, mode, status, seed, settings_json, host_participant_id, "
                "version, created_at, updated_at, expires_at) "
                "VALUES (?, ?, 'lobby', ?, ?, ?, 1, ?, ?, ?)",
                (
                    code,
                    mode,
                    seed,
                    _canonical_json(settings),
                    participant_id,
                    now,
                    now,
                    now + self.room_ttl_seconds,
                ),
            )
            connection.execute(
                "INSERT INTO participants "
                "(id, room_code, name, token_hash, seat, status, turn_index, "
                "spin_count, rerolls_remaining, current_spin_json, "
                "spin_history_json, joined_at, updated_at) "
                "VALUES (?, ?, ?, ?, 1, 'lobby', 0, 0, ?, NULL, '[]', ?, ?)",
                (
                    participant_id,
                    code,
                    name,
                    _sha256(token),
                    settings["rerolls"],
                    now,
                    now,
                ),
            )
            room = self._room_row(connection, code, mutation=False)
            view = self._room_view(
                connection,
                room,
                connection.execute(
                    "SELECT * FROM participants WHERE id = ?", (participant_id,)
                ).fetchone(),
            )
        return {
            "roomCode": code,
            "participantId": participant_id,
            "participantToken": token,
            "room": view,
        }

    def join_room(self, code: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise RequestError(400, "invalid_payload", "JSON object required.")
        name = _clean_name(payload.get("name"))
        token = secrets.token_urlsafe(32)
        participant_id = uuid.uuid4().hex
        now = self.clock()
        with self._transaction() as connection:
            room = self._room_row(connection, code, mutation=True)
            if room["mode"] != "live":
                raise RequestError(
                    409,
                    "solo_room",
                    "Solo rooms cannot be joined.",
                )
            if room["status"] != "lobby":
                raise RequestError(
                    409,
                    "room_already_started",
                    "This room has already started.",
                )
            settings = _json_loads(room["settings_json"], {})
            participants = connection.execute(
                "SELECT * FROM participants WHERE room_code = ? ORDER BY seat",
                (room["code"],),
            ).fetchall()
            if len(participants) >= settings["maxPlayers"]:
                raise RequestError(409, "room_full", "This room is full.")
            if any(item["name"].casefold() == name.casefold() for item in participants):
                raise RequestError(
                    409,
                    "name_taken",
                    "Choose a different manager name in this room.",
                )
            seat = max(item["seat"] for item in participants) + 1
            connection.execute(
                "INSERT INTO participants "
                "(id, room_code, name, token_hash, seat, status, turn_index, "
                "spin_count, rerolls_remaining, current_spin_json, "
                "spin_history_json, joined_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 'lobby', 0, 0, ?, NULL, '[]', ?, ?)",
                (
                    participant_id,
                    room["code"],
                    name,
                    _sha256(token),
                    seat,
                    settings["rerolls"],
                    now,
                    now,
                ),
            )
            self._touch_room(connection, room["code"])
            room = self._room_row(connection, room["code"], mutation=False)
            viewer = connection.execute(
                "SELECT * FROM participants WHERE id = ?", (participant_id,)
            ).fetchone()
            view = self._room_view(connection, room, viewer)
        return {
            "roomCode": room["code"],
            "participantId": participant_id,
            "participantToken": token,
            "room": view,
        }

    def get_room(self, code: str, token: str | None = None) -> dict[str, Any]:
        with self._transaction() as connection:
            room = self._room_row(connection, code, mutation=False)
            viewer = (
                self._participant_by_token(connection, room["code"], token)
                if token
                else None
            )
            return self._room_view(connection, room, viewer)

    def start_room(
        self,
        code: str,
        token: str,
        expected_version: Any,
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            room = self._room_row(connection, code, mutation=True)
            self._check_version(room, expected_version)
            participant = self._participant_by_token(
                connection, room["code"], token
            )
            if participant["id"] != room["host_participant_id"]:
                raise RequestError(
                    403,
                    "host_required",
                    "Only the room host can start the draft.",
                )
            if room["status"] != "lobby":
                raise RequestError(
                    409,
                    "invalid_room_status",
                    "Only a lobby can be started.",
                )
            now = self.clock()
            connection.execute(
                "UPDATE rooms SET status = 'drafting' WHERE code = ?",
                (room["code"],),
            )
            connection.execute(
                "UPDATE participants SET status = 'drafting', updated_at = ? "
                "WHERE room_code = ?",
                (now, room["code"]),
            )
            self._touch_room(connection, room["code"])
            room = self._room_row(connection, room["code"], mutation=False)
            participant = self._participant_by_token(
                connection, room["code"], token
            )
            return self._room_view(connection, room, participant)

    @staticmethod
    def _deterministic_index(
        seed: int,
        seat: int,
        turn: int,
        spin_number: int,
        count: int,
    ) -> int:
        material = f"{seed}|seat:{seat}|turn:{turn}|spin:{spin_number}"
        digest = hashlib.sha256(material.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") % count

    def spin(
        self,
        code: str,
        token: str,
        expected_version: Any,
        expected_turn: Any,
        *,
        reroll: bool = False,
        slot_id: str | None = None,
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            room = self._room_row(connection, code, mutation=True)
            self._check_version(room, expected_version)
            participant = self._participant_by_token(
                connection, room["code"], token
            )
            self._check_turn(participant, expected_turn)
            if room["status"] != "drafting" or participant["status"] != "drafting":
                raise RequestError(
                    409,
                    "draft_not_active",
                    "The manager is not in an active draft.",
                )
            settings = _json_loads(room["settings_json"], {})
            picks = self._picks(connection, participant["id"])
            slots = self._available_slots(settings, picks)
            current = _json_loads(participant["current_spin_json"], None)
            if current and not reroll:
                raise RequestError(
                    409,
                    "already_spun",
                    "Pick a player or use a reroll before spinning again.",
                )
            if reroll:
                if not current:
                    raise RequestError(
                        409,
                        "nothing_to_reroll",
                        "Spin once before using a reroll.",
                    )
                if participant["rerolls_remaining"] <= 0:
                    raise RequestError(
                        409,
                        "no_rerolls_remaining",
                        "No rerolls remain.",
                    )
            if settings["draftMode"] == "position-first":
                locked_slot_id = (
                    current.get("lockedSlotId") if current and reroll else slot_id
                )
                if not isinstance(locked_slot_id, str):
                    raise RequestError(
                        400,
                        "slot_required",
                        "slotId is required in position-first mode.",
                    )
                matching = [slot for slot in slots if slot.id == locked_slot_id]
                if not matching:
                    raise RequestError(
                        409,
                        "slot_unavailable",
                        "The requested slot is invalid or already filled.",
                    )
                slots = matching
            else:
                locked_slot_id = None
                if slot_id is not None:
                    raise RequestError(
                        400,
                        "unexpected_slot",
                        "Choose the slot when picking in squad-first mode.",
                    )
            candidates = [
                record
                for record in self.catalog.eligible(settings)
                if self._player_options(record, slots, picks, settings)
            ]
            if not candidates:
                raise RequestError(
                    409,
                    "catalog_exhausted",
                    "No eligible player remains for the open formation slots.",
                    {
                        "openSlotIds": [slot.id for slot in slots],
                        "catalogCompleteness": self.catalog.metadata.get(
                            "completeness"
                        ),
                    },
                )
            history = _json_loads(participant["spin_history_json"], [])
            unseen = [item for item in candidates if item["id"] not in history]
            if reroll and current and len(candidates) > 1:
                unseen_without_current = [
                    item
                    for item in unseen
                    if item["id"] != current["clubSeasonId"]
                ]
                if unseen_without_current:
                    unseen = unseen_without_current
            if not unseen:
                history = []
                unseen = [
                    item
                    for item in candidates
                    if not (
                        reroll
                        and current
                        and len(candidates) > 1
                        and item["id"] == current["clubSeasonId"]
                    )
                ]
                if not unseen:
                    unseen = candidates
            spin_number = participant["spin_count"] + 1
            index = self._deterministic_index(
                room["seed"],
                participant["seat"],
                participant["turn_index"],
                spin_number,
                len(unseen),
            )
            selected = sorted(unseen, key=lambda item: item["id"])[index]
            history.append(selected["id"])
            spin_payload = {
                "clubSeasonId": selected["id"],
                "turn": participant["turn_index"],
                "spinNumber": spin_number,
                "lockedSlotId": locked_slot_id,
            }
            rerolls_remaining = participant["rerolls_remaining"] - (1 if reroll else 0)
            now = self.clock()
            connection.execute(
                "UPDATE participants SET spin_count = ?, rerolls_remaining = ?, "
                "current_spin_json = ?, spin_history_json = ?, updated_at = ? "
                "WHERE id = ?",
                (
                    spin_number,
                    rerolls_remaining,
                    _canonical_json(spin_payload),
                    _canonical_json(history),
                    now,
                    participant["id"],
                ),
            )
            self._touch_room(connection, room["code"])
            room = self._room_row(connection, room["code"], mutation=False)
            participant = self._participant_by_token(
                connection, room["code"], token
            )
            return self._room_view(connection, room, participant)

    def pick(
        self,
        code: str,
        token: str,
        expected_version: Any,
        expected_turn: Any,
        player_season_id: Any,
        slot_id: Any,
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            room = self._room_row(connection, code, mutation=True)
            self._check_version(room, expected_version)
            participant = self._participant_by_token(
                connection, room["code"], token
            )
            self._check_turn(participant, expected_turn)
            if room["status"] != "drafting" or participant["status"] != "drafting":
                raise RequestError(
                    409,
                    "draft_not_active",
                    "The manager is not in an active draft.",
                )
            current = _json_loads(participant["current_spin_json"], None)
            if not current or current["turn"] != participant["turn_index"]:
                raise RequestError(
                    409,
                    "spin_required",
                    "Spin a club-season before selecting a player.",
                )
            if not isinstance(player_season_id, str):
                raise RequestError(
                    400,
                    "player_required",
                    "playerSeasonId is required.",
                )
            settings = _json_loads(room["settings_json"], {})
            picks = self._picks(connection, participant["id"])
            slots = self._available_slots(settings, picks)
            if settings["draftMode"] == "position-first":
                slot_id = current.get("lockedSlotId")
            if not isinstance(slot_id, str):
                raise RequestError(400, "slot_required", "slotId is required.")
            matching_slots = [slot for slot in slots if slot.id == slot_id]
            if not matching_slots:
                raise RequestError(
                    409,
                    "slot_unavailable",
                    "The requested slot is invalid or already filled.",
                )
            slot = matching_slots[0]
            record = self.catalog.by_id.get(current["clubSeasonId"])
            if not record:
                raise RequestError(
                    409,
                    "catalog_record_missing",
                    "The spun catalog record is no longer available.",
                )
            player = next(
                (
                    item
                    for item in record["players"]
                    if item["id"] == player_season_id
                ),
                None,
            )
            if not player:
                raise RequestError(
                    400,
                    "player_not_in_squad",
                    "The selected player does not belong to the spun club-season.",
                )
            options = self._player_options(record, [slot], picks, settings)
            if player["id"] not in {item["id"] for item, _ in options}:
                raise RequestError(
                    409,
                    "player_ineligible",
                    "The player is duplicated or cannot play in this slot.",
                )
            selected_rating = (
                player.get("primeRating")
                if settings["ratingsMode"] == "prime"
                else player.get("seasonRating")
            )
            public_player = self._public_player(
                player,
                settings,
                reveal_rating=True,
            )
            pick_payload = {
                "turn": participant["turn_index"],
                "slotId": slot.id,
                "slotLabel": slot.label,
                "clubSeason": {
                    "id": record["id"],
                    "club": record["club"],
                    "season": record["season"],
                    "source": record["source"],
                    "confidence": record["confidence"],
                },
                "player": public_player,
                "selectedRating": selected_rating,
                "ratingsMode": settings["ratingsMode"],
            }
            now = self.clock()
            try:
                connection.execute(
                    "INSERT INTO picks "
                    "(room_code, participant_id, turn_index, club_season_id, "
                    "player_season_id, person_id, slot_id, payload_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        room["code"],
                        participant["id"],
                        participant["turn_index"],
                        record["id"],
                        player["id"],
                        player["personId"],
                        slot.id,
                        _canonical_json(pick_payload),
                        now,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise RequestError(
                    409,
                    "duplicate_pick",
                    "This player, slot, or turn was already committed.",
                ) from error
            next_turn = participant["turn_index"] + 1
            status = (
                "complete"
                if next_turn >= settings["targetPicks"]
                else "drafting"
            )
            connection.execute(
                "UPDATE participants SET turn_index = ?, status = ?, "
                "current_spin_json = NULL, updated_at = ? WHERE id = ?",
                (next_turn, status, now, participant["id"]),
            )
            incomplete = connection.execute(
                "SELECT COUNT(*) AS count FROM participants "
                "WHERE room_code = ? AND status != 'complete'",
                (room["code"],),
            ).fetchone()["count"]
            if incomplete == 0:
                connection.execute(
                    "UPDATE rooms SET status = 'complete' WHERE code = ?",
                    (room["code"],),
                )
            self._touch_room(connection, room["code"])
            room = self._room_row(connection, room["code"], mutation=False)
            participant = self._participant_by_token(
                connection, room["code"], token
            )
            return self._room_view(connection, room, participant)

    def move(
        self,
        code: str,
        token: str,
        expected_version: Any,
        from_slot_id: Any,
        to_slot_id: Any,
        *,
        swap: bool = False,
    ) -> dict[str, Any]:
        """Move a committed pick to an eligible open slot or swap two picks."""
        if not isinstance(from_slot_id, str) or not isinstance(to_slot_id, str):
            raise RequestError(
                400,
                "slots_required",
                "fromSlotId and toSlotId are required.",
            )
        if from_slot_id == to_slot_id:
            raise RequestError(
                400,
                "same_slot",
                "Choose a different destination slot.",
            )
        with self._transaction() as connection:
            room = self._room_row(connection, code, mutation=True)
            self._check_version(room, expected_version)
            participant = self._participant_by_token(
                connection, room["code"], token
            )
            if room["status"] != "drafting":
                raise RequestError(
                    409,
                    "draft_not_active",
                    "Picks can only be repositioned before the room completes.",
                )
            settings = _json_loads(room["settings_json"], {})
            slots = {slot.id: slot for slot in FORMATIONS[settings["formation"]]}
            source_slot = slots.get(from_slot_id)
            target_slot = slots.get(to_slot_id)
            if not source_slot or not target_slot:
                raise RequestError(
                    400,
                    "invalid_slot",
                    "A source or destination slot is not in this formation.",
                )
            source_row = connection.execute(
                "SELECT * FROM picks WHERE participant_id = ? AND slot_id = ?",
                (participant["id"], from_slot_id),
            ).fetchone()
            if not source_row:
                raise RequestError(
                    404,
                    "pick_not_found",
                    "No drafted player occupies fromSlotId.",
                )
            source_payload = _json_loads(source_row["payload_json"], {})
            source_player = source_payload.get("player", {})
            if not _compatible(source_player, target_slot):
                raise RequestError(
                    409,
                    "player_ineligible",
                    "The drafted player cannot play in the destination slot.",
                )
            target_row = connection.execute(
                "SELECT * FROM picks WHERE participant_id = ? AND slot_id = ?",
                (participant["id"], to_slot_id),
            ).fetchone()
            if target_row and not swap:
                raise RequestError(
                    409,
                    "slot_occupied",
                    "Destination slot is occupied; pass swap=true to exchange players.",
                )
            target_payload: dict[str, Any] | None = None
            if target_row:
                target_payload = _json_loads(target_row["payload_json"], {})
                target_player = target_payload.get("player", {})
                if not _compatible(target_player, source_slot):
                    raise RequestError(
                        409,
                        "swap_ineligible",
                        "The destination player cannot play in the source slot.",
                    )
            source_payload["slotId"] = target_slot.id
            source_payload["slotLabel"] = target_slot.label
            now = self.clock()
            if target_row and target_payload is not None:
                target_payload["slotId"] = source_slot.id
                target_payload["slotLabel"] = source_slot.label
                temporary_slot = f"__swap__{uuid.uuid4().hex}"
                connection.execute(
                    "UPDATE picks SET slot_id = ? WHERE id = ?",
                    (temporary_slot, source_row["id"]),
                )
                connection.execute(
                    "UPDATE picks SET slot_id = ?, payload_json = ? WHERE id = ?",
                    (
                        source_slot.id,
                        _canonical_json(target_payload),
                        target_row["id"],
                    ),
                )
                connection.execute(
                    "UPDATE picks SET slot_id = ?, payload_json = ? WHERE id = ?",
                    (
                        target_slot.id,
                        _canonical_json(source_payload),
                        source_row["id"],
                    ),
                )
            else:
                connection.execute(
                    "UPDATE picks SET slot_id = ?, payload_json = ? WHERE id = ?",
                    (
                        target_slot.id,
                        _canonical_json(source_payload),
                        source_row["id"],
                    ),
                )
            connection.execute(
                "UPDATE participants SET updated_at = ? WHERE id = ?",
                (now, participant["id"]),
            )
            self._touch_room(connection, room["code"])
            room = self._room_row(connection, room["code"], mutation=False)
            participant = self._participant_by_token(
                connection, room["code"], token
            )
            return self._room_view(connection, room, participant)

    def health(self) -> dict[str, Any]:
        with self._transaction() as connection:
            now = self.clock()
            connection.execute(
                "UPDATE rooms SET status = 'expired', updated_at = ?, "
                "version = version + 1 "
                "WHERE status != 'expired' AND expires_at <= ?",
                (now, now),
            )
            counts = {
                row["status"]: row["count"]
                for row in connection.execute(
                    "SELECT status, COUNT(*) AS count FROM rooms GROUP BY status"
                ).fetchall()
            }
        return {
            "ok": True,
            "service": "hnl-room-api",
            "apiVersion": API_VERSION,
            "sqlite": True,
            "roomCounts": {status: counts.get(status, 0) for status in ROOM_STATUSES},
            "catalog": self.catalog.metadata,
        }


class RoomsAPIHandler(BaseHTTPRequestHandler):
    """Threaded JSON HTTP adapter around a shared :class:`RoomStore`."""

    server_version = "HNLRooms/" + API_VERSION
    protocol_version = "HTTP/1.1"

    @property
    def store(self) -> RoomStore:
        return self.server.room_store  # type: ignore[attr-defined]

    def _cors_origin(self) -> str | None:
        configured = os.getenv("HNL_ALLOWED_ORIGINS", "*").strip()
        origin = self.headers.get("Origin")
        if configured == "*":
            return "*"
        allowed = {item.strip() for item in configured.split(",") if item.strip()}
        if origin in allowed:
            return origin
        return None

    def _send(
        self,
        status: int,
        payload: Any | None,
        *,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        body = (
            b""
            if payload is None
            else json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        self.send_response(status)
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            if origin != "*":
                self.send_header("Vary", "Origin")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Authorization, Content-Type, X-Participant-Token",
        )
        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS",
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if payload is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _error(self, error: RequestError) -> None:
        payload: dict[str, Any] = {
            "error": {
                "code": error.code,
                "message": error.message,
            }
        }
        if error.details:
            payload["error"]["details"] = error.details
        self._send(error.status, payload)

    def _token(self, payload: Mapping[str, Any] | None = None) -> str | None:
        authorization = self.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        header_token = self.headers.get("X-Participant-Token")
        if header_token:
            return header_token.strip()
        if payload:
            value = payload.get("participantToken")
            return value if isinstance(value, str) else None
        return None

    def _read_payload(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            return {}
        try:
            length = int(raw_length)
        except ValueError as error:
            raise RequestError(
                400, "invalid_content_length", "Invalid Content-Length."
            ) from error
        limit = int(
            os.getenv("HNL_MAX_BODY_BYTES", str(DEFAULT_MAX_BODY_BYTES))
        )
        if length < 0 or length > limit:
            raise RequestError(413, "payload_too_large", "Request body is too large.")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RequestError(400, "invalid_json", "Request body is not valid JSON.") from error
        if not isinstance(payload, dict):
            raise RequestError(400, "invalid_payload", "JSON object required.")
        return payload

    @staticmethod
    def _route_parts(path: str) -> list[str]:
        return [item for item in path.split("/") if item]

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send(HTTPStatus.NO_CONTENT, None)

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urlsplit(self.path)
            parts = self._route_parts(parsed.path)
            if parts == ["health"]:
                self._send(200, self.store.health())
                return
            if parts == ["catalog"]:
                query = parse_qs(parsed.query)
                include_players = query.get("includePlayers", ["false"])[0].lower() in {
                    "1",
                    "true",
                    "yes",
                }
                self._send(
                    200,
                    self.store.catalog.public_inventory(include_players),
                )
                return
            if len(parts) == 2 and parts[0] == "rooms":
                query = parse_qs(parsed.query)
                token = self._token() or query.get("token", [None])[0]
                self._send(200, self.store.get_room(parts[1], token))
                return
            raise RequestError(404, "route_not_found", "Route was not found.")
        except RequestError as error:
            self._error(error)
        except Exception:
            self.log_error("Unhandled GET error")
            self._send(
                500,
                {"error": {"code": "internal_error", "message": "Internal server error."}},
            )

    def do_POST(self) -> None:  # noqa: N802
        try:
            parsed = urlsplit(self.path)
            parts = self._route_parts(parsed.path)
            payload = self._read_payload()
            if parts == ["rooms"]:
                self._send(
                    HTTPStatus.CREATED,
                    self.store.create_room(payload),
                )
                return
            if len(parts) == 3 and parts[0] == "rooms":
                code, action = parts[1], parts[2]
                if action == "join":
                    self._send(
                        HTTPStatus.CREATED,
                        self.store.join_room(code, payload),
                    )
                    return
                token = self._token(payload)
                if action == "start":
                    self._send(
                        200,
                        self.store.start_room(
                            code,
                            token or "",
                            payload.get("expectedVersion"),
                        ),
                    )
                    return
                if action == "spin":
                    self._send(
                        200,
                        self.store.spin(
                            code,
                            token or "",
                            payload.get("expectedVersion"),
                            payload.get("expectedTurn"),
                            reroll=bool(payload.get("reroll", False)),
                            slot_id=payload.get("slotId"),
                        ),
                    )
                    return
                if action == "pick":
                    self._send(
                        200,
                        self.store.pick(
                            code,
                            token or "",
                            payload.get("expectedVersion"),
                            payload.get("expectedTurn"),
                            payload.get("playerSeasonId"),
                            payload.get("slotId"),
                        ),
                    )
                    return
                if action == "move":
                    self._send(
                        200,
                        self.store.move(
                            code,
                            token or "",
                            payload.get("expectedVersion"),
                            payload.get("fromSlotId"),
                            payload.get("toSlotId"),
                            swap=bool(payload.get("swap", False)),
                        ),
                    )
                    return
            raise RequestError(404, "route_not_found", "Route was not found.")
        except RequestError as error:
            self._error(error)
        except Exception:
            self.log_error("Unhandled POST error")
            self._send(
                500,
                {"error": {"code": "internal_error", "message": "Internal server error."}},
            )

    def log_message(self, format: str, *args: Any) -> None:
        if os.getenv("HNL_QUIET", "").lower() not in {"1", "true", "yes"}:
            super().log_message(format, *args)


class RoomsHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        room_store: RoomStore,
    ) -> None:
        self.room_store = room_store
        super().__init__(server_address, RoomsAPIHandler)


def make_server(
    store: RoomStore,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> RoomsHTTPServer:
    return RoomsHTTPServer((host, port), store)


def main() -> None:
    host = os.getenv("HNL_API_HOST", DEFAULT_HOST)
    port = int(
        os.getenv(
            "HNL_ROOMS_PORT",
            os.getenv("HNL_API_PORT", os.getenv("PORT", str(DEFAULT_PORT))),
        )
    )
    database_path = os.getenv(
        "HNL_ROOMS_DB",
        str(Path("data") / "rooms.sqlite3"),
    )
    catalog_path = os.getenv("HNL_CATALOG_PATH")
    ttl = int(
        os.getenv("HNL_ROOM_TTL_SECONDS", str(DEFAULT_ROOM_TTL_SECONDS))
    )
    catalog = Catalog.load(catalog_path)
    store = RoomStore(database_path, catalog, room_ttl_seconds=ttl)
    server = make_server(store, host, port)
    print(
        f"HNL room API {API_VERSION} listening on http://{host}:{port} "
        f"with {catalog.metadata['clubSeasonCount']} club-seasons "
        f"from {catalog.metadata['sourcePath']}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
