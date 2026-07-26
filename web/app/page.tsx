"use client";

import {
  type CSSProperties,
  type FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Image from "next/image";

type Screen = "home" | "setup" | "lobby" | "draft" | "results";
type GameMode = "solo" | "live";
type Difficulty = "easy" | "normal" | "hard";
type RatingsMode = "season" | "prime";
type DraftMode = "squad-first" | "position-first";
type SortMode = "rating" | "position" | "surname";

type Slot = {
  id: string;
  label: string;
  category: "GK" | "DEF" | "MID" | "FWD";
  acceptedPositions: string[];
};

type Player = {
  id: string;
  personId: string;
  name: string;
  positions: string[];
  nationality?: string | null;
  rating?: number | null;
  ratingHidden?: boolean;
  ratingKind?: string;
  available?: boolean;
  eligibleSlotIds?: string[];
  stats?: {
    appearances?: number | null;
    starts?: number | null;
    minutes?: number | null;
    goals?: number | null;
    assists?: number | null;
    yellowCards?: number | null;
    redCards?: number | null;
    marketValuePeakEur?: number | null;
  };
};

type Pick = {
  turn: number;
  slotId: string;
  slotLabel: string;
  selectedRating: number | null;
  clubSeason: {
    id: string;
    club: Club;
    season: Season;
  };
  player: Player;
};

type Club = {
  id: string;
  name: string;
  shortName?: string;
  city?: string | null;
  accent?: string | null;
  participantId?: string | null;
  managerName?: string | null;
  isHuman?: boolean;
};

type Season = {
  id: string;
  label: string;
  startYear: number;
  endYear: number;
};

type Spin = {
  clubSeasonId: string;
  club: Club;
  season: Season;
  turn: number;
  spinNumber: number;
  lockedSlotId?: string | null;
  players?: Player[] | null;
  squadHidden?: boolean;
};

type ScorerEvent = {
  playerId?: string | null;
  playerName: string;
  minute: number | string;
  assistPlayerId?: string | null;
  assistPlayerName?: string | null;
};

type SeasonMatch = {
  matchweek: number;
  opponent: Club;
  venue: "H" | "A";
  goalsFor: number;
  goalsAgainst: number;
  outcome: "W" | "D" | "L";
  scorers: ScorerEvent[];
  opponentScorers?: ScorerEvent[];
  opponentGoalMinutes?: Array<number | string>;
  opponentParticipantId?: string | null;
  managerMatch?: boolean;
  isManagerVsManager?: boolean;
  matchType?: "league" | "manager-head-to-head";
  running?: {
    played: number;
    wins: number;
    draws: number;
    losses: number;
    points: number;
    goalsFor: number;
    goalsAgainst: number;
    goalDifference: number;
  };
};

type PlayerSeasonTotal = {
  playerId: string;
  playerName: string;
  slotId?: string | null;
  positions?: string[];
  rating?: number | null;
  appearances?: number;
  starts?: number;
  goals: number;
  assists: number;
  cleanSheets: number;
  goalContributions?: number;
};

type SeasonProjection = {
  projectedPosition: number;
  expectedPoints: number;
  titleProbability: number;
  topFourProbability: number;
  perfectProbability: number;
};

type SeasonAward = {
  playerId?: string | null;
  playerName: string;
  goals?: number;
  assists?: number;
};

type LeagueTableRow = {
  position: number;
  teamId: string;
  name: string;
  shortName: string;
  accent: string;
  isDraftedXI: boolean;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDifference: number;
  points: number;
};

type SeasonResult = {
  model?: string;
  confidence?: number;
  disclosure?: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDifference: number;
  points: number;
  seed?: number;
  averageRating?: number;
  finalPosition?: number;
  matches?: SeasonMatch[];
  projection?: SeasonProjection;
  playerStats?: PlayerSeasonTotal[];
  awards?: {
    leagueTitle?: boolean;
    invincible?: boolean;
    perfectSeason?: boolean;
    bestAttack?: boolean;
    bestDefence?: boolean;
    earned?: Array<{ code: string; name: string }>;
    topScorer?: SeasonAward | null;
    topCreator?: SeasonAward | null;
    playerOfSeason?: SeasonAward | null;
  };
  records?: {
    longestWinningStreak?: number;
    longestUnbeatenStreak?: number;
    longestScoringStreak?: number;
    longestCleanSheetStreak?: number;
    biggestWin?: SeasonMatch | null;
    highestScoringMatch?: SeasonMatch | null;
  };
  leagueTable?: LeagueTableRow[];
};

type Participant = {
  id: string;
  name: string;
  seat: number;
  isHost: boolean;
  status: string;
  turn: number;
  rerollsRemaining: number;
  picks: Pick[];
  filledSlotIds: string[];
  squadRating?: number | null;
  currentSpin?: Spin | null;
  result?: SeasonResult | null;
};

type RoomSettings = {
  formation: string;
  slots: Slot[];
  targetPicks: number;
  difficulty: Difficulty;
  rerolls: number;
  showRatings: boolean;
  ratingsMode: RatingsMode;
  draftMode: DraftMode;
  seasonStart: number;
  seasonEnd: number;
  maxPlayers: number;
};

type Room = {
  apiVersion: string;
  code: string;
  mode: GameMode;
  status: "lobby" | "drafting" | "complete" | "expired";
  version: number;
  seed: number;
  hostParticipantId: string;
  viewerParticipantId?: string | null;
  settings: RoomSettings;
  participants: Participant[];
  leaderboard?: Array<{
    participantId: string;
    name: string;
    squadRating: number | null;
    rank: number;
  }> | null;
  catalog?: {
    completeness?: string;
    confidence?: number | null;
  };
};

type RoomAuthResponse = {
  roomCode: string;
  participantId: string;
  participantToken: string;
  room: Room;
};

type CatalogInventory = {
  metadata?: {
    clubSeasonCount?: number;
    playerSeasonCount?: number;
    normalizedCoverage?: {
      earliestStartYear?: number;
      latestStartYear?: number;
    };
    coverage?: {
      completeHistoricalRosterArchive?: boolean;
      officialLegacyChampionSquads?: number;
      confidence?: number;
    };
    completeness?: string;
  };
  clubSeasons?: Array<{
    id: string;
    club: Club;
    season: Season;
    playerCount: number;
  }>;
};

type CatalogClubSeason = NonNullable<CatalogInventory["clubSeasons"]>[number];

type SpinAnimation = {
  key: string;
  items: CatalogClubSeason[];
  selected: Spin;
  reducedMotion: boolean;
};

type SeasonPhase = "preview" | "running" | "final";
type SimulationSpeed = "normal" | "fast";

type SetupState = {
  formation: string;
  difficulty: Difficulty;
  ratingsMode: RatingsMode;
  draftMode: DraftMode;
  showRatings: boolean;
  seasonStart: number;
  seasonEnd: number;
  maxPlayers: number;
};

const API_BASE = (
  process.env.NEXT_PUBLIC_SIM_API_URL ?? "http://127.0.0.1:8002"
).replace(/\/$/, "");

const FORMATIONS = [
  "4-3-3",
  "4-4-2",
  "4-2-3-1",
  "4-5-1",
  "3-4-3",
  "3-5-2",
  "5-4-1",
  "4-1-2-1-2",
  "4-4-1-1",
  "5-3-2",
  "3-4-1-2",
  "4-2-2-2",
] as const;

const DEFAULT_SETUP: SetupState = {
  formation: "4-3-3",
  difficulty: "normal",
  ratingsMode: "season",
  draftMode: "squad-first",
  showRatings: true,
  seasonStart: 1995,
  seasonEnd: 2025,
  maxPlayers: 4,
};

const FORMATION_PREVIEWS: Record<string, string[]> = {
  "4-3-3": ["GK", "RB", "CB", "CB", "LB", "CM", "CM", "CM", "RW", "ST", "LW"],
  "4-4-2": ["GK", "RB", "CB", "CB", "LB", "RM", "CM", "CM", "LM", "ST", "ST"],
  "4-2-3-1": ["GK", "RB", "CB", "CB", "LB", "DM", "DM", "RW", "AM", "LW", "ST"],
  "4-5-1": ["GK", "RB", "CB", "CB", "LB", "RM", "CM", "CM", "CM", "LM", "ST"],
  "3-4-3": ["GK", "CB", "CB", "CB", "RM", "CM", "CM", "LM", "RW", "ST", "LW"],
  "3-5-2": ["GK", "CB", "CB", "CB", "RWB", "DM", "CM", "CM", "LWB", "ST", "ST"],
  "5-4-1": ["GK", "RWB", "CB", "CB", "CB", "LWB", "RM", "CM", "CM", "LM", "ST"],
  "4-1-2-1-2": ["GK", "RB", "CB", "CB", "LB", "DM", "CM", "CM", "AM", "ST", "ST"],
  "4-4-1-1": ["GK", "RB", "CB", "CB", "LB", "RM", "CM", "CM", "LM", "AM", "ST"],
  "5-3-2": ["GK", "RWB", "CB", "CB", "CB", "LWB", "CM", "CM", "CM", "ST", "ST"],
  "3-4-1-2": ["GK", "CB", "CB", "CB", "RM", "CM", "CM", "LM", "AM", "ST", "ST"],
  "4-2-2-2": ["GK", "RB", "CB", "CB", "LB", "DM", "DM", "AM", "AM", "ST", "ST"],
};

const EMPTY_SEASON_MATCHES: SeasonMatch[] = [];

type PitchPoint = readonly [x: number, y: number];

/*
 * Coordinates follow the stable API slot order for each formation. Keeping the
 * complete shape here avoids category-based spreading that pushes two holding
 * midfielders to one side or leaves a lone central role off-centre.
 */
const FORMATION_COORDINATES: Record<string, readonly PitchPoint[]> = {
  "4-3-3": [
    [50, 89],
    [86, 70],
    [62, 73],
    [38, 73],
    [14, 70],
    [50, 57],
    [68, 44],
    [32, 44],
    [80, 21],
    [50, 15],
    [20, 21],
  ],
  "4-4-2": [
    [50, 89],
    [86, 70],
    [62, 73],
    [38, 73],
    [14, 70],
    [86, 46],
    [62, 48],
    [38, 48],
    [14, 46],
    [62, 16],
    [38, 16],
  ],
  "4-2-3-1": [
    [50, 89],
    [86, 70],
    [62, 73],
    [38, 73],
    [14, 70],
    [64, 57],
    [36, 57],
    [82, 34],
    [50, 35],
    [18, 34],
    [50, 15],
  ],
  "4-5-1": [
    [50, 89],
    [86, 70],
    [62, 73],
    [38, 73],
    [14, 70],
    [86, 45],
    [67, 53],
    [50, 44],
    [33, 53],
    [14, 45],
    [50, 15],
  ],
  "3-4-3": [
    [50, 89],
    [70, 73],
    [50, 75],
    [30, 73],
    [86, 47],
    [62, 49],
    [38, 49],
    [14, 47],
    [80, 21],
    [50, 15],
    [20, 21],
  ],
  "3-5-2": [
    [50, 89],
    [70, 73],
    [50, 75],
    [30, 73],
    [90, 58],
    [50, 57],
    [67, 43],
    [33, 43],
    [10, 58],
    [62, 16],
    [38, 16],
  ],
  "5-4-1": [
    [50, 89],
    [90, 61],
    [70, 73],
    [50, 75],
    [30, 73],
    [10, 61],
    [86, 45],
    [62, 48],
    [38, 48],
    [14, 45],
    [50, 15],
  ],
  "4-1-2-1-2": [
    [50, 89],
    [86, 70],
    [62, 73],
    [38, 73],
    [14, 70],
    [50, 58],
    [68, 46],
    [32, 46],
    [50, 33],
    [62, 15],
    [38, 15],
  ],
  "4-4-1-1": [
    [50, 89],
    [86, 70],
    [62, 73],
    [38, 73],
    [14, 70],
    [86, 47],
    [62, 49],
    [38, 49],
    [14, 47],
    [50, 31],
    [50, 14],
  ],
  "5-3-2": [
    [50, 89],
    [90, 61],
    [70, 73],
    [50, 75],
    [30, 73],
    [10, 61],
    [68, 45],
    [50, 47],
    [32, 45],
    [62, 16],
    [38, 16],
  ],
  "3-4-1-2": [
    [50, 89],
    [70, 73],
    [50, 75],
    [30, 73],
    [86, 48],
    [62, 49],
    [38, 49],
    [14, 48],
    [50, 32],
    [62, 15],
    [38, 15],
  ],
  "4-2-2-2": [
    [50, 89],
    [86, 70],
    [62, 73],
    [38, 73],
    [14, 70],
    [65, 57],
    [35, 57],
    [68, 35],
    [32, 35],
    [62, 15],
    [38, 15],
  ],
};

const AI_MATCH_REVEAL_MS: Record<SimulationSpeed, number> = {
  normal: 1_400,
  fast: 470,
};

const MANAGER_MATCH_REVEAL_MS: Record<SimulationSpeed, number> = {
  normal: 4_400,
  fast: 1_470,
};

const CLUB_CREST_IDS = new Set([
  "419",
  "447",
  "144",
  "327",
  "2362",
  "999",
  "11194",
  "599",
  "5107",
  "918",
  "223",
  "2566",
  "420",
  "314",
  "485",
  "24575",
  "11083",
  "12109",
  "456",
]);

const CLUB_CREST_ALIASES: Record<string, string> = {
  "croatia-zagreb": "419",
  "gnk-dinamo": "419",
  "hnk-hajduk": "447",
  "hnk-rijeka": "144",
  "nk-osijek": "327",
  "nk-slaven-belupo": "2362",
  "nk-istra-1961": "999",
  "nk-lokomotiva": "11194",
  "nk-varazdin": "599",
  "nk-zagreb": "5107",
  "nk-inter-zapresic": "918",
  "hnk-sibenik": "223",
  "nk-zadar": "2566",
  "rnk-split": "420",
  "hnk-cibalia": "314",
  "nk-hrvatski-dragovoljac": "485",
  "hnk-gorica": "24575",
  "nk-rudes": "11083",
  "nk-lucko": "12109",
  "hnk-vukovar-1991": "456",
};

class ApiError extends Error {
  code: string;
  status: number;

  constructor(message: string, code = "request_failed", status = 0) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "API nije dostupan. Provjeri je li Docker servis pokrenut.",
      "network_error",
    );
  }
  const payload = (await response.json().catch(() => ({}))) as {
    error?: { code?: string; message?: string };
  };
  if (!response.ok) {
    throw new ApiError(
      payload.error?.message ?? `Zahtjev nije uspio (${response.status}).`,
      payload.error?.code ?? "request_failed",
      response.status,
    );
  }
  return payload as T;
}

