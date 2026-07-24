#!/usr/bin/env python3
"""Small standard-library HTTP API for the deterministic HNL simulator."""

from __future__ import annotations

import inspect
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlsplit

import sim_engine


API_VERSION = "1.0.0"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_MAX_BODY_BYTES = 1_000_000


class RequestError(ValueError):
    """An expected client error with an HTTP status and stable error code."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _extract_draft(payload: dict[str, Any]) -> tuple[Any, list[Any] | None]:
    nested = payload.get("draft")
    if nested is not None and not isinstance(nested, dict):
        raise RequestError(400, "invalid_draft", "'draft' must be an object.")
    nested = nested or {}

    team = payload.get(
        "drafted_team",
        payload.get("team", nested.get("team")),
    )
    players = payload.get(
        "drafted_players",
        payload.get("players", nested.get("players")),
    )
    if team is not None and not isinstance(team, (str, dict)):
        raise RequestError(
            400,
            "invalid_drafted_team",
            "Drafted team must be a string or object.",
        )
    if players is not None and not isinstance(players, list):
        raise RequestError(
            400,
            "invalid_drafted_players",
            "Drafted players must be an array.",
        )
    return team, players


def _draft_team_from_payload(
    drafted_team: Any,
    drafted_players: list[Any] | None,
) -> sim_engine.Team | None:
    """Validate the browser draft and convert it to the engine dataclasses."""
    if not isinstance(drafted_team, dict):
        return None

    def numeric(name: str, default: float | None = None) -> float:
        value = drafted_team.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RequestError(
                400,
                "invalid_team_rating",
                f"Drafted team field '{name}' must be numeric.",
            )
        parsed = float(value)
        if not 0 <= parsed <= 150:
            raise RequestError(
                400,
                "invalid_team_rating",
                f"Drafted team field '{name}' must be between 0 and 150.",
            )
        return parsed

    position_fit_value = drafted_team.get(
        "position_fit",
        drafted_team.get("positionFit", 1.0),
    )
    if isinstance(position_fit_value, bool) or not isinstance(
        position_fit_value, (int, float)
    ):
        raise RequestError(
            400,
            "invalid_position_fit",
            "Drafted team field 'positionFit' must be numeric.",
        )
    position_fit = float(position_fit_value)
    if not 0.5 <= position_fit <= 1.0:
        raise RequestError(
            400,
            "invalid_position_fit",
            "Drafted team field 'positionFit' must be between 0.5 and 1.",
        )

    player_payloads = drafted_players
    if player_payloads is None:
        nested_players = drafted_team.get("players", [])
        if not isinstance(nested_players, list):
            raise RequestError(
                400,
                "invalid_drafted_players",
                "Drafted team field 'players' must be an array.",
            )
        player_payloads = nested_players

    players: list[sim_engine.Player] = []
    for index, item in enumerate(player_payloads):
        if not isinstance(item, dict):
            raise RequestError(
                400,
                "invalid_drafted_player",
                f"Drafted player {index + 1} must be an object.",
            )
        name = item.get("name")
        position = item.get("position")
        weight = item.get("scoring_weight", item.get("scoringWeight", 1.0))
        if not isinstance(name, str) or not name.strip():
            raise RequestError(
                400,
                "invalid_drafted_player",
                f"Drafted player {index + 1} needs a name.",
            )
        if not isinstance(position, str) or not position.strip():
            raise RequestError(
                400,
                "invalid_drafted_player",
                f"Drafted player {index + 1} needs a position.",
            )
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise RequestError(
                400,
                "invalid_drafted_player",
                f"Drafted player {index + 1} scoringWeight must be numeric.",
            )
        players.append(
            sim_engine.Player(
                name=name.strip(),
                position=position.strip(),
                scoring_weight=max(0.001, float(weight)),
            )
        )

    if players and len(players) != 11:
        raise RequestError(
            400,
            "invalid_squad_size",
            "A drafted simulation requires exactly 11 players.",
        )

    return sim_engine.Team(
        name=getattr(sim_engine, "USER_TEAM", "Korisnikov XI"),
        attack=numeric("attack"),
        midfield=numeric("midfield"),
        defence=numeric("defence"),
        goalkeeper=numeric("goalkeeper"),
        bench=numeric("bench", 75.0),
        position_fit=position_fit,
        players=tuple(players),
    )


def _supported_call(
    function: Callable[..., Any],
    seed: int,
    drafted_team: Any,
    drafted_players: list[Any] | None,
    extra_candidates: dict[str, Any] | None = None,
) -> tuple[Any, list[str], list[str]]:
    """Call the current or a future extended engine signature safely.

    The current reference engine accepts only ``seed`` for a season. If a
    future version adds draft parameters, this adapter forwards them by common
    parameter names without requiring an API-server rewrite.
    """

    signature = inspect.signature(function)
    parameters = signature.parameters
    accepts_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    )
    kwargs: dict[str, Any] = {}
    applied: list[str] = []
    warnings: list[str] = []

    if "seed" in parameters or accepts_kwargs:
        kwargs["seed"] = seed
    else:
        raise RuntimeError(
            f"{function.__name__} does not expose a supported 'seed' parameter."
        )

    def forward(value: Any, names: tuple[str, ...], label: str) -> bool:
        if value is None:
            return False
        for name in names:
            if name in parameters:
                kwargs[name] = value
                applied.append(label)
                return True
        if accepts_kwargs:
            kwargs[names[0]] = value
            applied.append(label)
            return True
        return False

    draft_object = {
        "team": drafted_team,
        "players": drafted_players,
    }
    has_draft = drafted_team is not None or drafted_players is not None
    if has_draft and "draft" in parameters:
        kwargs["draft"] = draft_object
        applied.append("draft")
    elif has_draft and accepts_kwargs:
        kwargs["drafted_team"] = drafted_team
        kwargs["drafted_players"] = drafted_players
        applied.extend(["drafted_team", "drafted_players"])
    else:
        team_applied = forward(
            drafted_team,
            ("drafted_team", "draft_team", "team"),
            "drafted_team",
        )
        players_applied = forward(
            drafted_players,
            ("drafted_players", "draft_players", "players"),
            "drafted_players",
        )
        if has_draft and not (team_applied or players_applied):
            warnings.append(
                "Draft payload was accepted but not applied because this "
                "sim_engine version exposes only simulate_season(seed)."
            )

    for name, value in (extra_candidates or {}).items():
        if name in parameters or accepts_kwargs:
            kwargs[name] = value
            applied.append(name)

    return function(**kwargs), sorted(set(applied)), warnings


def simulate(payload: dict[str, Any]) -> dict[str, Any]:
    seed = payload.get("seed", getattr(sim_engine, "DEFAULT_SEED", 0))
    if not _is_int(seed):
        raise RequestError(400, "invalid_seed", "'seed' must be an integer.")

    mode = payload.get("mode", "season")
    if mode not in {"season", "challenge", "challenge38"}:
        raise RequestError(
            400,
            "invalid_mode",
            "'mode' must be 'season', 'challenge', or 'challenge38'.",
        )
    drafted_team, drafted_players = _extract_draft(payload)

    if mode == "season":
        custom_team = _draft_team_from_payload(drafted_team, drafted_players)
        if custom_team is not None:
            result = sim_engine.simulate_season(seed=seed, user_team=custom_team)
            applied = ["user_team", "drafted_players"]
            warnings = []
        else:
            result, applied, warnings = _supported_call(
                sim_engine.simulate_season,
                seed,
                drafted_team,
                drafted_players,
            )
    else:
        if not hasattr(sim_engine, "simulate_challenge"):
            raise RequestError(
                501,
                "challenge_unavailable",
                "This sim_engine version does not expose simulate_challenge.",
            )
        matches = payload.get("matches", 38)
        boost = payload.get("showcase_boost", 40.0)
        if not _is_int(matches) or not 1 <= matches <= 1000:
            raise RequestError(
                400,
                "invalid_matches",
                "'matches' must be an integer from 1 through 1000.",
            )
        if isinstance(boost, bool) or not isinstance(boost, (int, float)):
            raise RequestError(
                400,
                "invalid_showcase_boost",
                "'showcase_boost' must be numeric.",
            )
        result, applied, warnings = _supported_call(
            sim_engine.simulate_challenge,
            seed,
            drafted_team,
            drafted_players,
            {
                "matches_count": matches,
                "showcase_boost": float(boost),
            },
        )

    if not isinstance(result, dict):
        result = {"result": result}
    response = dict(result)
    response["_api"] = {
        "version": API_VERSION,
        "mode_requested": mode,
        "draft_received": drafted_team is not None or drafted_players is not None,
        "draft_applied": any(name.startswith("draft") for name in applied),
        "forwarded_parameters": applied,
        "warnings": warnings,
    }
    return response


def _localhost_origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    configured = {
        item.strip()
        for item in os.getenv("API_CORS_ORIGINS", "").split(",")
        if item.strip()
    }
    if origin in configured or "*" in configured:
        return True
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    )


class ApiHandler(BaseHTTPRequestHandler):
    server_version = f"HNL38API/{API_VERSION}"

    def _cors_headers(self) -> None:
        origin = self.headers.get("Origin")
        if _localhost_origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")

    def _write_json(
        self,
        status: int,
        payload: dict[str, Any],
        *,
        include_body: bool = True,
    ) -> None:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded) if include_body else 0))
        self.end_headers()
        if include_body:
            self.wfile.write(encoded)

    def _error(self, error: RequestError) -> None:
        self._write_json(
            error.status,
            {"error": {"code": error.code, "message": error.message}},
        )

    def _read_json_object(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise RequestError(
                411,
                "content_length_required",
                "Content-Length is required.",
            )
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise RequestError(
                400,
                "invalid_content_length",
                "Content-Length must be an integer.",
            ) from exc
        maximum = int(
            os.getenv("API_MAX_BODY_BYTES", str(DEFAULT_MAX_BODY_BYTES))
        )
        if length < 0 or length > maximum:
            raise RequestError(
                413,
                "payload_too_large",
                f"Request body must not exceed {maximum} bytes.",
            )
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise RequestError(
                400,
                "invalid_json",
                "Request body must be valid UTF-8 JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise RequestError(
                400,
                "invalid_payload",
                "Request JSON must be an object.",
            )
        return payload

    def do_OPTIONS(self) -> None:  # noqa: N802
        if self.path not in {"/health", "/simulate", "/challenge"}:
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {"error": {"code": "not_found", "message": "Route not found."}},
            )
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._write_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "api_version": API_VERSION,
                    "engine_version": getattr(
                        sim_engine, "ENGINE_VERSION", "unknown"
                    ),
                },
            )
            return
        self._write_json(
            HTTPStatus.NOT_FOUND,
            {"error": {"code": "not_found", "message": "Route not found."}},
        )

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/simulate", "/challenge"}:
            self._write_json(
                HTTPStatus.NOT_FOUND,
                {"error": {"code": "not_found", "message": "Route not found."}},
            )
            return
        try:
            payload = self._read_json_object()
            if self.path == "/challenge":
                payload["mode"] = "challenge38"
                if "matchesCount" in payload and "matches" not in payload:
                    payload["matches"] = payload["matchesCount"]
                if (
                    "showcaseBoost" in payload
                    and "showcase_boost" not in payload
                ):
                    payload["showcase_boost"] = payload["showcaseBoost"]
            result = simulate(payload)
        except RequestError as error:
            self._error(error)
            return
        except Exception as error:  # keep server alive; details stay server-side
            self.log_error("simulation failed: %s", error)
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "error": {
                        "code": "simulation_failed",
                        "message": "The simulation could not be completed.",
                    }
                },
            )
            return
        self._write_json(HTTPStatus.OK, result)


def main() -> int:
    host = os.getenv("API_HOST", DEFAULT_HOST)
    try:
        port = int(os.getenv("API_PORT", str(DEFAULT_PORT)))
    except ValueError as exc:
        raise SystemExit("API_PORT must be an integer.") from exc
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(
        json.dumps(
            {
                "status": "listening",
                "host": host,
                "port": port,
                "api_version": API_VERSION,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
