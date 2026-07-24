#!/usr/bin/env python3
"""Deterministic reference engine for the Croatian HNL draft prototype.

The model is intentionally transparent. Official HNS results determine the
home/away scoring intercepts; player/team ratings and all dynamic effects are
editorial prototype inputs until they are fitted on licensed historical data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Sequence


ENGINE_VERSION = "0.1.0"
DEFAULT_SEED = 38_020_260_724
USER_TEAM = "Korisnikov XI"


@dataclass(frozen=True)
class Player:
    name: str
    position: str
    scoring_weight: float


@dataclass(frozen=True)
class Team:
    name: str
    attack: float
    midfield: float
    defence: float
    goalkeeper: float
    bench: float
    position_fit: float = 1.0
    cohesion: float = 0.0
    players: tuple[Player, ...] = ()

    @property
    def average_rating(self) -> float:
        return (
            self.attack + self.midfield + self.defence + self.goalkeeper
        ) / 4.0


@dataclass
class TeamState:
    fatigue: float = 0.0
    injury_remaining: list[int] = field(default_factory=list)


@dataclass
class MatchResult:
    round: int
    home: str
    away: str
    home_goals: int
    away_goals: int
    home_xg: float
    away_xg: float
    home_yellow: int
    away_yellow: int
    home_red: int
    away_red: int
    home_red_minute: int | None
    away_red_minute: int | None
    home_substitutions: int
    away_substitutions: int
    home_substitution_windows: int
    away_substitution_windows: int
    home_unavailable: int
    away_unavailable: int
    home_fatigue: float
    away_fatigue: float
    scorers: list[dict[str, Any]]


MODEL_CONFIG: dict[str, float] = {
    # Completed 2025/26 HNS Semafor: 263/180 and 216/180.
    "mu_home": 1.4611,
    "mu_away": 1.2000,
    "beta_attack": 0.13,
    "beta_defence": 0.11,
    "beta_cohesion": 0.04,
    "ovr_points_per_strength_unit": 10.0,
    "fatigue_ovr_deduction_at_1": 4.0,
    "new_injury_probability": 0.045,
    "in_match_injury_probability": 0.055,
    "red_card_rate_per_team": 0.1028,
    "yellow_card_rate_per_team": 2.71945,
    "lambda_min": 0.05,
    "lambda_max": 6.0,
}


def user_players() -> tuple[Player, ...]:
    """Illustrative player-season cards; weights allocate simulated goals."""
    return (
        Player("Dominik Livaković (Dinamo 2020/21)", "GK", 0.03),
        Player("Darijo Srna (Hajduk 2002/03)", "RB", 0.70),
        Player("Josip Šimunić (Dinamo 2012/13)", "CB", 0.35),
        Player("Joško Gvardiol (Dinamo 2020/21)", "CB", 0.65),
        Player("Danijel Pranjić (Osijek 2003/04)", "LB", 0.55),
        Player("Marcelo Brozović (Dinamo 2013/14)", "DM", 1.25),
        Player("Luka Modrić (Dinamo 2007/08)", "CM", 2.05),
        Player("Dani Olmo (Dinamo 2018/19)", "AM", 2.55),
        Player("Marko Pjaca (Dinamo 2015/16)", "RW", 3.20),
        Player("Mario Mandžukić (Dinamo 2008/09)", "ST", 5.10),
        Player("Mislav Oršić (Dinamo 2020/21)", "LW", 4.35),
    )


def abstract_players(team_name: str) -> tuple[Player, ...]:
    """Role labels avoid pretending that a moving 2026/27 roster is frozen."""
    return (
        Player(f"{team_name} — CF", "ST", 4.0),
        Player(f"{team_name} — LW", "LW", 2.5),
        Player(f"{team_name} — RW", "RW", 2.5),
        Player(f"{team_name} — AM", "AM", 1.8),
        Player(f"{team_name} — ostali", "MIX", 3.2),
    )


def make_team(
    name: str,
    attack: float,
    midfield: float,
    defence: float,
    goalkeeper: float,
    bench: float,
) -> Team:
    return Team(
        name=name,
        attack=attack,
        midfield=midfield,
        defence=defence,
        goalkeeper=goalkeeper,
        bench=bench,
        players=abstract_players(name),
    )


def default_teams() -> list[Team]:
    """One drafted XI plus the other nine official 2026/27 participants.

    The component ratings are disclosed editorial inputs, not HNS ratings.
    Korisnikov XI occupies the Dinamo slot so the league remains ten teams.
    """
    return [
        Team(
            USER_TEAM,
            attack=92.0,
            midfield=90.0,
            defence=88.5,
            goalkeeper=88.0,
            bench=75.0,
            position_fit=0.985,
            players=user_players(),
        ),
        make_team("HNK Hajduk", 80.5, 79.0, 78.0, 79.5, 73.0),
        make_team("HNK Rijeka", 79.0, 78.5, 79.0, 78.0, 72.5),
        make_team("NK Varaždin", 75.0, 74.5, 76.0, 74.0, 69.5),
        make_team("NK Istra 1961", 74.0, 75.0, 75.5, 74.0, 69.5),
        make_team("NK Slaven Belupo", 73.5, 73.0, 72.5, 72.0, 68.5),
        make_team("NK Osijek", 72.5, 74.0, 73.0, 74.0, 69.0),
        make_team("NK Lokomotiva", 73.5, 74.0, 71.5, 71.0, 68.0),
        make_team("HNK Gorica", 72.0, 72.5, 71.5, 72.0, 67.5),
        make_team("NK Rudeš", 68.0, 68.5, 67.5, 67.0, 64.0),
    ]


def derive_seed(master_seed: int, *labels: object) -> int:
    material = "|".join([str(master_seed), *(str(label) for label in labels)])
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def rng_for(master_seed: int, *labels: object) -> random.Random:
    return random.Random(derive_seed(master_seed, *labels))


def sample_poisson(rng: random.Random, lam: float) -> int:
    """Knuth sampler; lambda is capped at six by this prototype."""
    threshold = math.exp(-lam)
    product = 1.0
    count = 0
    while product > threshold:
        count += 1
        product *= rng.random()
    return count - 1


def first_leg_rounds(team_names: Sequence[str]) -> list[list[tuple[str, str]]]:
    """Berger/circle-style single round robin for an even number of teams."""
    if len(team_names) < 2 or len(team_names) % 2:
        raise ValueError("The HNL reference schedule requires an even team count.")
    rotating = list(team_names)
    rounds: list[list[tuple[str, str]]] = []
    for round_index in range(len(rotating) - 1):
        pairings: list[tuple[str, str]] = []
        half = len(rotating) // 2
        for pair_index in range(half):
            left = rotating[pair_index]
            right = rotating[-1 - pair_index]
            if pair_index == 0:
                home, away = (
                    (left, right) if round_index % 2 == 0 else (right, left)
                )
            elif (round_index + pair_index) % 2 == 0:
                home, away = left, right
            else:
                home, away = right, left
            pairings.append((home, away))
        rounds.append(pairings)
        rotating = [rotating[0], rotating[-1], *rotating[1:-1]]
    return rounds


def hnl_schedule(team_names: Sequence[str]) -> list[list[tuple[str, str]]]:
    """Four cycles: every pair meets twice at each ground (36 rounds for 10)."""
    first = first_leg_rounds(team_names)
    reverse = [[(away, home) for home, away in rnd] for rnd in first]
    return first + reverse + first + reverse


def prepare_team_for_match(
    team: Team,
    state: TeamState,
    event_rng: random.Random,
) -> dict[str, Any]:
    if event_rng.random() < MODEL_CONFIG["new_injury_probability"]:
        state.injury_remaining.append(event_rng.randint(1, 4))

    unavailable = len(state.injury_remaining)
    in_match_injury = (
        1 if event_rng.random() < MODEL_CONFIG["in_match_injury_probability"] else 0
    )
    if in_match_injury:
        state.injury_remaining.append(event_rng.randint(1, 3))

    substitutions = min(
        5,
        3 + int(state.fatigue >= 0.18) + in_match_injury,
    )
    substitution_windows = min(3, max(1, (substitutions + 1) // 2))

    replacement_gap = max(0.0, team.average_rating - team.bench)
    injury_penalty = min(8.0, unavailable * 0.25 * replacement_gap)
    fit_penalty = (1.0 - team.position_fit) * 8.0
    fatigue_after_subs = state.fatigue * (1.0 - 0.07 * substitutions)
    fatigue_penalty = (
        MODEL_CONFIG["fatigue_ovr_deduction_at_1"] * fatigue_after_subs
    )
    bench_delta = (team.bench - team.average_rating) * 0.012 * substitutions
    total_delta = -injury_penalty - fit_penalty - fatigue_penalty + bench_delta

    return {
        "attack": team.attack + total_delta,
        "midfield": team.midfield + total_delta,
        "defence": team.defence + total_delta,
        "goalkeeper": team.goalkeeper + total_delta,
        "unavailable": unavailable,
        "substitutions": substitutions,
        "substitution_windows": substitution_windows,
        "fatigue": state.fatigue,
    }


def attack_strength(effective: dict[str, Any]) -> float:
    rating = 0.58 * effective["attack"] + 0.42 * effective["midfield"]
    return (rating - 75.0) / MODEL_CONFIG["ovr_points_per_strength_unit"]


def defence_strength(effective: dict[str, Any]) -> float:
    rating = 0.65 * effective["defence"] + 0.35 * effective["goalkeeper"]
    return (rating - 75.0) / MODEL_CONFIG["ovr_points_per_strength_unit"]


def clamp_lambda(value: float) -> float:
    return min(
        MODEL_CONFIG["lambda_max"],
        max(MODEL_CONFIG["lambda_min"], value),
    )


def red_card_adjustment(
    home_lambda: float,
    away_lambda: float,
    home_minute: int | None,
    away_minute: int | None,
) -> tuple[float, float]:
    if home_minute is not None:
        remaining = (90 - home_minute) / 90.0
        home_lambda *= math.exp(-0.45 * remaining)
        away_lambda *= math.exp(0.35 * remaining)
    if away_minute is not None:
        remaining = (90 - away_minute) / 90.0
        away_lambda *= math.exp(-0.45 * remaining)
        home_lambda *= math.exp(0.35 * remaining)
    return clamp_lambda(home_lambda), clamp_lambda(away_lambda)


def choose_scorers(
    team: Team,
    goals: int,
    rng: random.Random,
    side: str,
) -> list[dict[str, Any]]:
    players = team.players or abstract_players(team.name)
    weights = [max(0.001, player.scoring_weight) for player in players]
    events: list[dict[str, Any]] = []
    for _ in range(goals):
        player = rng.choices(players, weights=weights, k=1)[0]
        events.append(
            {
                "team": team.name,
                "side": side,
                "player": player.name,
                "minute": rng.randint(1, 90),
            }
        )
    return events


def update_post_match_state(state: TeamState, substitutions: int) -> None:
    state.injury_remaining = [
        matches - 1 for matches in state.injury_remaining if matches > 1
    ]
    load = 0.145 - 0.012 * substitutions
    state.fatigue = min(1.0, max(0.0, state.fatigue * 0.58 + load))


def simulate_match(
    master_seed: int,
    mode: str,
    round_number: int,
    match_number: int,
    home: Team,
    away: Team,
    states: dict[str, TeamState],
) -> MatchResult:
    event_rng = rng_for(
        master_seed, mode, "events", round_number, match_number, home.name, away.name
    )
    score_rng = rng_for(
        master_seed, mode, "score", round_number, match_number, home.name, away.name
    )
    scorer_rng = rng_for(
        master_seed, mode, "scorers", round_number, match_number, home.name, away.name
    )

    home_eff = prepare_team_for_match(home, states[home.name], event_rng)
    away_eff = prepare_team_for_match(away, states[away.name], event_rng)

    home_eta = (
        math.log(MODEL_CONFIG["mu_home"])
        + MODEL_CONFIG["beta_attack"] * attack_strength(home_eff)
        - MODEL_CONFIG["beta_defence"] * defence_strength(away_eff)
        + MODEL_CONFIG["beta_cohesion"] * (home.cohesion - away.cohesion)
    )
    away_eta = (
        math.log(MODEL_CONFIG["mu_away"])
        + MODEL_CONFIG["beta_attack"] * attack_strength(away_eff)
        - MODEL_CONFIG["beta_defence"] * defence_strength(home_eff)
        + MODEL_CONFIG["beta_cohesion"] * (away.cohesion - home.cohesion)
    )
    home_lambda = clamp_lambda(math.exp(home_eta))
    away_lambda = clamp_lambda(math.exp(away_eta))

    red_probability = 1.0 - math.exp(-MODEL_CONFIG["red_card_rate_per_team"])
    home_red = 1 if event_rng.random() < red_probability else 0
    away_red = 1 if event_rng.random() < red_probability else 0
    home_red_minute = event_rng.randint(15, 88) if home_red else None
    away_red_minute = event_rng.randint(15, 88) if away_red else None
    home_lambda, away_lambda = red_card_adjustment(
        home_lambda, away_lambda, home_red_minute, away_red_minute
    )

    home_goals = sample_poisson(score_rng, home_lambda)
    away_goals = sample_poisson(score_rng, away_lambda)
    home_yellow = sample_poisson(
        event_rng, MODEL_CONFIG["yellow_card_rate_per_team"]
    )
    away_yellow = sample_poisson(
        event_rng, MODEL_CONFIG["yellow_card_rate_per_team"]
    )
    scorers = choose_scorers(home, home_goals, scorer_rng, "home")
    scorers.extend(choose_scorers(away, away_goals, scorer_rng, "away"))
    scorers.sort(key=lambda event: (event["minute"], event["team"], event["player"]))

    update_post_match_state(
        states[home.name], int(home_eff["substitutions"])
    )
    update_post_match_state(
        states[away.name], int(away_eff["substitutions"])
    )

    return MatchResult(
        round=round_number,
        home=home.name,
        away=away.name,
        home_goals=home_goals,
        away_goals=away_goals,
        home_xg=round(home_lambda, 4),
        away_xg=round(away_lambda, 4),
        home_yellow=home_yellow,
        away_yellow=away_yellow,
        home_red=home_red,
        away_red=away_red,
        home_red_minute=home_red_minute,
        away_red_minute=away_red_minute,
        home_substitutions=int(home_eff["substitutions"]),
        away_substitutions=int(away_eff["substitutions"]),
        home_substitution_windows=int(home_eff["substitution_windows"]),
        away_substitution_windows=int(away_eff["substitution_windows"]),
        home_unavailable=int(home_eff["unavailable"]),
        away_unavailable=int(away_eff["unavailable"]),
        home_fatigue=round(float(home_eff["fatigue"]), 4),
        away_fatigue=round(float(away_eff["fatigue"]), 4),
        scorers=scorers,
    )


def blank_table(team_names: Iterable[str]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "team": name,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "gf": 0,
            "ga": 0,
            "gd": 0,
            "points": 0,
            "yellow": 0,
            "red": 0,
            "fair_play_minus": 0,
        }
        for name in team_names
    }


def add_match_to_table(
    table: dict[str, dict[str, Any]],
    match: MatchResult,
) -> None:
    home = table[match.home]
    away = table[match.away]
    home["played"] += 1
    away["played"] += 1
    home["gf"] += match.home_goals
    home["ga"] += match.away_goals
    away["gf"] += match.away_goals
    away["ga"] += match.home_goals
    home["yellow"] += match.home_yellow
    away["yellow"] += match.away_yellow
    home["red"] += match.home_red
    away["red"] += match.away_red
    if match.home_goals > match.away_goals:
        home["wins"] += 1
        away["losses"] += 1
        home["points"] += 3
    elif match.home_goals < match.away_goals:
        away["wins"] += 1
        home["losses"] += 1
        away["points"] += 3
    else:
        home["draws"] += 1
        away["draws"] += 1
        home["points"] += 1
        away["points"] += 1


def h2h_values(
    tied_names: set[str],
    matches: Sequence[MatchResult],
) -> dict[str, tuple[int, int]]:
    values = {name: [0, 0] for name in tied_names}
    for match in matches:
        if match.home not in tied_names or match.away not in tied_names:
            continue
        home = values[match.home]
        away = values[match.away]
        home[1] += match.home_goals - match.away_goals
        away[1] += match.away_goals - match.home_goals
        if match.home_goals > match.away_goals:
            home[0] += 3
        elif match.home_goals < match.away_goals:
            away[0] += 3
        else:
            home[0] += 1
            away[0] += 1
    return {name: (value[0], value[1]) for name, value in values.items()}


def rank_table(
    table: dict[str, dict[str, Any]],
    matches: Sequence[MatchResult],
    master_seed: int,
    critical_positions: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Apply HNS ordinary rules; critical groups add H2H/fair play/draw of lots.

    The caller must pass the UEFA positions for that season. This reference run
    treats only champion (1) and relegation (10) as critical.
    """
    critical_positions = critical_positions or {1, 10}
    rows = [dict(row) for row in table.values()]
    for row in rows:
        row["gd"] = row["gf"] - row["ga"]
        row["fair_play_minus"] = row["yellow"] + 3 * row["red"]

    point_groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        point_groups[int(row["points"])].append(row)

    ranked: list[dict[str, Any]] = []
    for points in sorted(point_groups, reverse=True):
        group = point_groups[points]
        first_position = len(ranked) + 1
        position_range = set(range(first_position, first_position + len(group)))
        critical = bool(position_range & critical_positions) and len(group) > 1
        if critical:
            names = {str(row["team"]) for row in group}
            h2h = h2h_values(names, matches)
            for row in group:
                row["h2h_points"], row["h2h_gd"] = h2h[str(row["team"])]
                row["lot"] = derive_seed(
                    master_seed, "draw_of_lots", points, row["team"]
                )
            group.sort(
                key=lambda row: (
                    -int(row["h2h_points"]),
                    -int(row["h2h_gd"]),
                    -int(row["gd"]),
                    int(row["fair_play_minus"]),
                    int(row["lot"]),
                )
            )
            for row in group:
                row["tiebreak"] = "critical:H2H pts,H2H GD,overall GD,fair play,lot"
        else:
            group.sort(
                key=lambda row: (
                    -int(row["gd"]),
                    -int(row["gf"]),
                    str(row["team"]),
                )
            )
            for row in group:
                row["tiebreak"] = "ordinary:overall GD,goals scored"
        ranked.extend(group)

    previous_key: tuple[int, int, int] | None = None
    shared_rank = 0
    for display_index, row in enumerate(ranked, start=1):
        ordinary_key = (
            int(row["points"]),
            int(row["gd"]),
            int(row["gf"]),
        )
        if ordinary_key != previous_key:
            shared_rank = display_index
        row["rank"] = display_index if row["tiebreak"].startswith("critical") else shared_rank
        row["display_order"] = display_index
        previous_key = ordinary_key
        row.pop("lot", None)
    return ranked