function formatNumber(value: number | undefined, fallback: string) {
  return typeof value === "number"
    ? new Intl.NumberFormat("hr-HR").format(value)
    : fallback;
}

function managerInitials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

function clubMonogram(club: Club) {
  const clubName = `${club.shortName || ""} ${club.name}`.toLocaleLowerCase(
    "hr-HR",
  );
  const knownMonograms: Array<[string, string]> = [
    ["dinamo", "DIN"],
    ["hajduk", "HAJ"],
    ["rijeka", "RIJ"],
    ["osijek", "OSI"],
    ["istra", "IST"],
    ["lokomotiva", "LOK"],
    ["gorica", "GOR"],
    ["slaven", "SLA"],
    ["varaždin", "VAR"],
    ["varazdin", "VAR"],
    ["vukovar", "VUK"],
  ];
  const known = knownMonograms.find(([needle]) => clubName.includes(needle));
  if (known) return known[1];

  const cleaned = (club.shortName || club.name)
    .replace(/\b(HNK|GNK|NK|RNK|NŠ|NŠK|HAŠK|1\.)\b/gi, " ")
    .replace(/[^A-Za-zÀ-ž0-9 ]/g, " ")
    .trim();
  const words = cleaned.split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
  return words
    .slice(0, 3)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

function clubCrestPath(club: Club) {
  const sourceId = String(club.id).toLocaleLowerCase("hr-HR");
  const crestId = CLUB_CREST_IDS.has(sourceId)
    ? sourceId
    : CLUB_CREST_ALIASES[sourceId];
  return crestId ? `/clubs/${crestId}.png` : null;
}

function surname(name: string) {
  return name.trim().split(/\s+/).at(-1) ?? name;
}

function playerStatLine(player: Player) {
  const stats = player.stats ?? {};
  const parts: string[] = [];
  if (typeof stats.appearances === "number") parts.push(`${stats.appearances} N`);
  if (typeof stats.goals === "number") parts.push(`${stats.goals} G`);
  if (typeof stats.assists === "number") parts.push(`${stats.assists} A`);
  return parts.length ? parts.join(" · ") : "arhivski zapis";
}

function seededNoise(seed: number) {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
}

function buildSpinItems(
  catalog: CatalogInventory | null,
  selected: Spin,
  settings: RoomSettings,
  seed: number,
  seat: number,
): CatalogClubSeason[] {
  const selectedItem: CatalogClubSeason =
    catalog?.clubSeasons?.find((item) => item.id === selected.clubSeasonId) ?? {
      id: selected.clubSeasonId,
      club: selected.club,
      season: selected.season,
      playerCount: selected.players?.length ?? 0,
    };
  const eligible =
    catalog?.clubSeasons?.filter(
      (item) =>
        item.season.startYear >= settings.seasonStart &&
        item.season.startYear <= settings.seasonEnd,
    ) ?? [];
  const pool = eligible.length ? eligible : [selectedItem];
  const decoys = Array.from({ length: 17 }, (_, index) => {
    const noise = seededNoise(
      seed +
        seat * 193 +
        selected.turn * 977 +
        selected.spinNumber * 1543 +
        index * 71,
    );
    return pool[Math.floor(noise * pool.length) % pool.length];
  });
  if (decoys.at(-1)?.id === selectedItem.id && pool.length > 1) {
    decoys[decoys.length - 1] =
      pool[(pool.findIndex((item) => item.id === selectedItem.id) + 1) % pool.length];
  }
  return [...decoys, selectedItem];
}

function fallbackProjection(rating: number | null | undefined): SeasonProjection {
  const strength = rating ?? 70;
  const expectedPoints = Math.round(
    Math.max(28, Math.min(96, 48 + (strength - 70) * 2.15)),
  );
  const projectedPosition = Math.max(
    1,
    Math.min(10, 10 - Math.round((expectedPoints - 32) / 8)),
  );
  const titleProbability = Math.max(
    0.005,
    Math.min(0.92, (expectedPoints - 56) / 42),
  );
  return {
    projectedPosition,
    expectedPoints,
    titleProbability,
    topFourProbability: Math.max(
      0.04,
      Math.min(0.99, (expectedPoints - 35) / 45),
    ),
    perfectProbability: Math.max(0.0001, Math.min(0.018, (strength - 72) / 900)),
  };
}

function aggregateMatches(matches: SeasonMatch[]) {
  return matches.reduce(
    (total, match) => {
      total.played += 1;
      total.goalsFor += match.goalsFor;
      total.goalsAgainst += match.goalsAgainst;
      if (match.outcome === "W") total.wins += 1;
      if (match.outcome === "D") total.draws += 1;
      if (match.outcome === "L") total.losses += 1;
      total.points = total.wins * 3 + total.draws;
      total.goalDifference = total.goalsFor - total.goalsAgainst;
      return total;
    },
    {
      played: 0,
      wins: 0,
      draws: 0,
      losses: 0,
      points: 0,
      goalsFor: 0,
      goalsAgainst: 0,
      goalDifference: 0,
    },
  );
}

function probability(value: number | undefined) {
  if (typeof value !== "number") return "—";
  const normalized = value > 1 ? value : value * 100;
  if (normalized > 0 && normalized < 0.1) return "<0,1%";
  return `${new Intl.NumberFormat("hr-HR", {
    maximumFractionDigits: normalized < 10 ? 1 : 0,
  }).format(normalized)}%`;
}

function finishLabel(position: number | undefined) {
  if (!position) return "—";
  return `${position}.`;
}

function formatMatchMinute(minute: number | string) {
  if (typeof minute === "string") return minute.includes("′") ? minute : `${minute}′`;
  return `${minute}′`;
}

function simulateSeason(
  rating: number | null | undefined,
  seed: number,
  seat: number,
): SeasonResult {
  const strength = rating ?? 70;
  const firstNoise = seededNoise(seed + seat * 97);
  const secondNoise = seededNoise(seed + seat * 211 + 17);
  const wins = Math.max(
    3,
    Math.min(34, Math.round(12 + (strength - 70) * 0.88 + (firstNoise - 0.5) * 5)),
  );
  const draws = Math.max(
    1,
    Math.min(36 - wins, Math.round(8 - (strength - 75) * 0.12 + secondNoise * 3)),
  );
  const losses = 36 - wins - draws;
  const goalsFor = Math.max(
    wins,
    Math.round(38 + (strength - 65) * 2.05 + firstNoise * 10),
  );
  const goalsAgainst = Math.max(
    12,
    Math.round(51 - (strength - 65) * 1.45 + secondNoise * 9),
  );
  return {
    played: 36,
    wins,
    draws,
    losses,
    goalsFor,
    goalsAgainst,
    goalDifference: goalsFor - goalsAgainst,
    points: wins * 3 + draws,
  };
}

function slotPoint(slot: Slot, slots: Slot[], formation?: string) {
  const formationPoints = formation
    ? FORMATION_COORDINATES[formation]
    : undefined;
  const slotIndex = slots.findIndex((item) => item.id === slot.id);
  const formationPoint = formationPoints?.[slotIndex];
  if (formationPoint && formationPoints?.length === slots.length) {
    return { x: formationPoint[0], y: formationPoint[1] };
  }

  const sameCategory = slots.filter((item) => item.category === slot.category);
  const index = sameCategory.findIndex((item) => item.id === slot.id);
  const count = sameCategory.length;
  const label = slot.label.toUpperCase();
  let x = count === 1 ? 50 : 13 + (index * 74) / Math.max(1, count - 1);
  let y =
    slot.category === "GK"
      ? 89
      : slot.category === "DEF"
        ? 70
        : slot.category === "MID"
          ? 47
          : 20;

  if (label.includes("CB")) y = 73;
  if (label.includes("WB")) y = 61;
  if (label.includes("DM")) y = 57;
  if (label.includes("AM")) y = 35;
  if (label.includes("ST")) y = 16;
  if (/^(L|R)(B|WB|M|W)$/.test(label)) {
    x = label.startsWith("L") ? 14 : 86;
  }
  if (label === "LW") x = 20;
  if (label === "RW") x = 80;
  if (label === "LB") x = 14;
  if (label === "RB") x = 86;
  if (label === "LWB") x = 10;
  if (label === "RWB") x = 90;
  return { x, y };
}

function matchMinuteValue(minute: number | string) {
  if (typeof minute === "number") return minute;
  const parsed = Number.parseInt(minute, 10);
  return Number.isFinite(parsed) ? parsed : 90;
}

function isManagerFixture(
  match: SeasonMatch | undefined,
  participantIds: ReadonlySet<string>,
) {
  if (!match) return false;
  return Boolean(
    match.managerMatch ||
      match.isManagerVsManager ||
      match.matchType === "manager-head-to-head" ||
      match.opponent.isHuman ||
      match.opponentParticipantId ||
      match.opponent.participantId ||
      participantIds.has(match.opponent.id),
  );
}

function Header({
  stage,
  room,
  onHome,
}: {
  stage: string;
  room?: Room | null;
  onHome: () => void;
}) {
  return (
    <header className="topbar">
      <button className="brand" onClick={onHome} aria-label="36–0 HNL naslovnica">
        <span className="brand-score">36–0</span>
        <span className="brand-meta">
          HNL DRAFT
          <small>KLUB × SEZONA</small>
        </span>
      </button>
      <div className="stage-indicator" aria-label={`Trenutni korak: ${stage}`}>
        <span className="pulse-dot" aria-hidden="true" />
        {stage}
      </div>
      <div className="header-room">
        {room ? (
          <>
            <span>Soba</span>
            <strong>{room.code}</strong>
          </>
        ) : (
          <span className="fan-made">Nezavisni fan projekt</span>
        )}
      </div>
    </header>
  );
}

function SectionTitle({
  index,
  title,
  copy,
}: {
  index: string;
  title: string;
  copy?: string;
}) {
  return (
    <div className="section-title">
      <span>{index}</span>
      <div>
        <h2>{title}</h2>
        {copy ? <p>{copy}</p> : null}
      </div>
    </div>
  );
}

function Toggle({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`toggle-choice${active ? " active" : ""}`}
      aria-pressed={active}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function ClubShield({
  club,
  compact = false,
}: {
  club: Club;
  compact?: boolean;
}) {
  const crestPath = clubCrestPath(club);
  return (
    <span
      className={`club-shield${compact ? " compact" : ""}${
        crestPath ? " with-logo" : ""
      }`}
      style={
        {
          "--shield-accent": club.accent || "var(--lime)",
        } as CSSProperties
      }
      aria-hidden="true"
    >
      {crestPath ? (
        <Image
          key={crestPath}
          className="club-logo"
          src={crestPath}
          alt=""
          width={139}
          height={181}
          unoptimized
          draggable={false}
          onLoad={(event) =>
            event.currentTarget.parentElement?.classList.add("has-logo")
          }
          onError={(event) => {
            event.currentTarget.hidden = true;
            event.currentTarget.parentElement?.classList.remove(
              "with-logo",
              "has-logo",
            );
            event.currentTarget.parentElement?.classList.add("logo-failed");
          }}
        />
      ) : null}
      <i>{clubMonogram(club)}</i>
    </span>
  );
}

function ClubSeasonReel({ animation }: { animation: SpinAnimation }) {
  const style = {
    "--reel-index": animation.items.length - 1,
    "--reel-duration": animation.reducedMotion ? "180ms" : "3.25s",
    "--season-delay": animation.reducedMotion ? "0ms" : "180ms",
  } as CSSProperties;
  return (
    <div className="reel-state" key={animation.key} style={style}>
      <div className="round-label">
        KOTAČ {String(animation.selected.turn + 1).padStart(2, "0")}
      </div>
      <p className="eyebrow">KLUB × TOČNA SEZONA</p>
      <h2>Kotač se vrti…</h2>
      <div
        className="club-season-reel"
        aria-live="polite"
        aria-label={`Izvlačenje: ${animation.selected.club.name}, ${animation.selected.season.label}`}
      >
        <div className="reel-column club-column">
          <span className="reel-caption">KLUB</span>
          <div className="reel-viewport">
            <div className="reel-track">
              {animation.items.map((item, index) => (
                <div className="reel-item club-reel-item" key={`${item.id}-${index}`}>
                  <ClubShield club={item.club} compact />
                  <strong>{item.club.name}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
        <span className="reel-times" aria-hidden="true">
          ×
        </span>
        <div className="reel-column season-column">
          <span className="reel-caption">SEZONA</span>
          <div className="reel-viewport">
            <div className="reel-track">
              {animation.items.map((item, index) => (
                <div className="reel-item season-reel-item" key={`${item.id}-s-${index}`}>
                  <strong>{item.season.label}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <p className="reel-lock-copy">
        Zaključavamo klub, zatim sezonu. Sastav se otvara nakon zaustavljanja.
      </p>
    </div>
  );
}

function MatchCard({
  match,
  featured = false,
  revealMinute,
}: {
  match: SeasonMatch;
  featured?: boolean;
  revealMinute?: number;
}) {
  const isLiveReveal = typeof revealMinute === "number";
  const displayedMinute = Math.max(0, Math.min(90, revealMinute ?? 90));
  const isFullTime = !isLiveReveal || displayedMinute >= 90;
  const visibleScorers = isLiveReveal
    ? match.scorers.filter(
        (event) => matchMinuteValue(event.minute) <= displayedMinute,
      )
    : match.scorers;
  const opponentScorers =
    match.opponentScorers ??
    (match.opponentGoalMinutes ?? []).map((minute, index) => ({
      playerId: `opponent-${index}`,
      playerName:
        match.opponent.managerName ??
        match.opponent.shortName ??
        match.opponent.name,
      minute,
    }));
  const visibleOpponentScorers = isLiveReveal
    ? opponentScorers.filter(
        (event) => matchMinuteValue(event.minute) <= displayedMinute,
      )
    : opponentScorers;
  const displayedGoalsFor = isFullTime
    ? match.goalsFor
    : visibleScorers.length;
  const displayedGoalsAgainst = isFullTime
    ? match.goalsAgainst
    : visibleOpponentScorers.length;
  const visibleGoalFeed = [
    ...visibleScorers.map((event) => ({ ...event, against: false })),
    ...visibleOpponentScorers.map((event) => ({ ...event, against: true })),
  ].sort((a, b) => matchMinuteValue(a.minute) - matchMinuteValue(b.minute));

  return (
    <article
      className={[
        "match-card",
        isLiveReveal && !isFullTime
          ? "outcome-live manager-match-live"
          : `outcome-${match.outcome.toLowerCase()}`,
        featured ? "featured" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <div className="match-card-top">
        <span>
          KOLO {match.matchweek}
          {isLiveReveal ? " · MENADŽER VS MENADŽER" : ""}
        </span>
        <b>{isLiveReveal ? (isFullTime ? "FT" : `${displayedMinute}′`) : match.outcome}</b>
      </div>
      <div className="match-opponent">
        <ClubShield club={match.opponent} compact />
        <div>
          <strong>{match.opponent.name}</strong>
          <small>{match.venue === "H" ? "DOMA" : "U GOSTIMA"}</small>
        </div>
        <em>
          {displayedGoalsFor}
          <i>–</i>
          {displayedGoalsAgainst}
        </em>
      </div>
      {isLiveReveal ? (
        <div
          className="manager-match-progress"
          aria-label={
            isFullTime
              ? "Utakmica završena"
              : `Utakmica u tijeku, ${displayedMinute}. minuta`
          }
        >
          <span>0′</span>
          <div aria-hidden="true">
            <i style={{ width: `${(displayedMinute / 90) * 100}%` }} />
          </div>
          <strong>{isFullTime ? "FT" : "90′"}</strong>
        </div>
      ) : null}
      <div className="match-scorers">
        {visibleGoalFeed.length ? (
          <>
            <span aria-hidden="true">⚽</span>
            <p>
              {visibleGoalFeed.map((event, index) => (
                <span
                  className={event.against ? "opponent-goal" : ""}
                  key={`${event.playerId ?? event.playerName}-${event.minute}-${index}`}
                >
                  {event.playerName} {formatMatchMinute(event.minute)}
                </span>
              ))}
            </p>
          </>
        ) : isLiveReveal && !isFullTime ? (
          <p>Utakmica je u tijeku · bez pogodaka</p>
        ) : (
          <p>Bez pogodaka</p>
        )}
      </div>
    </article>
  );
}

export default function HnlDraftGame() {
  const [screen, setScreen] = useState<Screen>("home");
  const [mode, setMode] = useState<GameMode>("solo");
  const [managerName, setManagerName] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const [setup, setSetup] = useState<SetupState>(DEFAULT_SETUP);
  const [catalog, setCatalog] = useState<CatalogInventory | null>(null);
  const [room, setRoom] = useState<Room | null>(null);
  const [participantToken, setParticipantToken] = useState("");
  const [participantId, setParticipantId] = useState("");
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [lockedSlotId, setLockedSlotId] = useState<string | null>(null);
  const [repositioning, setRepositioning] = useState(false);
  const [moveFromSlotId, setMoveFromSlotId] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<SortMode>("rating");
  const [spinAnimation, setSpinAnimation] = useState<SpinAnimation | null>(null);
  const [seasonPhase, setSeasonPhase] = useState<SeasonPhase>("preview");
  const [revealedWeek, setRevealedWeek] = useState(0);
  const [activeMatchClock, setActiveMatchClock] = useState({
    key: "",
    minute: 0,
  });
  const [simulationSpeed, setSimulationSpeed] =
    useState<SimulationSpeed>("normal");
  const activeMatchRef = useRef({ key: "", minute: 0 });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const coverage = catalog?.metadata?.normalizedCoverage;
  const earliestYear = coverage?.earliestStartYear ?? 1995;
  const latestYear = coverage?.latestStartYear ?? 2025;
  const seasonYears = useMemo(
    () =>
      Array.from(
        { length: latestYear - earliestYear + 1 },
        (_, index) => earliestYear + index,
      ),
    [earliestYear, latestYear],
  );

  useEffect(() => {
    let active = true;
    apiRequest<CatalogInventory>("/catalog")
      .then((inventory) => {
        if (!active) return;
        setCatalog(inventory);
        const nextEarliest =
          inventory.metadata?.normalizedCoverage?.earliestStartYear ?? 1995;
        const nextLatest =
          inventory.metadata?.normalizedCoverage?.latestStartYear ?? 2025;
        setSetup((current) => ({
          ...current,
          seasonStart: nextEarliest,
          seasonEnd: nextLatest,
        }));
      })
      .catch(() => {
        if (active) setNotice("Katalog će se učitati kada API bude dostupan.");
      });

    window.queueMicrotask(() => {
      if (!active) return;
      const params = new URLSearchParams(window.location.search);
      const invitedCode = params.get("room");
      if (invitedCode) setJoinCode(invitedCode.toUpperCase().slice(0, 6));

      const saved = window.sessionStorage.getItem("hnl-room-session");
      if (saved) {
        try {
          const session = JSON.parse(saved) as {
            code: string;
            token: string;
            participantId: string;
          };
          setParticipantToken(session.token);
          setParticipantId(session.participantId);
          apiRequest<Room>(`/rooms/${session.code}`, {}, session.token)
            .then((restoredRoom) => {
              if (!active) return;
              setRoom(restoredRoom);
            })
            .catch(() => {
              window.sessionStorage.removeItem("hnl-room-session");
            });
        } catch {
          window.sessionStorage.removeItem("hnl-room-session");
        }
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const activeScreen: Screen = room
    ? room.status === "lobby"
      ? "lobby"
      : room.status === "drafting"
        ? "draft"
        : room.status === "complete"
          ? "results"
          : "home"
    : screen;

  const refreshRoom = useCallback(async () => {
    if (!room || !participantToken) return;
    try {
      const refreshed = await apiRequest<Room>(
        `/rooms/${room.code}`,
        {},
        participantToken,
      );
      setRoom(refreshed);
    } catch (refreshError) {
      if (refreshError instanceof ApiError && refreshError.code === "room_expired") {
        setError("Soba je istekla. Pokreni novu igru.");
      }
    }
  }, [participantToken, room]);

  useEffect(() => {
    if (
      !room ||
      !participantToken ||
      room.mode !== "live" ||
      room.status === "complete" ||
      room.status === "expired"
    ) {
      return;
    }
    const timer = window.setInterval(refreshRoom, 1200);
    return () => window.clearInterval(timer);
  }, [participantToken, refreshRoom, room]);

  const me = useMemo(
    () => room?.participants.find((item) => item.id === participantId) ?? null,
    [participantId, room],
  );
  const participantIds = useMemo(
    () => new Set(room?.participants.map((participant) => participant.id) ?? []),
    [room?.participants],
  );

  const currentSpin = me?.currentSpin ?? null;
  const selectedPlayer =
    currentSpin?.players?.find((item) => item.id === selectedPlayerId) ?? null;
  const seasonMatches = me?.result?.matches ?? EMPTY_SEASON_MATCHES;

  useEffect(() => {
    if (seasonPhase !== "running") return;
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const finished = revealedWeek >= seasonMatches.length;
    if (finished) {
      const finalTimer = window.setTimeout(
        () => setSeasonPhase("final"),
        reducedMotion ? 30 : 650,
      );
      return () => window.clearTimeout(finalTimer);
    }

    const match = seasonMatches[revealedWeek];
    const managerFixture = isManagerFixture(match, participantIds);
    if (!managerFixture) {
      activeMatchRef.current = { key: "", minute: 0 };
      const aiTimer = window.setTimeout(
        () =>
          setRevealedWeek((current) =>
            Math.min(current + 1, seasonMatches.length),
          ),
        reducedMotion ? 24 : AI_MATCH_REVEAL_MS[simulationSpeed],
      );
      return () => window.clearTimeout(aiTimer);
    }

    const matchKey = `${match.matchweek}:${match.opponent.id}`;
    const startingMinute =
      activeMatchRef.current.key === matchKey
        ? activeMatchRef.current.minute
        : 0;
    activeMatchRef.current = { key: matchKey, minute: startingMinute };

    if (reducedMotion) {
      const fullTimeTimer = window.setTimeout(() => {
        activeMatchRef.current.minute = 90;
        setActiveMatchClock({ key: matchKey, minute: 90 });
      }, 0);
      const reducedTimer = window.setTimeout(
        () =>
          setRevealedWeek((current) =>
            Math.min(current + 1, seasonMatches.length),
          ),
        40,
      );
      return () => {
        window.clearTimeout(fullTimeTimer);
        window.clearTimeout(reducedTimer);
      };
    }

    const totalDuration = MANAGER_MATCH_REVEAL_MS[simulationSpeed];
    const fullTimeHold = simulationSpeed === "fast" ? 150 : 400;
    const minuteRange = Math.max(0, 90 - startingMinute);
    const progressDuration =
      ((totalDuration - fullTimeHold) * minuteRange) / 90;
    const startedAt = window.performance.now();
    const progressTimer = window.setInterval(() => {
      const elapsed = window.performance.now() - startedAt;
      const minute = Math.min(
        90,
        Math.floor(
          startingMinute +
            (elapsed / Math.max(1, progressDuration)) * minuteRange,
        ),
      );
      activeMatchRef.current.minute = minute;
      setActiveMatchClock({ key: matchKey, minute });
    }, 90);
    const fullTimeTimer = window.setTimeout(() => {
      activeMatchRef.current.minute = 90;
      setActiveMatchClock({ key: matchKey, minute: 90 });
    }, progressDuration);
    const completeTimer = window.setTimeout(() => {
      setRevealedWeek((current) =>
        Math.min(current + 1, seasonMatches.length),
      );
    }, progressDuration + fullTimeHold);

    return () => {
      window.clearInterval(progressTimer);
      window.clearTimeout(fullTimeTimer);
      window.clearTimeout(completeTimer);
    };
  }, [
    participantIds,
    revealedWeek,
    seasonMatches,
    seasonPhase,
    simulationSpeed,
  ]);

  const sortedPlayers = useMemo(() => {
    const players = [...(currentSpin?.players ?? [])];
    if (sortMode === "rating") {
      return players.sort(
        (a, b) =>
          (b.rating ?? -1) - (a.rating ?? -1) || a.name.localeCompare(b.name),
      );
    }
    if (sortMode === "position") {
      return players.sort(
        (a, b) =>
          (a.positions[0] ?? "").localeCompare(b.positions[0] ?? "") ||
          a.name.localeCompare(b.name),
      );
    }
    return players.sort((a, b) => surname(a.name).localeCompare(surname(b.name)));
  }, [currentSpin?.players, sortMode]);

  const saveSession = (auth: RoomAuthResponse) => {
    setParticipantToken(auth.participantToken);
    setParticipantId(auth.participantId);
    setRoom(auth.room);
    setSeasonPhase("preview");
    setRevealedWeek(0);
    window.sessionStorage.setItem(
      "hnl-room-session",
      JSON.stringify({
        code: auth.roomCode,
        token: auth.participantToken,
        participantId: auth.participantId,
      }),
    );
    const url = new URL(window.location.href);
    url.searchParams.set("room", auth.roomCode);
    window.history.replaceState({}, "", url);
  };

  const clearMessages = () => {
    setError("");
    setNotice("");
  };

  const requireName = () => {
    const clean = managerName.trim();
    if (!clean) {
      setError("Upiši ime menadžera.");
      return null;
    }
    return clean;
  };

  const chooseMode = (nextMode: GameMode) => {
    clearMessages();
    if (!requireName()) return;
    setMode(nextMode);
    setScreen("setup");
  };

  const createGame = async () => {
    const cleanName = requireName();
    if (!cleanName) return;
    clearMessages();
    setBusy(true);
    try {
      const auth = await apiRequest<RoomAuthResponse>("/rooms", {
        method: "POST",
        body: JSON.stringify({
          mode,
          name: cleanName,
          settings: {
            formation: setup.formation,
            difficulty: setup.difficulty,
            ratingsMode: setup.ratingsMode,
            draftMode: setup.draftMode,
            showRatings: setup.showRatings,
            seasonStart: setup.seasonStart,
            seasonEnd: setup.seasonEnd,
            maxPlayers: mode === "solo" ? 1 : setup.maxPlayers,
          },
        }),
      });
      saveSession(auth);
      if (mode === "solo") {
        const started = await apiRequest<Room>(
          `/rooms/${auth.roomCode}/start`,
          {
            method: "POST",
            body: JSON.stringify({ expectedVersion: auth.room.version }),
          },
          auth.participantToken,
        );
        setRoom(started);
      }
    } catch (creationError) {
      setError(
        creationError instanceof Error
          ? creationError.message
          : "Sobu nije moguće stvoriti.",
      );
    } finally {
      setBusy(false);
    }
  };

  const joinRoom = async (event?: FormEvent) => {
    event?.preventDefault();
    const cleanName = requireName();
    const code = joinCode.trim().toUpperCase();
    if (!cleanName) return;
    if (code.length !== 6) {
      setError("Kod sobe ima 6 znakova.");
      return;
    }
    clearMessages();
    setBusy(true);
    try {
      const auth = await apiRequest<RoomAuthResponse>(`/rooms/${code}/join`, {
        method: "POST",
        body: JSON.stringify({ name: cleanName }),
      });
      saveSession(auth);
    } catch (joinError) {
      setError(
        joinError instanceof Error ? joinError.message : "Sobi se nije moguće pridružiti.",
      );
    } finally {
      setBusy(false);
    }
  };

  const startLiveDraft = async () => {
    if (!room || !participantToken) return;
    clearMessages();
    setBusy(true);
    try {
      setRoom(
        await apiRequest<Room>(
          `/rooms/${room.code}/start`,
          {
            method: "POST",
            body: JSON.stringify({ expectedVersion: room.version }),
          },
          participantToken,
        ),
      );
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Draft nije pokrenut.");
      await refreshRoom();
    } finally {
      setBusy(false);
    }
  };

  const spin = useCallback(
    async (reroll = false) => {
      if (!room || !me || !participantToken || busy) return;
      if (
        room.settings.draftMode === "position-first" &&
        !reroll &&
        !lockedSlotId
      ) {
        setError("Prvo odaberi praznu poziciju na terenu.");
        return;
      }
      clearMessages();
      setBusy(true);
      try {
        const payload: Record<string, unknown> = {
          expectedVersion: room.version,
          expectedTurn: me.turn,
          reroll,
        };
        if (room.settings.draftMode === "position-first" && !reroll) {
          payload.slotId = lockedSlotId;
        }
        const nextRoom = await apiRequest<Room>(
          `/rooms/${room.code}/spin`,
          { method: "POST", body: JSON.stringify(payload) },
          participantToken,
        );
        setRoom(nextRoom);
        setSelectedPlayerId(null);
        const nextManager = nextRoom.participants.find(
          (participant) => participant.id === participantId,
        );
        const selectedSpin = nextManager?.currentSpin;
        if (selectedSpin) {
          const reducedMotion = window.matchMedia(
            "(prefers-reduced-motion: reduce)",
          ).matches;
          setSpinAnimation({
            key: `${selectedSpin.turn}-${selectedSpin.spinNumber}-${selectedSpin.clubSeasonId}`,
            items: buildSpinItems(
              catalog,
              selectedSpin,
              nextRoom.settings,
              nextRoom.seed,
              nextManager.seat,
            ),
            selected: selectedSpin,
            reducedMotion,
          });
          await new Promise((resolve) =>
            window.setTimeout(resolve, reducedMotion ? 220 : 3650),
          );
          setSpinAnimation(null);
        }
      } catch (spinError) {
        setSpinAnimation(null);
        setError(spinError instanceof Error ? spinError.message : "Kotač se nije zavrtio.");
        await refreshRoom();
      } finally {
        setBusy(false);
      }
    },
    [
      busy,
      catalog,
      lockedSlotId,
      me,
      participantId,
      participantToken,
      refreshRoom,
      room,
    ],
  );

  const pickPlayer = async (player: Player, slotId: string) => {
    if (!room || !me || !participantToken || busy) return;
    clearMessages();
    setBusy(true);
    try {
      const nextRoom = await apiRequest<Room>(
        `/rooms/${room.code}/pick`,
        {
          method: "POST",
          body: JSON.stringify({
            expectedVersion: room.version,
            expectedTurn: me.turn,
            playerSeasonId: player.id,
            slotId,
          }),
        },
        participantToken,
      );
      setRoom(nextRoom);
      setSelectedPlayerId(null);
      setLockedSlotId(null);
    } catch (pickError) {
      setError(pickError instanceof Error ? pickError.message : "Igrač nije odabran.");
      await refreshRoom();
    } finally {
      setBusy(false);
    }
  };

  const movePick = async (fromSlotId: string, toSlotId: string, swap: boolean) => {
    if (!room || !participantToken || busy) return;
    clearMessages();
    setBusy(true);
    try {
      setRoom(
        await apiRequest<Room>(
          `/rooms/${room.code}/move`,
          {
            method: "POST",
            body: JSON.stringify({
              expectedVersion: room.version,
              fromSlotId,
              toSlotId,
              swap,
            }),
          },
          participantToken,
        ),
      );
      setMoveFromSlotId(null);
      setRepositioning(false);
    } catch (moveError) {
      setError(
        moveError instanceof Error
          ? moveError.message
          : "Igrača nije moguće premjestiti.",
      );
      setMoveFromSlotId(null);
      await refreshRoom();
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (activeScreen !== "draft" || currentSpin || busy) return;
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        event.code !== "Space" ||
        target?.tagName === "INPUT" ||
        target?.tagName === "BUTTON" ||
        target?.tagName === "SELECT"
      ) {
        return;
      }
      event.preventDefault();
      void spin(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeScreen, busy, currentSpin, spin]);

  const copyInvite = async () => {
    if (!room) return;
    const url = new URL(window.location.href);
    url.searchParams.set("room", room.code);
    try {
      await navigator.clipboard.writeText(url.toString());
      setNotice("Pozivnica je kopirana.");
    } catch {
      setNotice(`Kod sobe: ${room.code}`);
    }
  };

  const newGame = () => {
    window.sessionStorage.removeItem("hnl-room-session");
    const url = new URL(window.location.href);
    url.searchParams.delete("room");
    window.history.replaceState({}, "", url);
    setRoom(null);
    setParticipantToken("");
    setParticipantId("");
    setSelectedPlayerId(null);
    setLockedSlotId(null);
    setRepositioning(false);
    setMoveFromSlotId(null);
    setSpinAnimation(null);
    setSeasonPhase("preview");
    setRevealedWeek(0);
    setSimulationSpeed("normal");
    setError("");
    setNotice("");
    setScreen("home");
  };

  const goHome = () => {
    if (room && room.status !== "complete") {
      setNotice("Aktivna soba je sačuvana u ovom pregledniku.");
    }
    setScreen(room ? (room.status === "lobby" ? "lobby" : "draft") : "home");
  };

  const renderHome = () => (
    <main id="main-content" className="home-screen">
      <section className="home-hero">
        <div className="hero-copy">
          <p className="eyebrow">HRVATSKA LIGA · 1995/96 — 2025/26</p>
          <h1>
            Zavrti sezonu.
            <span>Složi XI.</span>
          </h1>
          <p className="hero-lead">
            Isti društveni draft ritam koji tražiš: klub i točna sezona, stvarna
            momčad te jedan izbor po krugu. Igraj sam ili otvori live sobu za
            četvero.
          </p>
          <div className="hero-metrics" aria-label="Pokrivenost kataloga">
            <div>
              <strong>
                {formatNumber(catalog?.metadata?.clubSeasonCount, "207")}
              </strong>
              <span>klub-sezona</span>
            </div>
            <div>
              <strong>
                {formatNumber(catalog?.metadata?.playerSeasonCount, "4.400+")}
              </strong>
              <span>igrač-zapisa</span>
            </div>
            <div>
              <strong>31</strong>
              <span>HNL sezona</span>
            </div>
          </div>
        </div>

        <div className="entry-card">
          <div className="entry-card-top">
            <span>01</span>
            <div>
              <p>MENADŽER</p>
              <h2>Kako želiš igrati?</h2>
            </div>
          </div>
          <label className="field-label" htmlFor="manager-name">
            Tvoje ime
          </label>
          <input
            id="manager-name"
            className="text-input"
            value={managerName}
            onChange={(event) => setManagerName(event.target.value)}
            maxLength={40}
            placeholder="npr. Josip"
            autoComplete="nickname"
          />
          <div className="mode-grid">
            <button
              className="mode-card primary"
              onClick={() => chooseMode("live")}
            >
              <span className="live-badge">
                <i aria-hidden="true" /> UŽIVO
              </span>
              <strong>Live draft</strong>
              <small>2–4 prijatelja · svi biraju istodobno</small>
              <b aria-hidden="true">→</b>
            </button>
            <button className="mode-card" onClick={() => chooseMode("solo")}>
              <span className="solo-badge">SOLO</span>
              <strong>Igraj sam</strong>
              <small>Ista pravila · vlastitim tempom</small>
              <b aria-hidden="true">→</b>
            </button>
          </div>
          <form className="join-row" onSubmit={joinRoom}>
            <label htmlFor="join-code">Imaš kod sobe?</label>
            <div>
              <input
                id="join-code"
                value={joinCode}
                onChange={(event) =>
                  setJoinCode(
                    event.target.value
                      .toUpperCase()
                      .replace(/[^A-Z0-9]/g, "")
                      .slice(0, 6),
                  )
                }
                placeholder="ABC123"
                aria-label="Šesteroznamenkasti kod sobe"
              />
              <button type="submit" disabled={busy}>
                Pridruži se
              </button>
            </div>
          </form>
        </div>
      </section>

      <section className="how-strip" aria-labelledby="how-title">
        <p id="how-title">JEDANAEST KRUGOVA. JEDNA MOMČAD.</p>
        {[
          ["01", "Zavrti", "Kotač bira samo klub-sezonu koja je tada igrala HNL."],
          ["02", "Odaberi", "Dobivaš popis igrača upravo te povijesne momčadi."],
          ["03", "Postavi", "Smjesti igrača na kompatibilno mjesto u formaciji."],
          ["04", "Simuliraj", "Nakon XI odigraj reproducibilnu HNL sezonu."],
        ].map(([number, title, copy]) => (
          <article key={number}>
            <span>{number}</span>
            <h3>{title}</h3>
            <p>{copy}</p>
          </article>
        ))}
      </section>

      <section className="data-note">
        <span>PROVJERENO PRAVILO</span>
        <p>
          Klub ulazi u kotač samo za sezone u kojima je igrao najviši rang.
          Primjerice, službeni HNS zapis potvrđuje HNK Vukovar 1991 u sezoni
          2025/26. Rani arhiv zasad uključuje službene šampionske momčadi, a ne
          glumi da je svaka povijesna registracija već potpuna.
        </p>
      </section>
    </main>
  );

  const renderSetup = () => {
    const previewSlots = FORMATION_PREVIEWS[setup.formation] ?? [];
    const previewObjects: Slot[] = previewSlots.map((label, index) => ({
      id: `${label}-${index}`,
      label,
      category:
        label === "GK"
          ? "GK"
          : ["RB", "LB", "CB", "RWB", "LWB"].some((value) =>
                label.includes(value),
              )
            ? "DEF"
            : ["ST", "RW", "LW"].some((value) => label.includes(value))
              ? "FWD"
              : "MID",
      acceptedPositions: [],
    }));
    return (
      <main id="main-content" className="setup-screen">
        <div className="setup-intro">
          <button className="back-button" onClick={() => setScreen("home")}>
            ← Natrag
          </button>
          <p className="eyebrow">
            {mode === "live" ? "LIVE SOBA" : "SOLO DRAFT"} · POSTAVKE
          </p>
          <h1>Postavi pravila.</h1>
          <p>
            Formacija se zaključava nakon početka. Svaki kotač daje jedan
            klub-sezonu i samo igrače te momčadi.
          </p>
        </div>

        <div className="setup-layout">
          <section className="settings-panel">
            <SectionTitle
              index="01"
              title="Formacija"
              copy="Dvanaest rasporeda kao u izvornom draft toku."
            />
            <div className="formation-grid" role="group" aria-label="Formacija">
              {FORMATIONS.map((formation) => (
                <Toggle
                  key={formation}
                  active={setup.formation === formation}
                  onClick={() =>
                    setSetup((current) => ({ ...current, formation }))
                  }
                >
                  {formation}
                </Toggle>
              ))}
            </div>

            <SectionTitle index="02" title="Težina" />
            <div className="difficulty-grid">
              {[
                ["easy", "Lako", "3 ponavljanja"],
                ["normal", "Normalno", "1 ponavljanje"],
                ["hard", "Teško", "bez ponavljanja · skrivene ocjene"],
              ].map(([value, title, copy]) => (
                <button
                  type="button"
                  key={value}
                  className={`difficulty-card${
                    setup.difficulty === value ? " active" : ""
                  }`}
                  aria-pressed={setup.difficulty === value}
                  onClick={() =>
                    setSetup((current) => ({
                      ...current,
                      difficulty: value as Difficulty,
                      showRatings:
                        value === "hard" ? false : current.showRatings,
                    }))
                  }
                >
                  <strong>{title}</strong>
                  <span>{copy}</span>
                </button>
              ))}
            </div>

            <div className="settings-two-column">
              <div>
                <SectionTitle index="03" title="Tijek drafta" />
                <div className="stacked-toggles">
                  <Toggle
                    active={setup.draftMode === "squad-first"}
                    onClick={() =>
                      setSetup((current) => ({
                        ...current,
                        draftMode: "squad-first",
                      }))
                    }
                  >
                    <strong>Momčad prvo</strong>
                    <small>Zavrti, odaberi igrača, pa poziciju</small>
                  </Toggle>
                  <Toggle
                    active={setup.draftMode === "position-first"}
                    onClick={() =>
                      setSetup((current) => ({
                        ...current,
                        draftMode: "position-first",
                      }))
                    }
                  >
                    <strong>Pozicija prvo</strong>
                    <small>Odaberi mjesto, zatim zavrti</small>
                  </Toggle>
                </div>
              </div>
              <div>
                <SectionTitle index="04" title="Ocjene" />
                <div className="stacked-toggles">
                  <Toggle
                    active={setup.ratingsMode === "season"}
                    onClick={() =>
                      setSetup((current) => ({
                        ...current,
                        ratingsMode: "season",
                      }))
                    }
                  >
                    <strong>Ta sezona</strong>
                    <small>Učinak baš u izvučenoj godini</small>
                  </Toggle>
                  <Toggle
                    active={setup.ratingsMode === "prime"}
                    onClick={() =>
                      setSetup((current) => ({
                        ...current,
                        ratingsMode: "prime",
                      }))
                    }
                  >
                    <strong>Prime</strong>
                    <small>Najviša HNL ocjena igrača</small>
                  </Toggle>
                </div>
              </div>
            </div>

            <SectionTitle
              index="05"
              title="Era"
              copy="Kotač nikad ne spaja klub s godinom u kojoj nije igrao HNL."
            />
            <div className="season-range">
              <label>
                Od
                <select
                  value={setup.seasonStart}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    setSetup((current) => ({
                      ...current,
                      seasonStart: value,
                      seasonEnd: Math.max(current.seasonEnd, value),
                    }));
                  }}
                >
                  {seasonYears.map((year) => (
                    <option key={year} value={year}>
                      {year}/{String(year + 1).slice(-2)}
                    </option>
                  ))}
                </select>
              </label>
              <span aria-hidden="true">—</span>
              <label>
                Do
                <select
                  value={setup.seasonEnd}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    setSetup((current) => ({
                      ...current,
                      seasonEnd: value,
                      seasonStart: Math.min(current.seasonStart, value),
                    }));
                  }}
                >
                  {seasonYears.map((year) => (
                    <option key={year} value={year}>
                      {year}/{String(year + 1).slice(-2)}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="inline-options">
              <label className="switch-row">
                <span>
                  <strong>Prikaži ocjene</strong>
                  <small>Teška razina ih uvijek skriva</small>
                </span>
                <input
                  type="checkbox"
                  checked={setup.showRatings && setup.difficulty !== "hard"}
                  disabled={setup.difficulty === "hard"}
                  onChange={(event) =>
                    setSetup((current) => ({
                      ...current,
                      showRatings: event.target.checked,
                    }))
                  }
                />
                <i aria-hidden="true" />
              </label>
              {mode === "live" ? (
                <label className="player-count">
                  <span>
                    <strong>Broj mjesta</strong>
                    <small>Sobu možeš pokrenuti i prije nego se popuni</small>
                  </span>
                  <select
                    value={setup.maxPlayers}
                    onChange={(event) =>
                      setSetup((current) => ({
                        ...current,
                        maxPlayers: Number(event.target.value),
                      }))
                    }
                  >
                    {[2, 3, 4].map((count) => (
                      <option key={count} value={count}>
                        {count}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
            </div>

            <button
              className="cta-button"
              onClick={createGame}
              disabled={busy}
            >
              {busy
                ? "Stvaram sobu…"
                : mode === "live"
                  ? "Otvori live sobu"
                  : "Započni draft"}
              <span aria-hidden="true">→</span>
            </button>
          </section>

          <aside className="formation-preview">
            <div className="preview-heading">
              <span>TAKTIČKA PLOČA</span>
              <strong>{setup.formation}</strong>
            </div>
            <div className="mini-pitch" aria-label={`Pregled ${setup.formation}`}>
              <div className="pitch-markings" aria-hidden="true" />
              {previewObjects.map((slot) => {
                const point = slotPoint(
                  slot,
                  previewObjects,
                  setup.formation,
                );
                return (
                  <span
                    key={slot.id}
                    className={`preview-slot ${slot.category.toLowerCase()}`}
                    style={
                      {
                        "--slot-x": `${point.x}%`,
                        "--slot-y": `${point.y}%`,
                      } as CSSProperties
                    }
                  >
                    {slot.label}
                  </span>
                );
              })}
            </div>
            <dl className="setup-summary">
              <div>
                <dt>Način</dt>
                <dd>{mode === "live" ? "Live draft" : "Solo"}</dd>
              </div>
              <div>
                <dt>Era</dt>
                <dd>
                  {setup.seasonStart}/{String(setup.seasonStart + 1).slice(-2)}—
                  {setup.seasonEnd}/{String(setup.seasonEnd + 1).slice(-2)}
                </dd>
              </div>
              <div>
                <dt>Ocjena</dt>
                <dd>{setup.ratingsMode === "prime" ? "Prime" : "Ta sezona"}</dd>
              </div>
              <div>
                <dt>Ponavljanja</dt>
                <dd>
                  {setup.difficulty === "easy"
                    ? 3
                    : setup.difficulty === "normal"
                      ? 1
                      : 0}
                </dd>
              </div>
            </dl>
            <p className="preview-disclosure">
              Ocjene su izvorni urednički model igre, ne službene ocjene HNS-a,
              Transfermarkta niti kladioničarska prognoza.
            </p>
          </aside>
        </div>
      </main>
    );
  };

  const renderLobby = () => {
    if (!room || !me) return null;
    return (
      <main id="main-content" className="lobby-screen">
        <section className="lobby-card">
          <div className="lobby-kicker">
            <span className="pulse-dot" aria-hidden="true" />
            LIVE LOBBY
          </div>
          <p>POZOVI PRIJATELJE</p>
          <h1>{room.code}</h1>
          <p className="lobby-copy">
            Pošalji ovaj kod ili kopiraj izravnu poveznicu. Svi menadžeri vrte i
            biraju istodobno.
          </p>
          <button className="copy-button" onClick={copyInvite}>
            Kopiraj pozivnicu <span aria-hidden="true">⧉</span>
          </button>

          <div className="lobby-divider">
            <span />
            MENADŽERI {room.participants.length}/{room.settings.maxPlayers}
            <span />
          </div>
          <div className="manager-grid">
            {Array.from({ length: room.settings.maxPlayers }).map((_, index) => {
              const manager = room.participants[index];
              return manager ? (
                <article className="manager-card joined" key={manager.id}>
                  <span>{managerInitials(manager.name)}</span>
                  <div>
                    <strong>{manager.name}</strong>
                    <small>{manager.isHost ? "Domaćin" : `Mjesto ${manager.seat}`}</small>
                  </div>
                  <i aria-label="Spreman">✓</i>
                </article>
              ) : (
                <article className="manager-card empty" key={`empty-${index}`}>
                  <span>+</span>
                  <div>
                    <strong>Čeka igrača</strong>
                    <small>Pošalji kod sobe</small>
                  </div>
                </article>
              );
            })}
          </div>

          <div className="lobby-rules">
            <span>{room.settings.formation}</span>
            <span>
              {room.settings.seasonStart}/{String(room.settings.seasonStart + 1).slice(-2)}
              —{room.settings.seasonEnd}/
              {String(room.settings.seasonEnd + 1).slice(-2)}
            </span>
            <span>{room.settings.ratingsMode === "prime" ? "Prime" : "Sezona"}</span>
            <span>{room.settings.rerolls} ponavljanja</span>
          </div>

          {me.isHost ? (
            <button
              className="cta-button lobby-start"
              onClick={startLiveDraft}
              disabled={busy}
            >
              {busy ? "Pokrećem…" : "Pokreni live draft"}
              <span aria-hidden="true">→</span>
            </button>
          ) : (
            <div className="waiting-message">
              <span className="spinner" aria-hidden="true" />
              Domaćin će pokrenuti draft
            </div>
          )}
        </section>
      </main>
    );
  };

  const renderPitch = () => {
    if (!room || !me) return null;
    return (
      <div className="draft-pitch" aria-label={`Formacija ${room.settings.formation}`}>
        <div className="pitch-markings" aria-hidden="true" />
        {room.settings.slots.map((slot) => {
          const point = slotPoint(
            slot,
            room.settings.slots,
            room.settings.formation,
          );
          const pick = me.picks.find((item) => item.slotId === slot.id);
          const playerCanFill = selectedPlayer?.eligibleSlotIds?.includes(slot.id);
          const canChoosePosition =
            room.settings.draftMode === "position-first" && !currentSpin && !pick;
          const interactive = Boolean(
            playerCanFill || canChoosePosition || (repositioning && me.picks.length),
          );
          const isLocked = lockedSlotId === slot.id;
          const isMoveSource = moveFromSlotId === slot.id;
          return (
            <button
              key={slot.id}
              type="button"
              className={[
                "pitch-slot",
                pick ? "filled" : "empty",
                interactive ? "interactive" : "",
                playerCanFill ? "eligible" : "",
                isLocked ? "locked" : "",
                isMoveSource ? "move-source" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              style={
                {
                  "--slot-x": `${point.x}%`,
                  "--slot-y": `${point.y}%`,
                  "--club-accent":
                    pick?.clubSeason.club.accent ?? "var(--lime)",
                } as CSSProperties
              }
              disabled={!interactive || busy}
              onClick={() => {
                if (playerCanFill && selectedPlayer) {
                  void pickPlayer(selectedPlayer, slot.id);
                } else if (repositioning) {
                  if (!moveFromSlotId) {
                    if (pick) {
                      setMoveFromSlotId(slot.id);
                      setNotice("Sada odaberi odredišno mjesto.");
                    }
                  } else if (moveFromSlotId !== slot.id) {
                    void movePick(moveFromSlotId, slot.id, Boolean(pick));
                  }
                } else if (canChoosePosition) {
                  setLockedSlotId(slot.id);
                  setError("");
                }
              }}
              aria-label={
                pick
                  ? `${slot.label}: ${pick.player.name}`
                  : isLocked
                    ? `${slot.label}, odabrano za sljedeći kotač`
                    : `Prazno mjesto ${slot.label}`
              }
            >
              {pick ? (
                <>
                  <span className="player-initials">
                    {managerInitials(pick.player.name)}
                  </span>
                  <strong>{surname(pick.player.name)}</strong>
                  <small>
                    {slot.label}
                    {typeof pick.selectedRating === "number"
                      ? ` · ${Math.round(pick.selectedRating)}`
                      : ""}
                  </small>
                </>
              ) : (
                <>
                  <span>+</span>
                  <strong>{slot.label}</strong>
                  <small>{isLocked ? "SLJEDEĆI" : "PRAZNO"}</small>
                </>
              )}
            </button>
          );
        })}
      </div>
    );
  };

  const renderDraft = () => {
    if (!room || !me) return null;
    const remaining = room.settings.targetPicks - me.picks.length;
    return (
      <main id="main-content" className="draft-screen">
        <section className="draft-statusbar">
          <div className="manager-progress">
            {room.participants.map((participant) => (
              <article
                key={participant.id}
                className={participant.id === me.id ? "active" : ""}
              >
                <span>{managerInitials(participant.name)}</span>
                <div>
                  <strong>{participant.name}</strong>
                  <small>
                    {participant.picks.length}/{room.settings.targetPicks} odabrano
                  </small>
                </div>
                <progress
                  max={room.settings.targetPicks}
                  value={participant.picks.length}
                  aria-label={`${participant.name}: ${participant.picks.length} od ${room.settings.targetPicks}`}
                />
              </article>
            ))}
          </div>
          <div className="draft-meta">
            <span>FORMACIJA</span>
            <strong>{room.settings.formation}</strong>
          </div>
        </section>

        <div className="draft-layout">
          <section className="pitch-panel">
            <div className="pitch-panel-heading">
              <div>
                <span>TVOJA JEDANAESTORKA</span>
                <h2>{managerName || me.name}</h2>
              </div>
              <div className="round-counter">
                <strong>{me.picks.length}</strong>
                <span>/ {room.settings.targetPicks}</span>
              </div>
            </div>
            {renderPitch()}
            {me.picks.length > 0 && room.status === "drafting" ? (
              <div className="move-controls">
                <button
                  type="button"
                  className={repositioning ? "active" : ""}
                  onClick={() => {
                    setRepositioning((current) => !current);
                    setMoveFromSlotId(null);
                    setSelectedPlayerId(null);
                    setNotice(
                      repositioning
                        ? ""
                        : "Odaberi igrača na terenu, zatim prazno mjesto ili igrača za zamjenu.",
                    );
                  }}
                >
                  ⇄ {repositioning ? "Odustani od premještanja" : "Premjesti igrača"}
                </button>
              </div>
            ) : null}
            <div className="team-rating-row">
              <div>
                <span>UKUPNO</span>
                <strong>
                  {typeof me.squadRating === "number"
                    ? Math.round(me.squadRating)
                    : "—"}
                </strong>
              </div>
              {(["GK", "DEF", "MID", "FWD"] as const).map((category) => {
                const values = me.picks
                  .filter((pick) => {
                    const slot = room.settings.slots.find(
                      (item) => item.id === pick.slotId,
                    );
                    return slot?.category === category;
                  })
                  .map((pick) => pick.selectedRating)
                  .filter((value): value is number => typeof value === "number");
                const average = values.length
                  ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
                  : null;
                return (
                  <div key={category}>
                    <span>{category}</span>
                    <strong>{average ?? "—"}</strong>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="wheel-panel">
            {spinAnimation ? (
              <ClubSeasonReel animation={spinAnimation} />
            ) : me.status === "complete" && room.status === "drafting" ? (
              <div className="spin-state draft-waiting">
                <div className="round-label">TVA XI JE SPREMNA</div>
                <p className="eyebrow">LIVE SOBA {room.code}</p>
                <h2>Čekamo ostale menadžere.</h2>
                <div className="waiting-ball" aria-hidden="true">
                  ✓
                </div>
                <p>
                  Rezultati se otključavaju čim svi dovrše svojih{" "}
                  {room.settings.targetPicks} izbora.
                </p>
                <div className="waiting-roster">
                  {room.participants.map((participant) => (
                    <span key={participant.id}>
                      <strong>{participant.name}</strong>
                      {participant.picks.length}/{room.settings.targetPicks}
                    </span>
                  ))}
                </div>
              </div>
            ) : !currentSpin ? (
              <div className="spin-state">
                <div className="round-label">
                  KRUG {String(me.turn + 1).padStart(2, "0")} /{" "}
                  {room.settings.targetPicks}
                </div>
                <p className="eyebrow">
                  {room.settings.draftMode === "position-first"
                    ? lockedSlotId
                      ? `POZICIJA ${room.settings.slots.find((slot) => slot.id === lockedSlotId)?.label}`
                      : "ODABERI POZICIJU NA TERENU"
                    : "ZAVRTI ZA MOMČAD"}
                </p>
                <h2>{remaining} mjesta do XI</h2>
                <div className={`wheel-window${busy ? " spinning" : ""}`}>
                  <span>KLUB</span>
                  <i>×</i>
                  <span>SEZONA</span>
                </div>
                <button
                  className="spin-button"
                  onClick={() => void spin(false)}
                  disabled={
                    busy ||
                    (room.settings.draftMode === "position-first" && !lockedSlotId)
                  }
                >
                  <span aria-hidden="true">✦</span>
                  {busy ? "Kotač se vrti…" : "Zavrti kotač"}
                </button>
                <p className="keyboard-hint">ili pritisni Space</p>
                <div className="reroll-display">
                  <span>Ponavljanja</span>
                  <strong>{me.rerollsRemaining}</strong>
                </div>
              </div>
            ) : (
              <div
                className="squad-state"
                style={
                  {
                    "--spin-accent": currentSpin.club.accent ?? "var(--lime)",
                  } as CSSProperties
                }
              >
                <div className="spin-result-head">
                  <div className="spun-club-identity">
                    <ClubShield club={currentSpin.club} />
                    <div className="spun-club-copy">
                      <span>IZVUČENA MOMČAD</span>
                      <h2>{currentSpin.club.name}</h2>
                      <strong>{currentSpin.season.label}</strong>
                    </div>
                  </div>
                  <div className="spin-head-actions">
                    <span className="rating-mode">
                      {room.settings.ratingsMode === "prime" ? "PRIME" : "SEZONA"}
                    </span>
                    <button
                      onClick={() => void spin(true)}
                      disabled={busy || me.rerollsRemaining <= 0}
                    >
                      ↻ Ponovi ({me.rerollsRemaining})
                    </button>
                  </div>
                </div>
                <div className="squad-instruction">
                  <span>{currentSpin.players?.length ?? 0} igrača</span>
                  <p>
                    {room.settings.draftMode === "position-first"
                      ? `Odaberi igrača za ${room.settings.slots.find((slot) => slot.id === currentSpin.lockedSlotId)?.label ?? "poziciju"}.`
                      : "Odaberi igrača, zatim kompatibilno prazno mjesto."}
                  </p>
                </div>
                <div className="sort-row">
                  <span>SORTIRAJ</span>
                  {[
                    ["rating", "Ocjena"],
                    ["position", "Pozicija"],
                    ["surname", "Prezime A–Ž"],
                  ].map(([value, label]) => (
                    <button
                      key={value}
                      className={sortMode === value ? "active" : ""}
                      aria-pressed={sortMode === value}
                      onClick={() => setSortMode(value as SortMode)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <div className="player-list">
                  {sortedPlayers.map((player) => {
                    const isSelected = selectedPlayerId === player.id;
                    return (
                      <article
                        key={player.id}
                        className={[
                          "player-row",
                          player.available ? "" : "unavailable",
                          isSelected ? "selected" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                      >
                        <button
                          className="player-main"
                          disabled={!player.available || busy}
                          aria-expanded={isSelected}
                          onClick={() =>
                            setSelectedPlayerId(isSelected ? null : player.id)
                          }
                        >
                          <span className="player-rating">
                            {typeof player.rating === "number"
                              ? Math.round(player.rating)
                              : "—"}
                          </span>
                          <span className="player-name">
                            <strong>{player.name}</strong>
                            <small>
                              {player.nationality || "—"} · {playerStatLine(player)}
                            </small>
                          </span>
                          <span className="position-tags">
                            {player.positions.slice(0, 3).map((position) => (
                              <i key={position}>{position}</i>
                            ))}
                          </span>
                          <b aria-hidden="true">{isSelected ? "−" : "+"}</b>
                        </button>
                        {isSelected ? (
                          <div className="placement-row">
                            <span>POSTAVI NA</span>
                            {(player.eligibleSlotIds ?? []).map((slotId) => {
                              const slot = room.settings.slots.find(
                                (item) => item.id === slotId,
                              );
                              return (
                                <button
                                  key={slotId}
                                  onClick={() => void pickPlayer(player, slotId)}
                                  disabled={busy}
                                >
                                  {slot?.label ?? slotId}
                                </button>
                              );
                            })}
                          </div>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              </div>
            )}
          </section>
        </div>
      </main>
    );
  };

  const startSeasonSimulation = () => {
    activeMatchRef.current = { key: "", minute: 0 };
    setRevealedWeek(0);
    setActiveMatchClock({ key: "", minute: 0 });
    setSimulationSpeed("normal");
    setSeasonPhase(seasonMatches.length ? "running" : "final");
  };

  const shareSeason = async () => {
    if (!room || !me?.result) return;
    const finish = finishLabel(me.result.finalPosition);
    const text = `36–0 HNL: ${me.name} — ${finish} mjesto, ${me.result.points} bodova (${me.result.wins}-${me.result.draws}-${me.result.losses}).`;
    try {
      if (navigator.share) {
        await navigator.share({ title: "36–0 HNL", text, url: window.location.href });
      } else {
        await navigator.clipboard.writeText(`${text} ${window.location.href}`);
        setNotice("Rezultat je kopiran.");
      }
    } catch {
      setNotice("Dijeljenje je otkazano.");
    }
  };

  const renderResults = () => {
    if (!room || !me) return null;
    const result =
      me.result ?? simulateSeason(me.squadRating, room.seed, me.seat);
    const projection =
      result.projection ?? fallbackProjection(me.squadRating);
    const ranked = room.participants
      .map((participant) => ({
        participant,
        result:
          participant.result ??
          simulateSeason(participant.squadRating, room.seed, participant.seat),
      }))
      .sort(
        (a, b) =>
          b.result.points - a.result.points ||
          b.result.goalDifference - a.result.goalDifference ||
          b.result.goalsFor - a.result.goalsFor ||
          a.participant.name.localeCompare(b.participant.name),
      );
    const categoryAverage = (category: Slot["category"]) => {
      const ratings = me.picks
        .filter((pick) => {
          const slot = room.settings.slots.find((item) => item.id === pick.slotId);
          return slot?.category === category;
        })
        .map((pick) => pick.selectedRating)
        .filter((value): value is number => typeof value === "number");
      return ratings.length
        ? Math.round(ratings.reduce((sum, value) => sum + value, 0) / ratings.length)
        : null;
    };

    if (seasonPhase === "preview") {
      return (
        <main id="main-content" className="season-preview-screen">
          <section className="season-squad-panel">
            <div className="season-panel-heading">
              <div>
                <p className="eyebrow">JEDANAESTORKA ZAVRŠENA</p>
                <h1>{me.name}</h1>
                <span>{room.settings.formation}</span>
              </div>
              <strong>{Math.round(me.squadRating ?? result.averageRating ?? 70)}</strong>
            </div>
            <div className="result-pitch">{renderPitch()}</div>
            <div className="line-strengths">
              {[
                ["GK", "Vratar", categoryAverage("GK")],
                ["DEF", "Obrana", categoryAverage("DEF")],
                ["MID", "Vezni red", categoryAverage("MID")],
                ["FWD", "Napad", categoryAverage("FWD")],
              ].map(([key, label, value]) => (
                <div key={String(key)}>
                  <span>{label}</span>
                  <strong>{value ?? "—"}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="preseason-panel">
            <span className="preseason-kicker">PREDSEZONSKA PROJEKCIJA</span>
            <div className="preseason-mark" aria-hidden="true">
              36
            </div>
            <h2>Može li ova XI do savršene sezone?</h2>
            <p>
              Model je već zaključao svih 36 kola. Animacija samo otkriva
              reproducibilan rezultat, utakmicu po utakmicu.
            </p>
            <div className="projection-grid">
              <div className="projection-primary">
                <span>PROJEKCIJA</span>
                <strong>{finishLabel(projection.projectedPosition)}</strong>
                <small>mjesto</small>
              </div>
              <div>
                <span>OČEKIVANI BODOVI</span>
                <strong>{Math.round(projection.expectedPoints)}</strong>
              </div>
              <div>
                <span>NASLOV</span>
                <strong>{probability(projection.titleProbability)}</strong>
              </div>
              <div>
                <span>TOP 4</span>
                <strong>{probability(projection.topFourProbability)}</strong>
              </div>
              <div>
                <span>SAVRŠENIH 36–0</span>
                <strong>{probability(projection.perfectProbability)}</strong>
              </div>
            </div>
            <button className="season-start-button" onClick={startSeasonSimulation}>
              Simuliraj sezonu <span>→</span>
            </button>
            <small className="projection-disclosure">
              Vjerojatnosti su urednički model igre, ne službena prognoza niti
              kvote za klađenje.
            </small>
          </section>
        </main>
      );
    }

    if (seasonPhase === "running") {
      const visibleMatches = seasonMatches.slice(0, revealedWeek);
      const running =
        visibleMatches.at(-1)?.running ?? aggregateMatches(visibleMatches);
      const activeMatch = seasonMatches[revealedWeek];
      const activeManagerFixture = isManagerFixture(
        activeMatch,
        participantIds,
      );
      const activeMatchKey = activeMatch
        ? `${activeMatch.matchweek}:${activeMatch.opponent.id}`
        : "";
      const displayedActiveMatchMinute =
        activeMatchClock.key === activeMatchKey
          ? activeMatchClock.minute
          : 0;
      const latestMatches = visibleMatches
        .slice(activeManagerFixture ? -2 : -3)
        .reverse();
      const currentRound = Math.min(
        seasonMatches.length,
        revealedWeek + (revealedWeek < seasonMatches.length ? 1 : 0),
      );
      const progressWeeks =
        revealedWeek +
        (activeManagerFixture
          ? Math.min(90, displayedActiveMatchMinute) / 90
          : 0);
      const progress = seasonMatches.length
        ? (progressWeeks / seasonMatches.length) * 100
        : 0;
      return (
        <main id="main-content" className="simulation-screen">
          <section className="simulation-team-rail">
            <div className="simulation-team-head">
              <div>
                <span>TVA XI</span>
                <h2>{me.name}</h2>
              </div>
              <strong>{Math.round(me.squadRating ?? result.averageRating ?? 70)}</strong>
            </div>
            <div className="simulation-mini-pitch">{renderPitch()}</div>
            <p>
              {room.settings.formation} · {room.settings.ratingsMode === "prime" ? "prime" : "sezonske"} ocjene
            </p>
          </section>

          <section className="matchweek-console">
            <header className="matchweek-header">
              <div>
                <span>SIMULACIJA UŽIVO</span>
                <h1>
                  Kolo {currentRound} <i>/ {seasonMatches.length || 36}</i>
                </h1>
              </div>
              <div className="simulation-controls">
                {revealedWeek < 18 ? (
                  <button onClick={() => setRevealedWeek(Math.min(18, seasonMatches.length))}>
                    Do zimske stanke
                  </button>
                ) : null}
                <button
                  className={simulationSpeed === "fast" ? "active" : ""}
                  onClick={() =>
                    setSimulationSpeed((current) =>
                      current === "normal" ? "fast" : "normal",
                    )
                  }
                >
                  {simulationSpeed === "fast" ? "Brzo ×3" : "Ubrzaj"}
                </button>
                <button
                  onClick={() => {
                    activeMatchRef.current = { key: "", minute: 0 };
                    setActiveMatchClock({ key: "", minute: 0 });
                    setRevealedWeek(seasonMatches.length);
                    setSeasonPhase("final");
                  }}
                >
                  Preskoči sve →
                </button>
              </div>
            </header>
            <div
              className="season-progress"
              aria-label={
                activeManagerFixture
                  ? `${revealedWeek} završenih kola, ${displayedActiveMatchMinute}. minuta sljedeće utakmice`
                  : `${revealedWeek} od 36 kola`
              }
            >
              <i style={{ width: `${progress}%` }} />
            </div>
            <div className="live-match-stack" aria-live="polite">
              {activeManagerFixture && activeMatch ? (
                <>
                  <MatchCard
                    key={`active-${activeMatch.matchweek}`}
                    match={activeMatch}
                    featured
                    revealMinute={displayedActiveMatchMinute}
                  />
                  {latestMatches.map((match) => (
                    <MatchCard key={match.matchweek} match={match} />
                  ))}
                </>
              ) : latestMatches.length ? (
                latestMatches.map((match, index) => (
                  <MatchCard
                    key={match.matchweek}
                    match={match}
                    featured={index === 0}
                  />
                ))
              ) : (
                <div className="kickoff-state">
                  <span aria-hidden="true">●</span>
                  <strong>Prvo kolo upravo počinje…</strong>
                </div>
              )}
            </div>
            <div className="running-scoreboard">
              {[
                ["P", "Pobjede", running.wins],
                ["N", "Neriješeno", running.draws],
                ["I", "Porazi", running.losses],
                ["B", "Bodovi", running.points],
              ].map(([key, label, value]) => (
                <div key={String(key)}>
                  <strong>{value}</strong>
                  <span>{label}</span>
                </div>
              ))}
            </div>
            <p className="running-goals">
              DG {running.goalsFor} · PG {running.goalsAgainst} · GR{" "}
              {running.goalDifference > 0 ? "+" : ""}
              {running.goalDifference}
            </p>
          </section>
        </main>
      );
    }

    const finalPosition = result.finalPosition;
    const perfect = result.awards?.perfectSeason || result.wins === 36;
    const champion = result.awards?.leagueTitle || finalPosition === 1;
    const invincible = result.awards?.invincible || result.losses === 0;
    const headline = perfect
      ? "36–0!"
      : champion
        ? "PRVACI!"
        : `${finishLabel(finalPosition)} MJESTO`;
    const goldenGlove = result.playerStats
      ?.filter((player) => player.positions?.includes("GK"))
      .sort((a, b) => b.cleanSheets - a.cleanSheets)[0];
    const awards = [
      result.awards?.topScorer
        ? {
            icon: "⚽",
            title: "Najbolji strijelac",
            player: result.awards.topScorer.playerName,
            value: `${result.awards.topScorer.goals ?? 0} golova`,
          }
        : null,
      result.awards?.topCreator
        ? {
            icon: "🎯",
            title: "Asistent",
            player: result.awards.topCreator.playerName,
            value: `${result.awards.topCreator.assists ?? 0} asistencija`,
          }
        : null,
      goldenGlove
        ? {
            icon: "🧤",
            title: "Zlatna rukavica",
            player: goldenGlove.playerName,
            value: `${goldenGlove.cleanSheets} bez primljenog gola`,
          }
        : null,
      result.awards?.playerOfSeason
        ? {
            icon: "★",
            title: "Igrač sezone",
            player: result.awards.playerOfSeason.playerName,
            value: `${result.awards.playerOfSeason.goals ?? 0}G · ${result.awards.playerOfSeason.assists ?? 0}A`,
          }
        : null,
    ].filter(
      (
        award,
      ): award is { icon: string; title: string; player: string; value: string } =>
        Boolean(award),
    );

    return (
      <main id="main-content" className="results-screen detailed-results">
        <section className="results-hero">
          <p className="eyebrow">SEZONA ZAVRŠENA</p>
          <span className="trophy-mark" aria-hidden="true">
            {champion ? "★" : "36"}
          </span>
          <h1>{headline}</h1>
          <p>
            {result.wins} pobjeda · {result.draws} neriješenih · {result.losses} poraza
          </p>
          <div className="champion-score">
            <strong>{result.points}</strong>
            <span>BODOVA</span>
          </div>
          <div className="result-hero-actions">
            <button onClick={() => void shareSeason()}>Podijeli sezonu</button>
            <button onClick={newGame}>Nova igra ↗</button>
          </div>
        </section>

        <section className="season-verdict">
          <span>
            {perfect
              ? "NEMOGUĆE JE POSTALO STVARNO"
              : invincible
                ? "NEPORAŽENA SEZONA"
                : champion
                  ? "NASLOV JE OSVOJEN"
                  : "KONAČNI SUD"}
          </span>
          <h2>
            {me.name}: {result.goalsFor} zabijenih, {result.goalsAgainst} primljenih.
          </h2>
          <p>
            Projekcija je bila {finishLabel(projection.projectedPosition)}, a
            ova XI završila je na {finishLabel(finalPosition)} mjestu. Rezultat
            je zaključan prije animacije i njezina brzina ga ne mijenja.
          </p>
          {result.awards?.earned?.length ? (
            <div className="earned-badges">
              {result.awards.earned.map((award) => (
                <span key={award.code}>★ {award.name}</span>
              ))}
            </div>
          ) : null}
        </section>

        <section className="season-record-grid">
          {[
            ["NAJDULJI NIZ POBJEDA", result.records?.longestWinningStreak ?? 0],
            [
              "NAJDULJI NIZ BEZ PORAZA",
              result.records?.longestUnbeatenStreak ?? 0,
            ],
            [
              "NAJVEĆA POBJEDA",
              result.records?.biggestWin
                ? `${result.records.biggestWin.goalsFor}–${result.records.biggestWin.goalsAgainst} vs ${result.records.biggestWin.opponent.name}`
                : "—",
            ],
            [
              "NAJVIŠE GOLOVA",
              result.records?.highestScoringMatch
                ? `${result.records.highestScoringMatch.goalsFor}–${result.records.highestScoringMatch.goalsAgainst} vs ${result.records.highestScoringMatch.opponent.name}`
                : "—",
            ],
          ].map(([label, value]) => (
            <div key={String(label)}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </section>

        {awards.length ? (
          <section className="awards-section">
            <div className="result-heading">
              <div>
                <span>NAGRADE SEZONE</span>
                <h2>Ljudi koji su odlučili sezonu.</h2>
              </div>
            </div>
            <div className="award-grid">
              {awards.map((award) => (
                <article key={award.title}>
                  <i aria-hidden="true">{award.icon}</i>
                  <span>{award.title}</span>
                  <strong>{award.player}</strong>
                  <small>{award.value}</small>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {result.playerStats?.length ? (
          <section className="player-season-section">
            <div className="result-heading">
              <div>
                <span>TVOJA XI</span>
                <h2>Učinak kroz svih 36 kola.</h2>
              </div>
            </div>
            <div className="player-season-table">
              <div className="player-season-row header">
                <span>Poz.</span>
                <span>Igrač</span>
                <span>G</span>
                <span>A</span>
                <span>ČM</span>
                <span>OVR</span>
              </div>
              {result.playerStats
                .slice()
                .sort(
                  (a, b) =>
                    (b.goals + b.assists) - (a.goals + a.assists) ||
                    a.playerName.localeCompare(b.playerName),
                )
                .map((player) => (
                  <div className="player-season-row" key={player.playerId}>
                    <span>{player.slotId?.toUpperCase() ?? player.positions?.[0] ?? "—"}</span>
                    <strong>{player.playerName}</strong>
                    <span>{player.goals || "—"}</span>
                    <span>{player.assists || "—"}</span>
                    <span>{player.cleanSheets || "—"}</span>
                    <b>{player.rating ?? "—"}</b>
                  </div>
                ))}
            </div>
          </section>
        ) : null}

        {result.leagueTable?.length ? (
          <section className="result-table-section league-table-section">
            <div className="result-heading">
              <div>
                <span>KONAČNA TABLICA</span>
                <h2>HNL nakon 36 kola.</h2>
              </div>
            </div>
            <div className="result-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Klub</th>
                    <th>O</th>
                    <th>P</th>
                    <th>N</th>
                    <th>I</th>
                    <th>DG</th>
                    <th>PG</th>
                    <th>GR</th>
                    <th>B</th>
                  </tr>
                </thead>
                <tbody>
                  {result.leagueTable.map((row) => (
                    <tr key={row.teamId} className={row.isDraftedXI ? "winner" : ""}>
                      <td>{row.position}</td>
                      <td>
                        <ClubShield
                          club={{
                            id: row.teamId,
                            name: row.name,
                            shortName: row.shortName,
                            accent: row.accent,
                          }}
                          compact
                        />
                        <strong>{row.isDraftedXI ? me.name : row.name}</strong>
                      </td>
                      <td>{row.played}</td>
                      <td>{row.wins}</td>
                      <td>{row.draws}</td>
                      <td>{row.losses}</td>
                      <td>{row.goalsFor}</td>
                      <td>{row.goalsAgainst}</td>
                      <td>{row.goalDifference > 0 ? "+" : ""}{row.goalDifference}</td>
                      <td><strong>{row.points}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}

        {seasonMatches.length ? (
          <section className="fixtures-section">
            <details>
              <summary>Svih 36 utakmica <span>otvori zapis ↓</span></summary>
              <div className="fixture-grid">
                {seasonMatches.map((match) => (
                  <MatchCard key={match.matchweek} match={match} />
                ))}
              </div>
            </details>
          </section>
        ) : null}

        {ranked.length > 1 ? (
          <section className="result-table-section manager-result-section">
            <div className="result-heading">
              <div>
                <span>SOBA {room.code}</span>
                <h2>Poredak menadžera.</h2>
              </div>
            </div>
            <div className="result-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Menadžer</th>
                    <th>OVR</th>
                    <th>P</th>
                    <th>N</th>
                    <th>I</th>
                    <th>GR</th>
                    <th>B</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map(({ participant, result: managerResult }, index) => (
                    <tr
                      key={participant.id}
                      className={participant.id === me.id ? "winner" : ""}
                    >
                      <td>{index + 1}</td>
                      <td>
                        <span>{managerInitials(participant.name)}</span>
                        <strong>{participant.name}</strong>
                      </td>
                      <td>{participant.squadRating?.toFixed(1) ?? "—"}</td>
                      <td>{managerResult.wins}</td>
                      <td>{managerResult.draws}</td>
                      <td>{managerResult.losses}</td>
                      <td>
                        {managerResult.goalDifference > 0 ? "+" : ""}
                        {managerResult.goalDifference}
                      </td>
                      <td><strong>{managerResult.points}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}

        <section className="result-disclosure">
          <strong>Kako je dobiven rezultat?</strong>
          <p>
            Svih 36 kola, protivnici, strijelci i tablica unaprijed su izvedeni
            na poslužitelju iz zaključane XI. Brzina animacije ne mijenja ishod.
            Model je urednička igra, ne službena HNS prognoza.
          </p>
        </section>
      </main>
    );
  };

  const stage =
    activeScreen === "home"
      ? "POČETAK"
      : activeScreen === "setup"
        ? "POSTAVKE"
        : activeScreen === "lobby"
          ? "SOBA"
          : activeScreen === "draft"
            ? `DRAFT ${me ? `${me.picks.length}/11` : ""}`
            : seasonPhase === "preview"
              ? "PREDSEZONA"
              : seasonPhase === "running"
                ? `SIMULACIJA ${revealedWeek}/${seasonMatches.length || 36}`
                : "REZULTATI";

  return (
    <div className="site-shell">
      <a className="skip-link" href="#main-content">
        Preskoči na sadržaj
      </a>
      <Header stage={stage} room={room} onHome={goHome} />
      <div className="status-announcer" aria-live="polite">
        {error || notice}
      </div>
      {(error || notice) && (
        <div className={`toast${error ? " error" : ""}`} role={error ? "alert" : "status"}>
          <span>{error || notice}</span>
          <button
            aria-label="Zatvori poruku"
            onClick={() => {
              setError("");
              setNotice("");
            }}
          >
            ×
          </button>
        </div>
      )}
      {activeScreen === "home" ? renderHome() : null}
      {activeScreen === "setup" ? renderSetup() : null}
      {activeScreen === "lobby" ? renderLobby() : null}
      {activeScreen === "draft" ? renderDraft() : null}
      {activeScreen === "results" ? renderResults() : null}
      <footer className="site-footer">
        <p>
          36–0 je nezavisna fan-made HNL draft igra. Nije povezana s HNS-om,
          klubovima, igračima ili pružateljima ocjena. Grbovi se prikazuju
          isključivo radi identifikacije i ostaju vlasništvo svojih nositelja.
        </p>
        <span>Podaci: HNS Riznica / COMET + sekundarni povijesni izvori</span>
      </footer>
    </div>
  );
}
