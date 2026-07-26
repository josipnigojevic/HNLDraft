#!/usr/bin/env python3
"""Exercise account cookies and a saved season through the public HTTP API."""

from __future__ import annotations

import http.cookiejar
import json
import os
import secrets
import urllib.error
import urllib.request
from typing import Any


BASE_URL = os.getenv("HNL_SMOKE_API_URL", "http://localhost:8002").rstrip("/")
ORIGIN = os.getenv("HNL_SMOKE_ORIGIN", "http://localhost:3001")
COOKIE_JAR = http.cookiejar.CookieJar()
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPCookieProcessor(COOKIE_JAR),
)


def request(
    path: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    participant_token: str | None = None,
) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json", "Origin": ORIGIN}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if participant_token:
        headers["Authorization"] = f"Bearer {participant_token}"
    with OPENER.open(
        urllib.request.Request(
            f"{BASE_URL}{path}",
            data=payload,
            method=method,
            headers=headers,
        ),
        timeout=20,
    ) as response:
        return json.load(response)


def own_participant(room: dict[str, Any], participant_id: str) -> dict[str, Any]:
    return next(
        item for item in room["participants"] if item["id"] == participant_id
    )


def main() -> None:
    username = f"smoke{secrets.token_hex(4)}"
    password = "account smoke passphrase 2026"
    registered = request(
        "/account/register",
        method="POST",
        body={
            "username": username,
            "email": f"{username}@example.invalid",
            "password": password,
        },
    )
    if registered["account"]["username"] != username or not COOKIE_JAR:
        raise AssertionError("Registration did not create an authenticated cookie.")

    me = request("/account/me")
    if me["account"]["username"] != username:
        raise AssertionError("The account cookie did not restore the signed-in user.")

    created = request(
        "/rooms",
        method="POST",
        body={
            "mode": "solo",
            "name": "Account Smoke",
            "seed": 3802026,
            "settings": {
                "formation": "4-3-3",
                "difficulty": "normal",
                "draftMode": "squad-first",
                "ratingsMode": "season",
                "seasonStart": 2020,
                "seasonEnd": 2025,
                "targetPicks": 1,
            },
        },
    )
    room_code = created["roomCode"]
    participant_id = created["participantId"]
    participant_token = created["participantToken"]
    room = request(
        f"/rooms/{room_code}/start",
        method="POST",
        participant_token=participant_token,
        body={"expectedVersion": created["room"]["version"]},
    )
    own = own_participant(room, participant_id)
    room = request(
        f"/rooms/{room_code}/spin",
        method="POST",
        participant_token=participant_token,
        body={
            "expectedVersion": room["version"],
            "expectedTurn": own["turn"],
        },
    )
    own = own_participant(room, participant_id)
    player = next(
        item
        for item in own["currentSpin"]["players"]
        if item["available"] and item["eligibleSlotIds"]
    )
    room = request(
        f"/rooms/{room_code}/pick",
        method="POST",
        participant_token=participant_token,
        body={
            "expectedVersion": room["version"],
            "expectedTurn": own["turn"],
            "playerSeasonId": player["id"],
            "slotId": player["eligibleSlotIds"][0],
        },
    )
    if room["status"] != "complete":
        raise AssertionError("The authenticated smoke season did not complete.")

    history = request("/account/history")
    if history["total"] != 1 or len(history["seasons"]) != 1:
        raise AssertionError("The completed season was not saved exactly once.")
    season = request(f"/account/history/{history['seasons'][0]['id']}")["season"]
    if season["roomCode"] != room_code or len(season["picks"]) != 1:
        raise AssertionError("The private season detail was incomplete.")

    public = request(f"/profiles/{username}")["profile"]
    if public["stats"]["seasonsPlayed"] != 1:
        raise AssertionError("The public aggregate profile was not updated.")
    if "email" in public or public["recentSeasons"][0].get("roomCode"):
        raise AssertionError("The public profile leaked private account data.")

    request("/account/logout", method="POST", body={})
    try:
        request("/account/me")
    except urllib.error.HTTPError as error:
        if error.code != 401:
            raise
    else:
        raise AssertionError("Logout did not invalidate the account session.")

    print(
        json.dumps(
            {
                "ok": True,
                "username": username,
                "roomCode": room_code,
                "historyEntries": history["total"],
                "points": history["seasons"][0]["points"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