def scorer_table(matches: Sequence[MatchResult]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str]] = Counter()
    for match in matches:
        for event in match.scorers:
            counts[(str(event["player"]), str(event["team"]))] += 1
    rows = [
        {"player": player, "team": team, "goals": goals}
        for (player, team), goals in counts.items()
    ]
    rows.sort(key=lambda row: (-int(row["goals"]), str(row["player"])))
    return rows


def validate_season(
    schedule: Sequence[Sequence[tuple[str, str]]],
    matches: Sequence[MatchResult],
    table: Sequence[dict[str, Any]],
    scorers: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    appearances: Counter[str] = Counter()
    pair_counts: Counter[tuple[str, str]] = Counter()
    venue_counts: Counter[tuple[str, str]] = Counter()
    rounds_ok = True
    for round_pairings in schedule:
        seen: set[str] = set()
        for home, away in round_pairings:
            seen.update([home, away])
            appearances[home] += 1
            appearances[away] += 1
            pair_counts[tuple(sorted((home, away)))] += 1
            venue_counts[(home, away)] += 1
        if len(seen) != 2 * len(round_pairings):
            rounds_ok = False

    total_goals = sum(match.home_goals + match.away_goals for match in matches)
    scorer_goals = sum(int(row["goals"]) for row in scorers)
    gf = sum(int(row["gf"]) for row in table)
    ga = sum(int(row["ga"]) for row in table)
    points_rows_ok = all(
        int(row["played"])
        == int(row["wins"]) + int(row["draws"]) + int(row["losses"])
        and int(row["points"]) == 3 * int(row["wins"]) + int(row["draws"])
        and int(row["gd"]) == int(row["gf"]) - int(row["ga"])
        for row in table
    )
    return {
        "match_count": len(matches),
        "match_count_is_180": len(matches) == 180,
        "round_count": len(schedule),
        "round_count_is_36": len(schedule) == 36,
        "five_matches_and_each_team_once_per_round": rounds_ok
        and all(len(round_pairings) == 5 for round_pairings in schedule),
        "each_team_plays_36": all(count == 36 for count in appearances.values()),
        "each_pair_meets_four_times": all(
            count == 4 for count in pair_counts.values()
        )
        and len(pair_counts) == 45,
        "each_pair_has_two_home_each": all(
            venue_counts[(a, b)] == 2 and venue_counts[(b, a)] == 2
            for a, b in pair_counts
        ),
        "table_equations_hold": points_rows_ok,
        "sum_gf_equals_sum_ga": gf == ga,
        "sum_gf": gf,
        "sum_ga": ga,
        "total_goals": total_goals,
        "scorer_goals": scorer_goals,
        "scorers_reconcile": scorer_goals == total_goals,
    }


def canonical_hash(payload: dict[str, Any]) -> str:
    material = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def simulate_season(
    seed: int = DEFAULT_SEED,
    user_team: Team | None = None,
) -> dict[str, Any]:
    """Simulate the official 36-round format.

    Passing ``user_team`` replaces only the drafted XI slot. The default path
    remains byte-for-byte reproducible for the published research example.
    """
    base_teams = default_teams()
    teams = [user_team, *base_teams[1:]] if user_team is not None else base_teams
    if len({team.name for team in teams}) != len(teams):
        raise ValueError("Team names must be unique within a simulated season.")
    by_name = {team.name: team for team in teams}
    schedule = hnl_schedule([team.name for team in teams])
    states = {team.name: TeamState() for team in teams}
    matches: list[MatchResult] = []
    match_number = 0
    for round_number, pairings in enumerate(schedule, start=1):
        for home_name, away_name in pairings:
            match_number += 1
            matches.append(
                simulate_match(
                    seed,
                    "season",
                    round_number,
                    match_number,
                    by_name[home_name],
                    by_name[away_name],
                    states,
                )
            )

    table_map = blank_table(by_name)
    for match in matches:
        add_match_to_table(table_map, match)
    ranked = rank_table(table_map, matches, seed, {1, 10})
    scorers = scorer_table(matches)
    validation = validate_season(schedule, matches, ranked, scorers)

    payload: dict[str, Any] = {
        "engine_version": ENGINE_VERSION,
        "mode": "official_hnl_36_round",
        "seed": seed,
        "rules_season": "2026/27",
        "calibration_season": "2025/26",
        "model_config": dict(MODEL_CONFIG),
        "rating_disclosure": (
            "All team components and player OVRs are editorial prototype inputs; "
            "HNS supplies rules/results, not these ratings."
        ),
        "teams": [
            {
                "name": team.name,
                "attack": team.attack,
                "midfield": team.midfield,
                "defence": team.defence,
                "goalkeeper": team.goalkeeper,
                "bench": team.bench,
                "position_fit": team.position_fit,
            }
            for team in teams
        ],
        "table": ranked,
        "top_scorers": scorers,
        "matches": [asdict(match) for match in matches],
        "validation": validation,
    }
    payload["content_sha256"] = canonical_hash(payload)
    return payload


def simulate_challenge(
    seed: int,
    matches_count: int = 38,
    showcase_boost: float = 40.0,
) -> dict[str, Any]:
    """Non-canonical 38-match golden-path challenge.

    The disclosed boost intentionally makes a perfect result reachable for a
    regression/demo seed. It is not used in the official-format season.
    """
    base_teams = default_teams()
    user = base_teams[0]
    boosted_user = replace(
        user,
        attack=user.attack + showcase_boost,
        midfield=user.midfield + showcase_boost,
        defence=user.defence + showcase_boost,
        goalkeeper=user.goalkeeper + showcase_boost,
    )
    opponents = base_teams[1:]
    states = {team.name: TeamState() for team in [boosted_user, *opponents]}
    results: list[MatchResult] = []
    wins = draws = losses = goals_for = goals_against = 0
    for match_index in range(matches_count):
        opponent = opponents[match_index % len(opponents)]
        if match_index % 2 == 0:
            home, away = boosted_user, opponent
        else:
            home, away = opponent, boosted_user
        result = simulate_match(
            seed,
            "challenge38",
            match_index + 1,
            match_index + 1,
            home,
            away,
            states,
        )
        results.append(result)
        if result.home == USER_TEAM:
            user_goals, opponent_goals = result.home_goals, result.away_goals
        else:
            user_goals, opponent_goals = result.away_goals, result.home_goals
        goals_for += user_goals
        goals_against += opponent_goals
        if user_goals > opponent_goals:
            wins += 1
        elif user_goals == opponent_goals:
            draws += 1
        else:
            losses += 1

    payload: dict[str, Any] = {
        "engine_version": ENGINE_VERSION,
        "mode": "noncanonical_38_match_showcase",
        "seed": seed,
        "matches": matches_count,
        "showcase_boost": showcase_boost,
        "disclosure": (
            "The challenge adds a test-only component boost to Korisnikov XI. "
            "It is a golden-path/reproducibility demo, not an HNL forecast."
        ),
        "record": {
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "points": 3 * wins + draws,
            "goals_for": goals_for,
            "goals_against": goals_against,
            "goal_difference": goals_for - goals_against,
        },
        "perfect": wins == matches_count,
        "results": [asdict(result) for result in results],
    }
    payload["content_sha256"] = canonical_hash(payload)
    return payload


def find_perfect_seed(
    start_seed: int,
    max_seeds: int,
    matches_count: int,
    showcase_boost: float,
) -> dict[str, Any] | None:
    for seed in range(start_seed, start_seed + max_seeds):
        result = simulate_challenge(seed, matches_count, showcase_boost)
        if result["perfect"]:
            return result
    return None


def markdown_table(payload: dict[str, Any]) -> str:
    lines = [
        "| Pos | Club | P | W | D | L | GF | GA | GD | Pts |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["table"]:
        lines.append(
            "| {display_order} | {team} | {played} | {wins} | {draws} | "
            "{losses} | {gf} | {ga} | {gd:+d} | {points} |".format(**row)
        )
    return "\n".join(lines)


def render_season_markdown(payload: dict[str, Any]) -> str:
    validation = payload["validation"]
    lines = [
        "# Deterministic HNL example output",
        "",
        f"- Engine: `{payload['engine_version']}`",
        f"- Seed: `{payload['seed']}`",
        f"- Content SHA-256: `{payload['content_sha256']}`",
        f"- Total matches/goals: {validation['match_count']} / {validation['total_goals']}",
        "",
        "## Final table",
        "",
        markdown_table(payload),
        "",
        "## Top scorers",
        "",
        "| Rank | Player | Team | Goals |",
        "|---:|---|---|---:|",
    ]
    for index, row in enumerate(payload["top_scorers"][:15], start=1):
        lines.append(
            f"| {index} | {row['player']} | {row['team']} | {row['goals']} |"
        )
    lines.extend(
        [
            "",
            "## Validation",
            "",
            "| Check | Result |",
            "|---|---|",
        ]
    )
    for key, value in validation.items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.append("")
    return "\n".join(lines)


def render_challenge_markdown(payload: dict[str, Any]) -> str:
    record = payload["record"]
    lines = [
        "# Non-canonical 38-match showcase",
        "",
        f"- Seed: `{payload['seed']}`",
        f"- Disclosed test-only component boost: `+{payload['showcase_boost']}`",
        f"- Record: **{record['wins']}-{record['draws']}-{record['losses']}**",
        f"- Points: **{record['points']}**",
        f"- Goals: **{record['goals_for']}–{record['goals_against']}**",
        f"- Perfect: **{payload['perfect']}**",
        f"- Content SHA-256: `{payload['content_sha256']}`",
        "",
        payload["disclosure"],
        "",
    ]
    return "\n".join(lines)


def write_payload(
    output_dir: Path,
    stem: str,
    payload: dict[str, Any],
    markdown: str,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(markdown, encoding="utf-8")
    return json_path, markdown_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    season_parser = subparsers.add_parser(
        "season", help="Simulate the official 10-team, 36-round HNL format."
    )
    season_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    season_parser.add_argument(
        "--output-dir", type=Path, default=Path("outputs") / "example"
    )

    challenge_parser = subparsers.add_parser(
        "challenge", help="Run the disclosed non-canonical 38-match showcase."
    )
    challenge_parser.add_argument("--seed", type=int, required=True)
    challenge_parser.add_argument("--matches", type=int, default=38)
    challenge_parser.add_argument("--showcase-boost", type=float, default=40.0)
    challenge_parser.add_argument(
        "--output-dir", type=Path, default=Path("outputs") / "challenge"
    )

    find_parser = subparsers.add_parser(
        "find-perfect",
        help="Find and print the first disclosed showcase seed with all wins.",
    )
    find_parser.add_argument("--start-seed", type=int, default=1)
    find_parser.add_argument("--max-seeds", type=int, default=100_000)
    find_parser.add_argument("--matches", type=int, default=38)
    find_parser.add_argument("--showcase-boost", type=float, default=40.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "season":
        payload = simulate_season(args.seed)
        json_path, markdown_path = write_payload(
            args.output_dir,
            f"season_seed_{args.seed}",
            payload,
            render_season_markdown(payload),
        )
        print(json.dumps({"json": str(json_path), "markdown": str(markdown_path)}))
        return 0
    if args.command == "challenge":
        payload = simulate_challenge(args.seed, args.matches, args.showcase_boost)
        json_path, markdown_path = write_payload(
            args.output_dir,
            f"challenge_seed_{args.seed}",
            payload,
            render_challenge_markdown(payload),
        )
        print(json.dumps({"json": str(json_path), "markdown": str(markdown_path)}))
        return 0
    if args.command == "find-perfect":
        payload = find_perfect_seed(
            args.start_seed,
            args.max_seeds,
            args.matches,
            args.showcase_boost,
        )
        if payload is None:
            print(
                json.dumps(
                    {
                        "found": False,
                        "start_seed": args.start_seed,
                        "max_seeds": args.max_seeds,
                    }
                )
            )
            return 1
        print(
            json.dumps(
                {
                    "found": True,
                    "seed": payload["seed"],
                    "record": payload["record"],
                    "showcase_boost": payload["showcase_boost"],
                    "content_sha256": payload["content_sha256"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
