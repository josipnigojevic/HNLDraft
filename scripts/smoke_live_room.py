#!/usr/bin/env python3
"""Exercise a complete two-manager live room through the public HTTP API."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


BASE_URL = os.getenv("HNL_SMOKE_API_URL", "http://localhost:8002").rstrip("/")
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    payload = json.dumps(body).encode() if body is not None else None
    headers = {
        "Accept": "application/json",
        "Origin": "http://localhost:3001",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with OPENER.open(
        urllib.request.Request(
            f"{BASE_URL}{path}",
            data=payload,
            method=method,
            headers=headers,
        ),
        timeout=10,
    ) as response:
        return json.load(response)


def participant(room: dict[str, Any], participant_id: str) -> dict[str, Any]:
    return next(
        item for item in room["participants"] if item["id"] == participant_id
    )


def spin_and_pick(
    room: dict[str, Any],
    room_code: str,
    participant_id: str,
    token: str,
) -> dict[str, Any]:
    own = participant(room, participant_id)
    room = request(
        f"/rooms/{room_code}/spin",
        method="POST",
        token=token,
        body={
            "expectedVersion": room["version"],
            "expectedTurn": own["turn"],
            "reroll": False,
        },
    )
    own = participant(room, participant_id)
    player = next(
        item
        for item in own["currentSpin"]["players"]
        if item["available"] and item["eligibleSlotIds"]
    )
    return request(
        f"/rooms/{room_code}/pick",
        method="POST",
        token=token,
        body={
            "expectedVersion": room["version"],
            "expectedTurn": own["turn"],
            "playerSeasonId": player["id"],
            "slotId": player["eligibleSlotIds"][0],
        },
    )


def validate_full_season(manager: dict[str, Any]) -> None:
    result = manager["result"]
    matches = result.get("matches", [])
    if len(matches) != 36:
        raise AssertionError(f"Expected 36 ordered fixtures, got {len(matches)}.")
    if [match["matchweek"] for match in matches] != list(range(1, 37)):
        raise AssertionError("Matchweeks were not ordered from 1 through 36.")

    final_running = matches[-1]["running"]
    aggregate_fields = {
        "played": "played",
        "wins": "wins",
        "draws": "draws",
        "losses": "losses",
        "points": "points",
        "goalsFor": "goalsFor",
        "goalsAgainst": "goalsAgainst",
        "goalDifference": "goalDifference",
    }
    for running_field, result_field in aggregate_fields.items():
        if final_running[running_field] != result[result_field]:
            raise AssertionError(
                f"Running {running_field} did not match final {result_field}."
            )

    if len(result.get("leagueTable", [])) != 10:
        raise AssertionError("The final HNL table did not contain ten teams.")
    if len(result.get("playerStats", [])) != len(manager["picks"]):
        raise AssertionError("Player season totals did not cover the drafted XI.")

    drafted_ids = {pick["player"]["id"] for pick in manager["picks"]}
    scorer_ids = {
        event["playerId"]
        for match in matches
        for event in match.get("scorers", [])
        if event.get("playerId")
    }
    if not scorer_ids.issubset(drafted_ids):
        raise AssertionError("A goal was attributed outside the drafted squad.")


def main() -> None:
    created = request(
        "/rooms",
        method="POST",
        body={
            "mode": "live",
            "name": "Docker Host",
            "seed": 3802026,
            "settings": {
                "formation": "4-3-3",
                "difficulty": "normal",
                "draftMode": "squad-first",
                "ratingsMode": "season",
                "seasonStart": 2020,
                "seasonEnd": 2025,
                "maxPlayers": 2,
                "targetPicks": 1,
            },
        },
    )
    room_code = created["roomCode"]
    host_id = created["participantId"]
    host_token = created["participantToken"]

    joined = request(
        f"/rooms/{room_code}/join",
        method="POST",
        body={"name": "Docker Guest"},
    )
    guest_id = joined["participantId"]
    guest_token = joined["participantToken"]
    room = request(
        f"/rooms/{room_code}/start",
        method="POST",
        token=host_token,
        body={"expectedVersion": joined["room"]["version"]},
    )

    room = spin_and_pick(room, room_code, host_id, host_token)
    guest_view = request(f"/rooms/{room_code}", token=guest_token)
    host_view = participant(guest_view, host_id)
    if host_view.get("currentSpin") and not host_view["currentSpin"].get(
        "squadHidden"
    ):
        raise AssertionError("Another manager's active squad was not private.")

    room = spin_and_pick(room, room_code, guest_id, guest_token)
    if room["status"] != "complete":
        raise AssertionError(f"Expected a complete room, got {room['status']!r}.")
    if any(item["result"]["played"] != 36 for item in room["participants"]):
        raise AssertionError("Completed manager result did not contain 36 matches.")

    solo = request(
        "/rooms",
        method="POST",
        body={
            "mode": "solo",
            "name": "Full XI",
            "seed": 380,
            "settings": {
                "formation": "4-3-3",
                "difficulty": "normal",
                "draftMode": "squad-first",
                "ratingsMode": "season",
                "seasonStart": 1995,
                "seasonEnd": 2025,
                "targetPicks": 11,
            },
        },
    )
    solo_code = solo["roomCode"]
    solo_id = solo["participantId"]
    solo_token = solo["participantToken"]
    solo_room = request(
        f"/rooms/{solo_code}/start",
        method="POST",
        token=solo_token,
        body={"expectedVersion": solo["room"]["version"]},
    )
    for _ in range(11):
        solo_room = spin_and_pick(solo_room, solo_code, solo_id, solo_token)
    solo_manager = participant(solo_room, solo_id)
    if solo_room["status"] != "complete" or len(solo_manager["picks"]) != 11:
        raise AssertionError("The full eleven-player solo flow did not complete.")
    validate_full_season(solo_manager)

    print(
        json.dumps(
            {
                "ok": True,
                "live": {
                    "roomCode": room_code,
                    "status": room["status"],
                    "version": room["version"],
                    "participants": [
                        {
                            "name": item["name"],
                            "picks": len(item["picks"]),
                            "points": item["result"]["points"],
                        }
                        for item in room["participants"]
                    ],
                },
                "solo": {
                    "roomCode": solo_code,
                    "status": solo_room["status"],
                    "picks": len(solo_manager["picks"]),
                    "points": solo_manager["result"]["points"],
                },
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
