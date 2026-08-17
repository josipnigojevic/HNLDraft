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

type AccountStats = {
  seasonsPlayed: number;
  titles: number;
  wins: number;
  draws: number;
  losses: number;
  points: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDifference: number;
  averagePoints?: number | null;
  bestPoints?: number | null;
  bestFinish?: number | null;
  averageFinish?: number | null;
  winRate?: number | null;
  perfectSeasons?: number;
  invincibleSeasons?: number;
};

type Account = {
  id: string;
  username: string;
  email?: string | null;
  displayName?: string | null;
  createdAt?: string | null;
  stats?: Partial<AccountStats> | null;
};

type SeasonHistoryEntry = {
  id: string;
  roomCode?: string | null;
  seasonId?: string | null;
  mode?: GameMode | null;
  managerName?: string | null;
  formation?: string | null;
  difficulty?: Difficulty | null;
  ratingsMode?: RatingsMode | null;
  completedAt?: string | null;
  createdAt?: string | null;
  finalPosition?: number | null;
  points?: number | null;
  wins?: number | null;
  draws?: number | null;
  losses?: number | null;
  goalsFor?: number | null;
  goalsAgainst?: number | null;
  goalDifference?: number | null;
  averageRating?: number | null;
  titleWon?: boolean;
  perfectSeason?: boolean;
  picks?: Pick[] | null;
  settings?: Partial<RoomSettings> | null;
  result?: SeasonResult | null;
};

type AccountHistory = {
  account?: Account | null;
  stats: AccountStats;
  seasons: SeasonHistoryEntry[];
};

type AccountResponse = {
  account?: Account | null;
  user?: Account | null;
  stats?: Partial<AccountStats> | null;
};

type HistoryResponse = {
  account?: Account | null;
  stats?: Partial<AccountStats> | null;
  seasons?: SeasonHistoryEntry[] | null;
  history?: SeasonHistoryEntry[] | null;
  items?: SeasonHistoryEntry[] | null;
  total?: number;
  limit?: number;
  offset?: number;
};

type HistoryDetailResponse = {
  season?: SeasonHistoryEntry | null;
};

type PublicProfileResponse = {
  profile?: {
    username: string;
    createdAt?: string | null;
    stats?: Partial<AccountStats> | null;
    recentSeasons?: SeasonHistoryEntry[] | null;
  } | null;
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
  landingIndex: number;
  loopLength?: number;
  phase: "pending" | "settled";
  round: number;
  selected: Spin | null;
  reducedMotion: boolean;
};

type SpinStrip = {
  items: CatalogClubSeason[];
  landingIndex: number;
};

type SeasonPhase = "preview" | "running" | "final";
type SimulationSpeed = "normal" | "fast";
type AccountDialogMode = "login" | "register" | "forgot" | "reset";

type AccountFormState = {
  identifier: string;
  username: string;
  email: string;
  password: string;
  passwordConfirmation: string;
  resetToken: string;
};

type PasswordRecoveryResponse = {
  ok?: boolean;
  resetToken?: string | null;
  resetUrl?: string | null;
};

const PASSWORD_RESET_FRAGMENT = "#reset-password=";

function passwordResetTokenFromFragment(fragment: string) {
  if (!fragment.startsWith(PASSWORD_RESET_FRAGMENT)) return "";
  try {
    return decodeURIComponent(fragment.slice(PASSWORD_RESET_FRAGMENT.length)).trim();
  } catch {
    return "";
  }
}

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
  process.env.NEXT_PUBLIC_SIM_API_URL ?? "http://localhost:8002"
).replace(/\/$/, "");

const SPIN_CONFLICT_CODES = new Set(["version_conflict", "turn_conflict"]);
const SPIN_CONFLICT_RETRY_DELAYS_MS = [90, 180, 360, 720] as const;
const ROOM_MUTATION_CONFLICT_CODES = new Set([
  "version_conflict",
  "turn_conflict",
]);
const ROOM_MUTATION_RETRY_DELAYS_MS = [90, 180, 360, 720, 1_000] as const;
const ACTIVE_ROOM_MUTATIONS = new Set<string>();

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
  "10314",
  "2776",
  "5111",
  "6087",
]);

const CLUB_CREST_ALIASES: Record<string, string> = {
  "croatia-zagreb": "419",
  "dinamo-zagreb": "419",
  "gnk-dinamo": "419",
  "gnk-dinamo-zagreb": "419",
  "hnk-hajduk": "447",
  "hnk-hajduk-split": "447",
  "hajduk-split": "447",
  "hnk-rijeka": "144",
  "nk-osijek": "327",
  "nk-slaven-belupo": "2362",
  "slaven-belupo-koprivnica": "2362",
  "nk-istra-1961": "999",
  "nk-pula-staro-cesko": "999",
  "nk-lokomotiva": "11194",
  "nk-lokomotiva-zagreb": "11194",
  "nk-varazdin": "599",
  "nk-varteks-varazdin": "599",
  "nk-zagreb": "5107",
  "zagreb": "5107",
  "nk-inter-zapresic": "918",
  "hnk-sibenik": "223",
  "nk-zadar": "2566",
  "rnk-split": "420",
  "hnk-cibalia": "314",
  "hnk-cibalia-vinkovci": "314",
  "nk-hrvatski-dragovoljac": "485",
  "hnk-gorica": "24575",
  "nk-rudes": "11083",
  "nk-lucko": "12109",
  "hnk-vukovar-1991": "456",
  "nk-karlovac-1919": "10314",
  "nk-kamen-ingrad-velika": "2776",
  "nk-croatia-sesvete": "5111",
  "nk-medjimurje-cakovec": "6087",
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

function spinIdentity(spin: Spin | null | undefined) {
  return spin
    ? `${spin.turn}:${spin.spinNumber}:${spin.clubSeasonId}`
    : null;
}

function waitForRetry(delayMs: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, delayMs);
  });
}

function beginRoomMutation(key: string) {
  if (ACTIVE_ROOM_MUTATIONS.has(key)) return false;
  ACTIVE_ROOM_MUTATIONS.add(key);
  return true;
}

function finishRoomMutation(key: string) {
  ACTIVE_ROOM_MUTATIONS.delete(key);
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
      credentials: "include",
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

type RetriedRoomMutationOptions = {
  initialRoom: Room;
  path: string;
  token: string;
  buildPayload: (latestRoom: Room) => Record<string, unknown>;
  acceptRoomState: (latestRoom: Room) => void;
  isApplied?: (latestRoom: Room) => boolean;
  canRetry?: (latestRoom: Room) => boolean;
};

async function mutateRoomWithRetry({
  initialRoom,
  path,
  token,
  buildPayload,
  acceptRoomState,
  isApplied = () => false,
  canRetry = () => true,
}: RetriedRoomMutationOptions): Promise<Room> {
  let requestRoom = initialRoom;

  for (
    let attempt = 0;
    attempt <= ROOM_MUTATION_RETRY_DELAYS_MS.length;
    attempt += 1
  ) {
    try {
      const nextRoom = await apiRequest<Room>(
        path,
        {
          method: "POST",
          body: JSON.stringify(buildPayload(requestRoom)),
        },
        token,
      );
      acceptRoomState(nextRoom);
      return nextRoom;
    } catch (requestError) {
      const retryableConflict =
        requestError instanceof ApiError &&
        requestError.status === 409 &&
        ROOM_MUTATION_CONFLICT_CODES.has(requestError.code);
      if (!retryableConflict) throw requestError;

      const freshRoom = await apiRequest<Room>(
        `/rooms/${initialRoom.code}`,
        {},
        token,
      );
      acceptRoomState(freshRoom);

      // A lost response or the same action from another device may already
      // have committed. Treat that state as success instead of submitting the
      // action twice (especially important for swaps).
      if (isApplied(freshRoom)) return freshRoom;
      if (!canRetry(freshRoom)) {
        throw new ApiError(
          "Radnja više nije dostupna jer se stanje tvoje momčadi promijenilo.",
          "room_mutation_superseded",
          409,
        );
      }
      if (attempt >= ROOM_MUTATION_RETRY_DELAYS_MS.length) {
        throw new ApiError(
          "Soba je trenutačno zauzeta. Pokušaj ponovno za trenutak.",
          "room_mutation_retry_exhausted",
          409,
        );
      }

      requestRoom = freshRoom;
      await waitForRetry(ROOM_MUTATION_RETRY_DELAYS_MS[attempt]);
    }
  }

  // The bounded loop always returns or throws. This keeps TypeScript aware of
  // that invariant if the retry schedule is ever changed.
  throw new ApiError("Zahtjev nije dovršen.", "room_mutation_retry_exhausted", 409);
}

function formatNumber(value: number | undefined, fallback: string) {
  return typeof value === "number"
    ? new Intl.NumberFormat("hr-HR").format(value)
    : fallback;
}

const EMPTY_ACCOUNT_STATS: AccountStats = {
  seasonsPlayed: 0,
  titles: 0,
  wins: 0,
  draws: 0,
  losses: 0,
  points: 0,
  goalsFor: 0,
  goalsAgainst: 0,
  goalDifference: 0,
  averagePoints: 0,
  bestPoints: 0,
  bestFinish: null,
  averageFinish: null,
  winRate: 0,
  perfectSeasons: 0,
  invincibleSeasons: 0,
};

function accountFromResponse(payload: AccountResponse | Account) {
  const wrapped = payload as AccountResponse;
  const candidate = wrapped.account ?? wrapped.user ?? (payload as Account);
  return candidate?.username ? candidate : null;
}

function historyResult(entry: SeasonHistoryEntry) {
  return entry.result ?? null;
}

function historyNumber(
  entry: SeasonHistoryEntry,
  field:
    | "wins"
    | "draws"
    | "losses"
    | "points"
    | "goalsFor"
    | "goalsAgainst"
    | "goalDifference"
    | "finalPosition",
) {
  const direct = entry[field];
  if (typeof direct === "number") return direct;
  const nested = historyResult(entry)?.[field];
  return typeof nested === "number" ? nested : 0;
}

function computedAccountStats(seasons: SeasonHistoryEntry[]): AccountStats {
  const finishes = seasons
    .map((season) => historyNumber(season, "finalPosition"))
    .filter((position) => position > 0);
  const wins = seasons.reduce(
    (total, season) => total + historyNumber(season, "wins"),
    0,
  );
  const draws = seasons.reduce(
    (total, season) => total + historyNumber(season, "draws"),
    0,
  );
  const losses = seasons.reduce(
    (total, season) => total + historyNumber(season, "losses"),
    0,
  );
  const played = wins + draws + losses;
  const goalsFor = seasons.reduce(
    (total, season) => total + historyNumber(season, "goalsFor"),
    0,
  );
  const goalsAgainst = seasons.reduce(
    (total, season) => total + historyNumber(season, "goalsAgainst"),
    0,
  );
  return {
    seasonsPlayed: seasons.length,
    titles: seasons.filter(
      (season) =>
        season.titleWon ||
        historyNumber(season, "finalPosition") === 1 ||
        historyResult(season)?.awards?.leagueTitle === true,
    ).length,
    wins,
    draws,
    losses,
    points: seasons.reduce(
      (total, season) => total + historyNumber(season, "points"),
      0,
    ),
    goalsFor,
    goalsAgainst,
    goalDifference: goalsFor - goalsAgainst,
    averagePoints: seasons.length
      ? seasons.reduce(
          (total, season) => total + historyNumber(season, "points"),
          0,
        ) / seasons.length
      : 0,
    bestPoints: seasons.length
      ? Math.max(...seasons.map((season) => historyNumber(season, "points")))
      : 0,
    bestFinish: finishes.length ? Math.min(...finishes) : null,
    averageFinish: finishes.length
      ? finishes.reduce((total, position) => total + position, 0) /
        finishes.length
      : null,
    winRate: played ? wins / played : 0,
    perfectSeasons: seasons.filter(
      (season) =>
        season.perfectSeason ||
        historyResult(season)?.awards?.perfectSeason ||
        (historyNumber(season, "wins") > 0 &&
          historyNumber(season, "draws") === 0 &&
          historyNumber(season, "losses") === 0),
    ).length,
    invincibleSeasons: seasons.filter(
      (season) =>
        (historyNumber(season, "wins") + historyNumber(season, "draws") > 0 &&
          historyNumber(season, "losses") === 0) ||
        historyResult(season)?.awards?.invincible,
    ).length,
  };
}

function normalizeHistory(
  payload: HistoryResponse,
  fallbackAccount?: Account | null,
): AccountHistory {
  const seasons = payload.seasons ?? payload.history ?? payload.items ?? [];
  const computed = computedAccountStats(seasons);
  return {
    account: payload.account ?? fallbackAccount ?? null,
    seasons,
    stats: {
      ...EMPTY_ACCOUNT_STATS,
      ...computed,
      ...(payload.stats ?? {}),
    },
  };
}

function formatHistoryDate(value?: string | null) {
  if (!value) return "Datum nije zabilježen";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return new Intl.DateTimeFormat("hr-HR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
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

type PositionGroup = "gk" | "def" | "mid" | "fwd";

function positionGroup(position: string | null | undefined): PositionGroup {
  const normalized = (position ?? "")
    .trim()
    .toUpperCase()
    .replace(/[\s_-]+/g, "");

  if (normalized === "G" || normalized === "GK") return "gk";
  if (
    ["DEF", "CB", "LCB", "RCB", "LB", "RB", "LWB", "RWB", "SW"].includes(
      normalized,
    ) ||
    normalized.endsWith("CB")
  ) {
    return "def";
  }
  if (
    ["FWD", "FW", "ST", "CF", "SS", "LW", "RW", "WF"].includes(
      normalized,
    ) ||
    normalized.endsWith("ST")
  ) {
    return "fwd";
  }
  return "mid";
}

function positionGroupClass(position: string | null | undefined) {
  return `position-${positionGroup(position)}`;
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
  const normalizedSeed = Math.abs(seed % 2_147_483_647);
  const value = Math.sin(normalizedSeed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
}

function spinCatalogPool(
  catalog: CatalogInventory | null,
  settings: RoomSettings,
) {
  return (
    catalog?.clubSeasons?.filter(
      (item) =>
        item.season.startYear >= settings.seasonStart &&
        item.season.startYear <= settings.seasonEnd,
    ) ?? []
  );
}

function deterministicSpinItem(
  pool: CatalogClubSeason[],
  seed: number,
  excludedIds: ReadonlySet<string>,
  avoidItems: readonly CatalogClubSeason[] = [],
) {
  if (!pool.length) return null;
  const startIndex = Math.floor(seededNoise(seed) * pool.length) % pool.length;
  const ordered = Array.from(
    { length: pool.length },
    (_, offset) => pool[(startIndex + offset) % pool.length],
  );
  return (
    ordered.find(
      (item) =>
        !excludedIds.has(item.id) &&
        avoidItems.every(
          (avoid) =>
            item.club.id !== avoid.club.id &&
            item.season.startYear !== avoid.season.startYear,
        ),
    ) ??
    ordered.find((item) => !excludedIds.has(item.id)) ??
    ordered[0]
  );
}

function buildSpinItems(
  catalog: CatalogInventory | null,
  selected: Spin,
  settings: RoomSettings,
  seed: number,
  seat: number,
): SpinStrip {
  const selectedItem: CatalogClubSeason =
    catalog?.clubSeasons?.find((item) => item.id === selected.clubSeasonId) ?? {
      id: selected.clubSeasonId,
      club: selected.club,
      season: selected.season,
      playerCount: selected.players?.length ?? 0,
    };
  const eligible = spinCatalogPool(catalog, settings);
  const poolById = new Map(
    [...eligible, selectedItem].map((item) => [item.id, item]),
  );
  const pool = [...poolById.values()];
  const reelSeed = Math.abs(seed % 2_147_483_647);
  const landingIndex = 17;
  const decoys: CatalogClubSeason[] = [];
  for (let index = 0; index < landingIndex; index += 1) {
    const previous = decoys.at(-1);
    const excludedIds = new Set(previous ? [previous.id] : []);
    if (index === landingIndex - 1) excludedIds.add(selectedItem.id);
    const item = deterministicSpinItem(
      pool,
      reelSeed +
        seat * 193 +
        selected.turn * 977 +
        selected.spinNumber * 1543 +
        index * 71,
      excludedIds,
      index === landingIndex - 1
        ? [selectedItem]
        : previous
          ? [previous]
          : [],
    );
    if (item) decoys.push(item);
  }

  const items = [...decoys, selectedItem];
  let neighbor = selectedItem;
  for (let index = 0; index < 2; index += 1) {
    const previousTailItems = items.slice(landingIndex + 1);
    const avoidedNeighbors = [selectedItem, ...previousTailItems];
    const tail = deterministicSpinItem(
      pool,
      reelSeed +
        seat * 389 +
        selected.turn * 1217 +
        selected.spinNumber * 2017 +
        index * 101,
      new Set([selectedItem.id, neighbor.id]),
      avoidedNeighbors,
    );
    if (tail) {
      items.push(tail);
      neighbor = tail;
    }
  }
  return { items, landingIndex };
}

function buildPendingSpinItems(
  catalog: CatalogInventory,
  settings: RoomSettings,
  seed: number,
  seat: number,
  turn: number,
): { items: CatalogClubSeason[]; loopLength: number } | null {
  const pool = spinCatalogPool(catalog, settings);
  if (!pool.length) return null;
  const reelSeed = Math.abs(seed % 2_147_483_647);
  const loopLength = Math.min(10, Math.max(4, pool.length));
  const baseItems: CatalogClubSeason[] = [];
  for (let index = 0; index < loopLength; index += 1) {
    const previous = baseItems.at(-1);
    const item = deterministicSpinItem(
      pool,
      reelSeed + seat * 271 + turn * 853 + index * 47,
      new Set(previous ? [previous.id] : []),
      previous ? [previous] : [],
    );
    if (item) baseItems.push(item);
  }
  if (!baseItems.length) return null;
  return {
    items: [...baseItems, ...baseItems],
    loopLength: baseItems.length,
  };
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
  const simulationSeed = Math.abs(seed % 2_147_483_647);
  const firstNoise = seededNoise(simulationSeed + seat * 97);
  const secondNoise = seededNoise(simulationSeed + seat * 211 + 17);
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
  account,
  onHome,
  onAccount,
}: {
  stage: string;
  room?: Room | null;
  account?: Account | null;
  onHome: () => void;
  onAccount: () => void;
}) {
  const accountLabel =
    account?.displayName?.trim() || account?.username || "Prijava";
  return (
    <header className="topbar">
      <button className="brand" onClick={onHome} aria-label="SHNL 36-0 naslovnica">
        <span className="brand-score">SHNL</span>
        <span className="brand-meta">
          36-0
          <small>KLUB × SEZONA</small>
        </span>
      </button>
      <div className="stage-indicator" aria-label={`Trenutni korak: ${stage}`}>
        <span className="pulse-dot" aria-hidden="true" />
        {stage}
      </div>
      <div className="header-actions">
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
        <button
          type="button"
          className={`account-trigger${account ? " signed-in" : ""}`}
          onClick={onAccount}
          aria-label={
            account
              ? `Otvori profil korisnika ${accountLabel}`
              : "Prijava ili izrada računa"
          }
        >
          <span aria-hidden="true">
            {account ? managerInitials(accountLabel) : "◎"}
          </span>
          <strong>{account ? accountLabel : "Prijava"}</strong>
        </button>
      </div>
    </header>
  );
}

function AccountDialog({
  mode,
  form,
  busy,
  error,
  notice,
  onMode,
  onChange,
  onSubmit,
  onClose,
}: {
  mode: AccountDialogMode;
  form: AccountFormState;
  busy: boolean;
  error: string;
  notice: string;
  onMode: (mode: AccountDialogMode) => void;
  onChange: (field: keyof AccountFormState, value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onClose: () => void;
}) {
  const registering = mode === "register";
  const forgotPassword = mode === "forgot";
  const resettingPassword = mode === "reset";
  const settingNewPassword = registering || resettingPassword;
  const title = registering
    ? "Sačuvaj svoju povijest."
    : forgotPassword
      ? "Vrati pristup računu."
      : resettingPassword
        ? "Postavi novu lozinku."
        : "Dobrodošao natrag.";
  const lead = registering
    ? "Svaka sezona koju završiš dok si prijavljen ulazi u tvoju statistiku."
    : forgotPassword
      ? "Upiši e-mail računa i poslat ćemo ti poveznicu za postavljanje nove lozinke."
      : resettingPassword
        ? "Odaberi novu lozinku od najmanje 15 znakova za svoj SHNL 36-0 račun."
        : "Prijavi se za pregled svih svojih momčadi, rezultata i rekorda.";
  return (
    <div
      className="account-modal-backdrop"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) onClose();
      }}
    >
      <section
        className="account-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="account-dialog-title"
      >
        <button
          type="button"
          className="account-modal-close"
          onClick={onClose}
          aria-label="Zatvori prozor računa"
        >
          ×
        </button>
        <p className="eyebrow">TVOJ SHNL 36-0 PROFIL</p>
        <h2 id="account-dialog-title">{title}</h2>
        <p className="account-modal-lead">{lead}</p>
        {forgotPassword || resettingPassword ? (
          <button
            type="button"
            className="account-back"
            onClick={() => onMode("login")}
          >
            ← Natrag na prijavu
          </button>
        ) : (
          <div
            className="account-mode-tabs"
            role="tablist"
            aria-label="Vrsta prijave"
          >
            <button
              type="button"
              role="tab"
              aria-selected={!registering}
              className={!registering ? "active" : ""}
              onClick={() => onMode("login")}
            >
              Prijava
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={registering}
              className={registering ? "active" : ""}
              onClick={() => onMode("register")}
            >
              Novi račun
            </button>
          </div>
        )}
        <form className="account-form" onSubmit={onSubmit}>
          {registering ? (
            <>
              <label htmlFor="account-username">
                Korisničko ime
                <input
                  id="account-username"
                  value={form.username}
                  onChange={(event) => onChange("username", event.target.value)}
                  minLength={3}
                  maxLength={24}
                  pattern="[A-Za-z0-9](?:[A-Za-z0-9_.-]{1,22}[A-Za-z0-9])?"
                  autoComplete="username"
                  placeholder="npr. maestro10"
                  required
                  autoFocus
                />
                <small>
                  3–24 znaka · počni i završi slovom ili brojem
                </small>
              </label>
              <label htmlFor="account-email">
                E-mail
                <input
                  id="account-email"
                  type="email"
                  value={form.email}
                  onChange={(event) => onChange("email", event.target.value)}
                  autoComplete="email"
                  placeholder="ti@primjer.hr"
                  required
                />
              </label>
            </>
          ) : forgotPassword ? (
            <label htmlFor="account-recovery-email">
              E-mail računa
              <input
                id="account-recovery-email"
                type="email"
                value={form.email}
                onChange={(event) => onChange("email", event.target.value)}
                autoComplete="email"
                placeholder="ti@primjer.hr"
                required
                autoFocus
              />
            </label>
          ) : resettingPassword ? null : (
            <label htmlFor="account-identifier">
              Korisničko ime ili e-mail
              <input
                id="account-identifier"
                value={form.identifier}
                onChange={(event) => onChange("identifier", event.target.value)}
                autoComplete="username"
                placeholder="maestro10 ili ti@primjer.hr"
                required
                autoFocus
              />
            </label>
          )}
          {!forgotPassword ? (
            <>
              <label htmlFor="account-password">
                {resettingPassword ? "Nova lozinka" : "Lozinka"}
                <input
                  id="account-password"
                  type="password"
                  value={form.password}
                  onChange={(event) => onChange("password", event.target.value)}
                  minLength={settingNewPassword ? 15 : undefined}
                  maxLength={128}
                  autoComplete={
                    settingNewPassword ? "new-password" : "current-password"
                  }
                  placeholder={
                    settingNewPassword ? "Najmanje 15 znakova" : "Tvoja lozinka"
                  }
                  required
                  autoFocus={resettingPassword}
                />
              </label>
              {mode === "login" ? (
                <div className="account-recovery-actions">
                  {form.resetToken ? (
                    <button
                      type="button"
                      className="account-forgot"
                      onClick={() => onMode("reset")}
                    >
                      Nastavi promjenu lozinke
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="account-forgot"
                    onClick={() => onMode("forgot")}
                  >
                    Zaboravili ste lozinku?
                  </button>
                </div>
              ) : null}
              {resettingPassword ? (
                <label htmlFor="account-password-confirmation">
                  Ponovi novu lozinku
                  <input
                    id="account-password-confirmation"
                    type="password"
                    value={form.passwordConfirmation}
                    onChange={(event) =>
                      onChange("passwordConfirmation", event.target.value)
                    }
                    minLength={15}
                    maxLength={128}
                    autoComplete="new-password"
                    placeholder="Ponovi novu lozinku"
                    required
                  />
                </label>
              ) : null}
            </>
          ) : null}
          {notice ? (
            <p className="account-form-notice" role="status">
              {notice}
            </p>
          ) : null}
          {error ? (
            <p className="account-form-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="account-submit" type="submit" disabled={busy}>
            {busy
              ? forgotPassword
                ? "Šaljemo…"
                : resettingPassword
                  ? "Mijenjamo…"
                  : "Spremamo…"
              : forgotPassword
                ? "Pošalji poveznicu →"
                : resettingPassword
                  ? "Postavi novu lozinku →"
              : registering
                ? "Izradi račun →"
                : "Prijavi se →"}
          </button>
        </form>
        <button type="button" className="account-skip" onClick={onClose}>
          Nastavi bez računa
        </button>
        <p className="account-privacy">
          Račun nije obavezan za igru. E-mail se nikad ne prikazuje na javnom
          profilu.
        </p>
      </section>
    </div>
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
  const settled = animation.phase === "settled";
  const selected = animation.selected;
  const style = {
    "--reel-index": animation.landingIndex,
    "--reel-loop-offset": `-${(animation.loopLength ?? 0) * 72}px`,
    "--reel-duration": animation.reducedMotion ? "180ms" : "3.25s",
    "--season-delay":
      animation.phase === "pending" || animation.reducedMotion
        ? "0ms"
        : "180ms",
  } as CSSProperties;
  return (
    <div
      className={`reel-state reel-${animation.phase}`}
      key={animation.key}
      style={style}
    >
      <div className="round-label">
        KOTAČ {String(animation.round + 1).padStart(2, "0")}
      </div>
      <p className="eyebrow">KLUB × TOČNA SEZONA</p>
      <h2>{settled ? "Izvučeno!" : "Kotač se vrti…"}</h2>
      <div className="club-season-reel" aria-hidden="true">
        <div className="reel-column club-column">
          <span className="reel-caption">KLUB</span>
          <div className="reel-viewport">
            <div className="reel-track">
              {animation.items.map((item, index) => {
                const itemState = settled
                  ? index === animation.landingIndex
                    ? " is-selected"
                    : Math.abs(index - animation.landingIndex) === 1
                      ? " is-neighbor"
                      : ""
                  : "";
                return (
                  <div
                    className={`reel-item club-reel-item${itemState}`}
                    key={`${item.id}-${index}`}
                  >
                    <ClubShield club={item.club} compact />
                    <strong>{item.club.name}</strong>
                  </div>
                );
              })}
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
              {animation.items.map((item, index) => {
                const itemState = settled
                  ? index === animation.landingIndex
                    ? " is-selected"
                    : Math.abs(index - animation.landingIndex) === 1
                      ? " is-neighbor"
                      : ""
                  : "";
                return (
                  <div
                    className={`reel-item season-reel-item${itemState}`}
                    key={`${item.id}-s-${index}`}
                  >
                    <strong>{item.season.label}</strong>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
      <p className="reel-lock-copy" role="status" aria-live="polite">
        {settled && selected
          ? `Izvučeno: ${selected.club.name} · ${selected.season.label}.`
          : "Čekamo potvrdu poslužitelja. Kotač ostaje u pokretu."}
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

function historyPosition(entry: SeasonHistoryEntry) {
  const position = entry.finalPosition ?? entry.result?.finalPosition;
  return typeof position === "number" ? position : null;
}

function historyTitle(entry: SeasonHistoryEntry) {
  const position = historyPosition(entry);
  if (entry.perfectSeason || entry.result?.awards?.perfectSeason) return "36–0";
  if (entry.titleWon || entry.result?.awards?.leagueTitle || position === 1) {
    return "Prvak";
  }
  return position ? `${position}. mjesto` : "Završena sezona";
}

function AccountHistoryPitch({ season }: { season: SeasonHistoryEntry }) {
  const picks = season.picks ?? [];
  const formation = season.formation ?? season.settings?.formation ?? "4-3-3";
  const storedSlots = season.settings?.slots ?? [];
  const fallbackLabels = FORMATION_PREVIEWS[formation] ?? [];
  const points = FORMATION_COORDINATES[formation] ?? [];

  return (
    <div className="history-pitch" aria-label={`Postava ${formation}`}>
      <span className="history-pitch-formation">{formation}</span>
      {picks.map((pick, pickIndex) => {
        const storedIndex = storedSlots.findIndex(
          (slot) => slot.id === pick.slotId,
        );
        const labelOccurrence = picks
          .slice(0, pickIndex)
          .filter((previous) => previous.slotLabel === pick.slotLabel).length;
        const matchingLabelIndexes = fallbackLabels
          .map((label, index) => (label === pick.slotLabel ? index : -1))
          .filter((index) => index >= 0);
        const labelIndex =
          matchingLabelIndexes[labelOccurrence] ??
          matchingLabelIndexes.at(-1) ??
          -1;
        const pointIndex =
          storedIndex >= 0
            ? storedIndex
            : labelIndex >= 0
              ? labelIndex
              : pickIndex;
        const point = points[pointIndex] ?? ([50, 50] as const);
        return (
          <div
            className="history-pitch-player"
            key={`${pick.slotId}-${pick.player.id}`}
            style={
              {
                "--history-x": `${point[0]}%`,
                "--history-y": `${point[1]}%`,
              } as CSSProperties
            }
          >
            <span className={positionGroupClass(pick.slotLabel)}>
              {pick.slotLabel}
            </span>
            <strong>{surname(pick.player.name)}</strong>
            <small>{pick.selectedRating ?? pick.player.rating ?? "—"}</small>
          </div>
        );
      })}
    </div>
  );
}

function AccountPanel({
  history,
  selectedSeason,
  selectedId,
  loading,
  detailLoading,
  error,
  publicView,
  onClose,
  onSelect,
  onBack,
  onLogout,
  onCopyProfile,
}: {
  history: AccountHistory | null;
  selectedSeason: SeasonHistoryEntry | null;
  selectedId: string | null;
  loading: boolean;
  detailLoading: boolean;
  error: string;
  publicView: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  onBack: () => void;
  onLogout: () => void;
  onCopyProfile: () => void;
}) {
  const account = history?.account;
  const stats = history?.stats ?? EMPTY_ACCOUNT_STATS;
  const seasons = history?.seasons ?? [];
  const result = selectedSeason ? historyResult(selectedSeason) : null;
  const displayName =
    account?.displayName?.trim() || account?.username || "HNL menadžer";
  const totalMatches = stats.wins + stats.draws + stats.losses;
  const displayedWinRate =
    typeof stats.winRate === "number" && stats.winRate > 0
      ? stats.winRate > 1
        ? stats.winRate
        : stats.winRate * 100
      : totalMatches
        ? (stats.wins / totalMatches) * 100
        : 0;

  return (
    <div className="account-panel-layer">
      <section
        className="account-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Profil i povijest HNL sezona"
      >
        <header className="account-panel-topbar">
          <button
            type="button"
            className="account-panel-brand"
            onClick={onBack}
            disabled={!selectedId}
          >
            <span>SHNL 36-0</span>
            <strong>{selectedId ? "← Povijest sezona" : "PROFIL MENADŽERA"}</strong>
          </button>
          <button
            type="button"
            className="account-panel-close"
            onClick={onClose}
            aria-label="Zatvori profil"
          >
            ×
          </button>
        </header>

        {loading ? (
          <div className="account-panel-state" role="status">
            <i aria-hidden="true" />
            <strong>Učitavamo tvoju svlačionicu…</strong>
          </div>
        ) : error ? (
          <div className="account-panel-state error" role="alert">
            <span>!</span>
            <strong>Profil trenutačno nije dostupan.</strong>
            <p>{error}</p>
          </div>
        ) : selectedId ? (
          detailLoading || !selectedSeason ? (
            <div className="account-panel-state" role="status">
              <i aria-hidden="true" />
              <strong>Otvaramo zapis sezone…</strong>
            </div>
          ) : (
            <div className="account-season-detail">
              <section className="history-detail-hero">
                <div>
                  <p className="eyebrow">
                    {selectedSeason.mode === "live" ? "LIVE DRAFT" : "SOLO DRAFT"} ·{" "}
                    {formatHistoryDate(
                      selectedSeason.completedAt ?? selectedSeason.createdAt,
                    )}
                  </p>
                  <h1>{historyTitle(selectedSeason)}</h1>
                  <p>
                    {selectedSeason.managerName || displayName} ·{" "}
                    {selectedSeason.formation ??
                      selectedSeason.settings?.formation ??
                      "Formacija nije zabilježena"}
                  </p>
                </div>
                <div className="history-detail-points">
                  <strong>{historyNumber(selectedSeason, "points")}</strong>
                  <span>BODOVA</span>
                </div>
              </section>

              <section className="history-detail-record">
                {[
                  ["P", historyNumber(selectedSeason, "wins"), "Pobjede"],
                  ["N", historyNumber(selectedSeason, "draws"), "Neriješeno"],
                  ["I", historyNumber(selectedSeason, "losses"), "Porazi"],
                  [
                    "GR",
                    historyNumber(selectedSeason, "goalDifference"),
                    `${historyNumber(selectedSeason, "goalsFor")}:${historyNumber(
                      selectedSeason,
                      "goalsAgainst",
                    )}`,
                  ],
                ].map(([label, value, copy]) => (
                  <div key={String(label)}>
                    <span>{label}</span>
                    <strong>
                      {label === "GR" && Number(value) > 0 ? "+" : ""}
                      {value}
                    </strong>
                    <small>{copy}</small>
                  </div>
                ))}
              </section>

              {selectedSeason.picks?.length ? (
                <section className="history-detail-section history-lineup-section">
                  <div className="account-section-heading">
                    <span>TVA XI</span>
                    <h2>Momčad koja je odigrala sezonu.</h2>
                  </div>
                  <AccountHistoryPitch season={selectedSeason} />
                </section>
              ) : null}

              {result?.playerStats?.length ? (
                <section className="history-detail-section">
                  <div className="account-section-heading">
                    <span>UČINAK IGRAČA</span>
                    <h2>Najbolji pojedinci.</h2>
                  </div>
                  <div className="account-player-list">
                    {result.playerStats
                      .slice()
                      .sort(
                        (a, b) =>
                          b.goals +
                            b.assists -
                            (a.goals + a.assists) ||
                          a.playerName.localeCompare(b.playerName),
                      )
                      .slice(0, 11)
                      .map((player, index) => (
                        <div key={player.playerId}>
                          <span>{String(index + 1).padStart(2, "0")}</span>
                          <strong>{player.playerName}</strong>
                          <small>
                            {player.goals} G · {player.assists} A ·{" "}
                            {player.cleanSheets} ČM
                          </small>
                          <b>{player.rating ?? "—"}</b>
                        </div>
                      ))}
                  </div>
                </section>
              ) : null}

              {result?.leagueTable?.length ? (
                <section className="history-detail-section">
                  <div className="account-section-heading">
                    <span>KONAČNA TABLICA</span>
                    <h2>HNL nakon 36 kola.</h2>
                  </div>
                  <div className="account-league-table">
                    <table>
                      <thead>
                        <tr>
                          <th>#</th>
                          <th>Klub</th>
                          <th>O</th>
                          <th>GR</th>
                          <th>B</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.leagueTable.map((row) => (
                          <tr
                            key={row.teamId}
                            className={row.isDraftedXI ? "mine" : ""}
                          >
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
                              <strong>
                                {row.isDraftedXI
                                  ? selectedSeason.managerName || displayName
                                  : row.name}
                              </strong>
                            </td>
                            <td>{row.played}</td>
                            <td>
                              {row.goalDifference > 0 ? "+" : ""}
                              {row.goalDifference}
                            </td>
                            <td>
                              <strong>{row.points}</strong>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : null}

              {result?.matches?.length ? (
                <section className="history-detail-section">
                  <div className="account-section-heading">
                    <span>RASPORED</span>
                    <h2>Svih 36 utakmica.</h2>
                  </div>
                  <div className="account-fixture-grid">
                    {result.matches.map((match) => (
                      <MatchCard key={match.matchweek} match={match} />
                    ))}
                  </div>
                </section>
              ) : null}
            </div>
          )
        ) : (
          <div className="account-overview">
            <section className="account-profile-hero">
              <div className="account-avatar" aria-hidden="true">
                {managerInitials(displayName) || "36"}
              </div>
              <div>
                <p className="eyebrow">
                  {publicView ? "JAVNI PROFIL" : "TVOJ PROFIL"}
                </p>
                <h1 id="account-panel-title">{displayName}</h1>
                <p>@{account?.username}</p>
                <small>
                  Menadžer od {formatHistoryDate(account?.createdAt)}
                </small>
              </div>
              {!publicView ? (
                <div className="account-profile-actions">
                  <button type="button" onClick={onCopyProfile}>
                    Kopiraj javni profil
                  </button>
                  <button type="button" onClick={onLogout}>
                    Odjava
                  </button>
                </div>
              ) : null}
            </section>

            <section className="account-stat-grid" aria-label="Statistika menadžera">
              {[
                ["SEZONE", stats.seasonsPlayed, "završeno"],
                ["NASLOVI", stats.titles, "osvojeno"],
                ["POBJEDE", stats.wins, `${displayedWinRate.toFixed(1)}%`],
                [
                  "BODOVI",
                  stats.points,
                  stats.seasonsPlayed
                    ? `prosjek ${(stats.averagePoints ?? 0).toFixed(1)} · rekord ${
                        stats.bestPoints ?? 0
                      }`
                    : "ukupno",
                ],
                [
                  "GOL-RAZLIKA",
                  `${stats.goalDifference > 0 ? "+" : ""}${stats.goalDifference}`,
                  `${stats.goalsFor}:${stats.goalsAgainst}`,
                ],
                [
                  "NAJBOLJI PLASMAN",
                  stats.bestFinish ? `${stats.bestFinish}.` : "—",
                  stats.averageFinish
                    ? `prosjek ${stats.averageFinish.toFixed(1)}.`
                    : "još bez plasmana",
                ],
              ].map(([label, value, copy]) => (
                <div key={String(label)}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{copy}</small>
                </div>
              ))}
            </section>

            <section className="account-history-section">
              <div className="account-section-heading">
                <span>SEZONSKI ARHIV</span>
                <h2>
                  {seasons.length
                    ? `${seasons.length} momčad${
                        seasons.length === 1 ? "" : "i"
                      } u povijesti.`
                    : "Tvoja prva sezona tek čeka."}
                </h2>
                <p>
                  {publicView
                    ? "Posljednji javno vidljivi rezultati ovog menadžera."
                    : "Otvorite sezonu za postavu, tablicu, igrače i svih 36 kola."}
                </p>
              </div>
              {seasons.length ? (
                <div className="account-season-list">
                  {seasons.map((season, index) => {
                    const position = historyPosition(season);
                    const title = historyTitle(season);
                    const canOpen = !publicView;
                    return (
                      <button
                        type="button"
                        key={season.id}
                        onClick={() => canOpen && onSelect(season.id)}
                        disabled={!canOpen}
                        className={
                          season.titleWon ||
                          season.perfectSeason ||
                          position === 1
                            ? "champion"
                            : ""
                        }
                      >
                        <span className="account-season-index">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <div className="account-season-main">
                          <span>
                            {season.mode === "live" ? "LIVE" : "SOLO"} ·{" "}
                            {formatHistoryDate(
                              season.completedAt ?? season.createdAt,
                            )}
                          </span>
                          <strong>{title}</strong>
                          <small>
                            {season.managerName || displayName} ·{" "}
                            {season.formation || "Formacija —"}
                          </small>
                        </div>
                        <div className="account-season-record">
                          <strong>{historyNumber(season, "points")}</strong>
                          <span>BODOVA</span>
                          <small>
                            {historyNumber(season, "wins")}–{historyNumber(season, "draws")}–
                            {historyNumber(season, "losses")}
                          </small>
                        </div>
                        <span className="account-season-arrow" aria-hidden="true">
                          {canOpen ? "→" : "•"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="account-empty-state">
                  <span aria-hidden="true">＋</span>
                  <strong>Odigraj draft i simuliraj sezonu.</strong>
                  <p>
                    Rezultat se automatski sprema kada si prijavljen prije
                    završetka simulacije.
                  </p>
                  <button type="button" onClick={onClose}>
                    Kreni igrati →
                  </button>
                </div>
              )}
            </section>
          </div>
        )}
      </section>
    </div>
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
  const spinRequestInFlightRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [account, setAccount] = useState<Account | null>(null);
  const [, setAccountStats] =
    useState<Partial<AccountStats> | null>(null);
  const [accountDialogOpen, setAccountDialogOpen] = useState(false);
  const [accountDialogMode, setAccountDialogMode] =
    useState<AccountDialogMode>("login");
  const [accountForm, setAccountForm] = useState<AccountFormState>({
    identifier: "",
    username: "",
    email: "",
    password: "",
    passwordConfirmation: "",
    resetToken: "",
  });
  const [accountBusy, setAccountBusy] = useState(false);
  const [accountError, setAccountError] = useState("");
  const [accountNotice, setAccountNotice] = useState("");
  const [accountPanelOpen, setAccountPanelOpen] = useState(false);
  const [accountHistory, setAccountHistory] =
    useState<AccountHistory | null>(null);
  const [accountHistoryLoading, setAccountHistoryLoading] = useState(false);
  const [accountHistoryError, setAccountHistoryError] = useState("");
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(
    null,
  );
  const [selectedHistorySeason, setSelectedHistorySeason] =
    useState<SeasonHistoryEntry | null>(null);
  const [historyDetailLoading, setHistoryDetailLoading] = useState(false);
  const [publicProfileView, setPublicProfileView] = useState(false);

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

  const loadOwnHistory = useCallback(
    async (currentAccount: Account) => {
      setAccountHistoryLoading(true);
      setAccountHistoryError("");
      try {
        const payload = await apiRequest<HistoryResponse>(
          "/account/history?limit=100&offset=0",
        );
        const normalized = normalizeHistory(payload, currentAccount);
        normalized.account = currentAccount;
        setAccountStats(normalized.stats);
        setAccountHistory(normalized);
      } catch (historyError) {
        setAccountHistoryError(
          historyError instanceof Error
            ? historyError.message
            : "Povijest sezona nije dostupna.",
        );
      } finally {
        setAccountHistoryLoading(false);
      }
    },
    [],
  );

  const openPublicProfile = useCallback(async (username: string) => {
    const cleanUsername = username.trim();
    if (!cleanUsername) return;
    setPublicProfileView(true);
    setAccountPanelOpen(true);
    setSelectedHistoryId(null);
    setSelectedHistorySeason(null);
    setAccountHistory(null);
    setAccountHistoryLoading(true);
    setAccountHistoryError("");
    try {
      const response = await apiRequest<PublicProfileResponse>(
        `/profiles/${encodeURIComponent(cleanUsername)}`,
      );
      if (!response.profile) {
        throw new ApiError("Profil nije pronađen.", "profile_not_found", 404);
      }
      const profileAccount: Account = {
        id: `public:${response.profile.username}`,
        username: response.profile.username,
        displayName: response.profile.username,
        createdAt: response.profile.createdAt,
        stats: response.profile.stats,
      };
      setAccountHistory(
        normalizeHistory(
          {
            account: profileAccount,
            stats: response.profile.stats,
            seasons: response.profile.recentSeasons ?? [],
          },
          profileAccount,
        ),
      );
    } catch (profileError) {
      setAccountHistoryError(
        profileError instanceof Error
          ? profileError.message
          : "Javni profil nije dostupan.",
      );
    } finally {
      setAccountHistoryLoading(false);
    }
  }, []);

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
      const profileUsername = params.get("profile");
      if (profileUsername) void openPublicProfile(profileUsername);
      const hasPasswordResetFragment = window.location.hash.startsWith(
        PASSWORD_RESET_FRAGMENT,
      );
      const resetToken = passwordResetTokenFromFragment(window.location.hash);
      if (hasPasswordResetFragment) {
        const cleanUrl = new URL(window.location.href);
        cleanUrl.hash = "";
        window.history.replaceState({}, "", cleanUrl);
      }
      if (resetToken) {
        setAccountForm((current) => ({
          ...current,
          password: "",
          passwordConfirmation: "",
          resetToken,
        }));
        setAccountDialogMode("reset");
        setAccountDialogOpen(true);
      }

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
  }, [openPublicProfile]);

  useEffect(() => {
    let active = true;
    apiRequest<AccountResponse>("/account/me")
      .then((payload) => {
        if (!active) return;
        const restoredAccount = accountFromResponse(payload);
        if (!restoredAccount) return;
        setAccount(restoredAccount);
        setAccountStats(payload.stats ?? restoredAccount.stats ?? null);
        setManagerName((current) => current || restoredAccount.username);
      })
      .catch((restoreError) => {
        if (
          restoreError instanceof ApiError &&
          (restoreError.status === 401 || restoreError.status === 404)
        ) {
          return;
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!accountDialogOpen && !accountPanelOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (accountDialogOpen) {
        setAccountDialogOpen(false);
        setAccountError("");
        setAccountNotice("");
        setAccountForm((current) => ({
          ...current,
          password: "",
          passwordConfirmation: "",
        }));
      }
      if (accountPanelOpen) {
        setAccountPanelOpen(false);
        setSelectedHistoryId(null);
        setSelectedHistorySeason(null);
      }
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [accountDialogOpen, accountPanelOpen]);

  const activeScreen: Screen = room
    ? room.status === "lobby"
      ? "lobby"
      : room.status === "drafting"
        ? "draft"
        : room.status === "complete"
          ? "results"
          : "home"
    : screen;

  useEffect(() => {
    const mobileDraftWheel =
      activeScreen === "draft" &&
      window.matchMedia("(max-width: 900px)").matches
        ? document.querySelector<HTMLElement>(".wheel-panel")
        : null;
    const top = mobileDraftWheel
      ? window.scrollY + mobileDraftWheel.getBoundingClientRect().top
      : 0;
    window.scrollTo({ top, left: 0, behavior: "auto" });
  }, [activeScreen, seasonPhase]);

  const acceptRoomState = useCallback((nextRoom: Room) => {
    setRoom((currentRoom) => {
      if (
        currentRoom?.code === nextRoom.code &&
        currentRoom.version > nextRoom.version
      ) {
        return currentRoom;
      }
      return nextRoom;
    });
  }, []);

  const refreshRoom = useCallback(async () => {
    if (!room || !participantToken) return;
    try {
      const refreshed = await apiRequest<Room>(
        `/rooms/${room.code}`,
        {},
        participantToken,
      );
      acceptRoomState(refreshed);
    } catch (refreshError) {
      if (refreshError instanceof ApiError && refreshError.code === "room_expired") {
        setError("Soba je istekla. Pokreni novu igru.");
      }
    }
  }, [acceptRoomState, participantToken, room]);

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

  const openAccountSurface = () => {
    setAccountError("");
    setAccountNotice("");
    if (!account) {
      setAccountDialogMode(accountForm.resetToken ? "reset" : "login");
      setAccountDialogOpen(true);
      return;
    }
    setPublicProfileView(false);
    setSelectedHistoryId(null);
    setSelectedHistorySeason(null);
    setAccountPanelOpen(true);
    void loadOwnHistory(account);
  };

  const closeAccountPanel = () => {
    setAccountPanelOpen(false);
    setSelectedHistoryId(null);
    setSelectedHistorySeason(null);
    if (publicProfileView) {
      const url = new URL(window.location.href);
      url.searchParams.delete("profile");
      window.history.replaceState({}, "", url);
    }
    setPublicProfileView(false);
  };

  const submitAccount = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAccountError("");
    setAccountNotice("");
    setAccountBusy(true);
    try {
      if (accountDialogMode === "forgot") {
        const response = await apiRequest<PasswordRecoveryResponse>(
          "/account/password-reset/request",
          {
            method: "POST",
            body: JSON.stringify({ email: accountForm.email.trim() }),
          },
        );
        let exposedResetToken = response.resetToken?.trim() ?? "";
        if (!exposedResetToken && response.resetUrl) {
          try {
            exposedResetToken = passwordResetTokenFromFragment(
              new URL(response.resetUrl, window.location.href).hash,
            );
          } catch {
            exposedResetToken = "";
          }
        }
        setAccountForm((current) => ({
          ...current,
          password: "",
          passwordConfirmation: "",
          resetToken: exposedResetToken || current.resetToken,
        }));
        if (exposedResetToken) {
          setAccountDialogMode("reset");
          setAccountNotice(
            "Zahtjev je prihvaćen. U lokalnom razvoju možeš odmah postaviti novu lozinku.",
          );
        } else {
          setAccountNotice(
            "Ako račun s tim e-mailom postoji, poslat ćemo poveznicu za novu lozinku.",
          );
        }
        return;
      }

      if (accountDialogMode === "reset") {
        if (!accountForm.resetToken) {
          throw new ApiError(
            "Poveznica za promjenu lozinke nije valjana. Zatraži novu poveznicu.",
            "invalid_password_reset_token",
            400,
          );
        }
        if (accountForm.password !== accountForm.passwordConfirmation) {
          throw new ApiError(
            "Upisane lozinke nisu jednake.",
            "password_confirmation_mismatch",
            400,
          );
        }
        await apiRequest<{ ok?: boolean }>("/account/password-reset/complete", {
          method: "POST",
          body: JSON.stringify({
            token: accountForm.resetToken,
            newPassword: accountForm.password,
          }),
        });
        setAccountForm((current) => ({
          ...current,
          password: "",
          passwordConfirmation: "",
          resetToken: "",
        }));
        setAccountDialogMode("login");
        setAccount(null);
        setAccountStats(null);
        setAccountHistory(null);
        setSelectedHistoryId(null);
        setSelectedHistorySeason(null);
        setAccountPanelOpen(false);
        setAccountNotice(
          "Lozinka je promijenjena. Sada se možeš prijaviti novom lozinkom.",
        );
        return;
      }

      const registering = accountDialogMode === "register";
      const payload = registering
        ? {
            username: accountForm.username.trim(),
            email: accountForm.email.trim(),
            password: accountForm.password,
          }
        : {
            identifier: accountForm.identifier.trim(),
            password: accountForm.password,
          };
      const response = await apiRequest<AccountResponse>(
        registering ? "/account/register" : "/account/login",
        {
          method: "POST",
          body: JSON.stringify(payload),
        },
      );
      const nextAccount = accountFromResponse(response);
      if (!nextAccount) {
        throw new ApiError(
          "Prijava je uspjela, ali profil nije vraćen.",
          "invalid_account_response",
        );
      }

      setAccount(nextAccount);
      setAccountStats(response.stats ?? nextAccount.stats ?? null);
      setManagerName((current) => current || nextAccount.username);
      setAccountForm((current) => ({
        ...current,
        password: "",
        passwordConfirmation: "",
        resetToken: "",
      }));

      if (room && participantToken) {
        try {
          const claim = await apiRequest<{
            claimed: boolean;
            participantId?: string;
            room?: Room;
          }>(`/rooms/${room.code}/claim`, {
            method: "POST",
            body: JSON.stringify({ participantToken }),
          });
          if (claim.room) setRoom(claim.room);
          setNotice(
            claim.claimed
              ? "Račun je povezan s ovom sobom. Sezona će biti spremljena."
              : "Prijavljen si. Ova soba već je povezana s računom.",
          );
        } catch (claimError) {
          setNotice(
            claimError instanceof ApiError && claimError.status === 409
              ? "Prijavljen si, ali ova momčad već pripada drugom računu."
              : "Prijavljen si. Aktivnu sobu nismo uspjeli povezati s profilom.",
          );
        }
      } else {
        setNotice(
          registering
            ? "Račun je spreman. Sve buduće sezone automatski se spremaju."
            : "Prijava uspješna.",
        );
      }

      setAccountDialogOpen(false);
      setPublicProfileView(false);
      setSelectedHistoryId(null);
      setSelectedHistorySeason(null);
      setAccountPanelOpen(true);
      await loadOwnHistory(nextAccount);
    } catch (submitError) {
      setAccountError(
        submitError instanceof Error
          ? submitError.message
          : "Račun trenutačno nije dostupan.",
      );
    } finally {
      setAccountBusy(false);
    }
  };

  const selectHistorySeason = async (historyId: string) => {
    if (publicProfileView) return;
    setSelectedHistoryId(historyId);
    setSelectedHistorySeason(null);
    setHistoryDetailLoading(true);
    setAccountHistoryError("");
    try {
      const response = await apiRequest<HistoryDetailResponse>(
        `/account/history/${encodeURIComponent(historyId)}`,
      );
      if (!response.season) {
        throw new ApiError("Zapis sezone nije pronađen.", "history_not_found", 404);
      }
      setSelectedHistorySeason(response.season);
    } catch (detailError) {
      setAccountHistoryError(
        detailError instanceof Error
          ? detailError.message
          : "Zapis sezone nije dostupan.",
      );
    } finally {
      setHistoryDetailLoading(false);
    }
  };

  const logoutAccount = async () => {
    setAccountBusy(true);
    try {
      await apiRequest<{ ok: boolean }>("/account/logout", {
        method: "POST",
      });
      setAccount(null);
      setAccountStats(null);
      setAccountHistory(null);
      setSelectedHistoryId(null);
      setSelectedHistorySeason(null);
      setAccountPanelOpen(false);
      setNotice("Odjavljen si. Anonimna igra i dalje je dostupna.");
    } catch (logoutError) {
      setAccountHistoryError(
        logoutError instanceof Error
          ? logoutError.message
          : "Odjava nije uspjela.",
      );
    } finally {
      setAccountBusy(false);
    }
  };

  const copyPublicProfile = async () => {
    if (!account) return;
    const url = new URL(window.location.origin);
    url.pathname = window.location.pathname;
    url.searchParams.set("profile", account.username);
    try {
      await navigator.clipboard.writeText(url.toString());
      setNotice("Poveznica javnog profila je kopirana.");
    } catch {
      setNotice(url.toString());
    }
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
        await mutateRoomWithRetry({
          initialRoom: auth.room,
          path: `/rooms/${auth.roomCode}/start`,
          token: auth.participantToken,
          buildPayload: (latestRoom) => ({
            expectedVersion: latestRoom.version,
          }),
          acceptRoomState,
          isApplied: (latestRoom) =>
            latestRoom.status === "drafting" ||
            latestRoom.status === "complete",
          canRetry: (latestRoom) => latestRoom.status === "lobby",
        });
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

  const startLiveDraft = useCallback(async () => {
    if (!room || !participantToken || busy) return;
    const mutationKey = `${room.code}:${participantId}`;
    if (!beginRoomMutation(mutationKey)) return;
    clearMessages();
    setBusy(true);
    try {
      await mutateRoomWithRetry({
        initialRoom: room,
        path: `/rooms/${room.code}/start`,
        token: participantToken,
        buildPayload: (latestRoom) => ({
          expectedVersion: latestRoom.version,
        }),
        acceptRoomState,
        isApplied: (latestRoom) =>
          latestRoom.status === "drafting" ||
          latestRoom.status === "complete",
        canRetry: (latestRoom) => latestRoom.status === "lobby",
      });
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Draft nije pokrenut.");
      await refreshRoom();
    } finally {
      finishRoomMutation(mutationKey);
      setBusy(false);
    }
  }, [
    acceptRoomState,
    busy,
    participantId,
    participantToken,
    refreshRoom,
    room,
  ]);

  const spin = useCallback(
    async (reroll = false) => {
      if (
        !room ||
        !me ||
        !participantToken ||
        busy ||
        spinRequestInFlightRef.current
      ) {
        return;
      }
      if (
        room.settings.draftMode === "position-first" &&
        !reroll &&
        !lockedSlotId
      ) {
        setError("Prvo odaberi praznu poziciju na terenu.");
        return;
      }
      spinRequestInFlightRef.current = true;
      clearMessages();
      setBusy(true);
      try {
        const roomCode = room.code;
        const initialTurn = me.turn;
        const initialSpinIdentity = spinIdentity(me.currentSpin);
        const initialRerollsRemaining = me.rerollsRemaining;
        let requestRoom = room;
        let requestManager = me;
        let nextRoom: Room | null = null;
        let animationCatalog = catalog;
        if (!animationCatalog?.clubSeasons?.length) {
          try {
            animationCatalog =
              await apiRequest<CatalogInventory>("/catalog");
            setCatalog(animationCatalog);
          } catch {
            // The spin can still complete if the decorative reel catalog is
            // temporarily unavailable.
          }
        }
        const reducedMotion = window.matchMedia(
          "(prefers-reduced-motion: reduce)",
        ).matches;
        if (animationCatalog) {
          const pendingStrip = buildPendingSpinItems(
            animationCatalog,
            room.settings,
            room.seed,
            me.seat,
            me.turn,
          );
          if (pendingStrip) {
            setSpinAnimation({
              key: `pending-${room.code}-${me.id}-${me.turn}-${Date.now()}`,
              items: pendingStrip.items,
              landingIndex: 0,
              loopLength: pendingStrip.loopLength,
              phase: "pending",
              round: me.turn,
              selected: null,
              reducedMotion,
            });
          }
        }

        for (let attempt = 0; ; attempt += 1) {
          const payload: Record<string, unknown> = {
            expectedVersion: requestRoom.version,
            expectedTurn: requestManager.turn,
            reroll,
          };
          if (requestRoom.settings.draftMode === "position-first" && !reroll) {
            payload.slotId = lockedSlotId;
          }

          try {
            nextRoom = await apiRequest<Room>(
              `/rooms/${room.code}/spin`,
              { method: "POST", body: JSON.stringify(payload) },
              participantToken,
            );
            acceptRoomState(nextRoom);
            break;
          } catch (requestError) {
            if (
              !(requestError instanceof ApiError) ||
              !SPIN_CONFLICT_CODES.has(requestError.code)
            ) {
              throw requestError;
            }

            const freshRoom = await apiRequest<Room>(
              `/rooms/${roomCode}`,
              {},
              participantToken,
            );
            acceptRoomState(freshRoom);
            const freshManager = freshRoom.participants.find(
              (participant) => participant.id === participantId,
            );
            if (!freshManager) {
              throw new ApiError(
                "Tvoja momčad više nije dostupna u ovoj sobi.",
                "participant_not_found",
                404,
              );
            }

            const freshSpinIdentity = spinIdentity(freshManager.currentSpin);
            const simultaneousSpinCompleted = reroll
              ? freshManager.turn === initialTurn &&
                Boolean(freshSpinIdentity) &&
                (freshSpinIdentity !== initialSpinIdentity ||
                  freshManager.rerollsRemaining < initialRerollsRemaining)
              : freshManager.turn === initialTurn &&
                Boolean(
                  freshSpinIdentity &&
                    freshSpinIdentity !== initialSpinIdentity,
                );
            if (simultaneousSpinCompleted) {
              nextRoom = freshRoom;
              break;
            }

            const requestedSlotWasFilled =
              !reroll &&
              freshRoom.settings.draftMode === "position-first" &&
              Boolean(
                lockedSlotId &&
                  freshManager.filledSlotIds.includes(lockedSlotId),
              );
            const terminalState =
              freshRoom.status !== "drafting" ||
              freshManager.status !== "drafting" ||
              freshManager.turn !== initialTurn ||
              requestedSlotWasFilled ||
              (reroll &&
                (!freshManager.currentSpin ||
                  freshManager.rerollsRemaining <= 0));
            if (terminalState) {
              setSpinAnimation(null);
              return;
            }

            requestRoom = freshRoom;
            requestManager = freshManager;
            const retryDelay =
              SPIN_CONFLICT_RETRY_DELAYS_MS[
                Math.min(
                  attempt,
                  SPIN_CONFLICT_RETRY_DELAYS_MS.length - 1,
                )
              ];
            await waitForRetry(retryDelay);
          }
        }

        if (!nextRoom) {
          setSpinAnimation(null);
          return;
        }
        setSelectedPlayerId(null);
        const nextManager = nextRoom.participants.find(
          (participant) => participant.id === participantId,
        );
        const selectedSpin = nextManager?.currentSpin;
        if (selectedSpin) {
          const settledStrip = buildSpinItems(
            animationCatalog,
            selectedSpin,
            nextRoom.settings,
            nextRoom.seed,
            nextManager.seat,
          );
          setSpinAnimation({
            key: `settled-${selectedSpin.turn}-${selectedSpin.spinNumber}-${selectedSpin.clubSeasonId}`,
            items: settledStrip.items,
            landingIndex: settledStrip.landingIndex,
            phase: "settled",
            round: selectedSpin.turn,
            selected: selectedSpin,
            reducedMotion,
          });
          await new Promise((resolve) =>
            window.setTimeout(resolve, reducedMotion ? 1_000 : 4_700),
          );
          setSpinAnimation(null);
        } else {
          setSpinAnimation(null);
        }
      } catch (spinError) {
        setSpinAnimation(null);
        setError(spinError instanceof Error ? spinError.message : "Kotač se nije zavrtio.");
        await refreshRoom();
      } finally {
        spinRequestInFlightRef.current = false;
        setBusy(false);
      }
    },
    [
      acceptRoomState,
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

  const pickPlayer = useCallback(
    async (player: Player, slotId: string) => {
      if (
        !room ||
        !me ||
        !participantToken ||
        busy
      ) {
        return;
      }
      const mutationKey = `${room.code}:${participantId}`;
      if (!beginRoomMutation(mutationKey)) return;
      clearMessages();
      setBusy(true);
      const requestedTurn = me.turn;
      const requestedSpinIdentity = spinIdentity(me.currentSpin);
      const requestedSlotId =
        room.settings.draftMode === "position-first"
          ? me.currentSpin?.lockedSlotId ?? slotId
          : slotId;
      try {
        await mutateRoomWithRetry({
          initialRoom: room,
          path: `/rooms/${room.code}/pick`,
          token: participantToken,
          buildPayload: (latestRoom) => ({
            expectedVersion: latestRoom.version,
            expectedTurn: requestedTurn,
            playerSeasonId: player.id,
            slotId: requestedSlotId,
          }),
          acceptRoomState,
          isApplied: (latestRoom) => {
            const latestManager = latestRoom.participants.find(
              (participant) => participant.id === participantId,
            );
            return Boolean(
              latestManager?.picks.some(
                (pick) =>
                  pick.turn === requestedTurn &&
                  pick.player.id === player.id &&
                  pick.slotId === requestedSlotId,
              ),
            );
          },
          canRetry: (latestRoom) => {
            const latestManager = latestRoom.participants.find(
              (participant) => participant.id === participantId,
            );
            return Boolean(
              latestRoom.status === "drafting" &&
                latestManager?.status === "drafting" &&
                latestManager.turn === requestedTurn &&
                spinIdentity(latestManager.currentSpin) ===
                  requestedSpinIdentity &&
                !latestManager.filledSlotIds.includes(requestedSlotId),
            );
          },
        });
        setSelectedPlayerId(null);
        setLockedSlotId(null);
      } catch (pickError) {
        setError(pickError instanceof Error ? pickError.message : "Igrač nije odabran.");
        await refreshRoom();
      } finally {
        finishRoomMutation(mutationKey);
        setBusy(false);
      }
    },
    [
      acceptRoomState,
      busy,
      me,
      participantId,
      participantToken,
      refreshRoom,
      room,
    ],
  );

  const movePick = useCallback(
    async (fromSlotId: string, toSlotId: string, swap: boolean) => {
      if (
        !room ||
        !me ||
        !participantToken ||
        busy
      ) {
        return;
      }
      const sourcePick = me.picks.find((pick) => pick.slotId === fromSlotId);
      if (!sourcePick) return;
      const targetPick = me.picks.find((pick) => pick.slotId === toSlotId);
      const mutationKey = `${room.code}:${participantId}`;
      if (!beginRoomMutation(mutationKey)) return;
      clearMessages();
      setBusy(true);
      try {
        await mutateRoomWithRetry({
          initialRoom: room,
          path: `/rooms/${room.code}/move`,
          token: participantToken,
          buildPayload: (latestRoom) => ({
            expectedVersion: latestRoom.version,
            fromSlotId,
            toSlotId,
            swap,
          }),
          acceptRoomState,
          isApplied: (latestRoom) => {
            const latestManager = latestRoom.participants.find(
              (participant) => participant.id === participantId,
            );
            const latestSource = latestManager?.picks.find(
              (pick) => pick.slotId === fromSlotId,
            );
            const latestTarget = latestManager?.picks.find(
              (pick) => pick.slotId === toSlotId,
            );
            if (latestTarget?.player.id !== sourcePick.player.id) return false;
            return targetPick
              ? latestSource?.player.id === targetPick.player.id
              : !latestSource;
          },
          canRetry: (latestRoom) => {
            const latestManager = latestRoom.participants.find(
              (participant) => participant.id === participantId,
            );
            const latestSource = latestManager?.picks.find(
              (pick) => pick.slotId === fromSlotId,
            );
            const latestTarget = latestManager?.picks.find(
              (pick) => pick.slotId === toSlotId,
            );
            return Boolean(
              latestRoom.status === "drafting" &&
                latestManager?.status === "drafting" &&
                latestSource?.player.id === sourcePick.player.id &&
                (targetPick
                  ? latestTarget?.player.id === targetPick.player.id
                  : !latestTarget),
            );
          },
        });
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
        finishRoomMutation(mutationKey);
        setBusy(false);
      }
    },
    [
      acceptRoomState,
      busy,
      me,
      participantId,
      participantToken,
      refreshRoom,
      room,
    ],
  );

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
          <p className="eyebrow">SHNL 36-0 · HRVATSKA LIGA · 1995/96 — 2025/26</p>
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
          <div className={`entry-account-note${account ? " connected" : ""}`}>
            <span aria-hidden="true">{account ? "✓" : "＋"}</span>
            <p>
              {account ? (
                <>
                  Sezona se sprema na profil <strong>@{account.username}</strong>.
                </>
              ) : (
                <>Igraj anonimno ili izradi račun za trajnu povijest sezona.</>
              )}
            </p>
            <button type="button" onClick={openAccountSurface}>
              {account ? "Profil" : "Prijava"}
            </button>
          </div>
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
    const draftedPicks = room.settings.slots.flatMap((slot) => {
      const pick = me.picks.find((item) => item.slotId === slot.id);
      return pick ? [{ pick, slot }] : [];
    });
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
                <details className="mobile-squad-summary">
                  <summary>
                    <span>
                      <strong>Tvoja XI</strong>
                      <small>
                        {me.picks.length}/{room.settings.targetPicks} odabrano
                      </small>
                    </span>
                    <b aria-hidden="true">PREGLED ↓</b>
                  </summary>
                  {draftedPicks.length ? (
                    <ul aria-label="Odabrani igrači u Tvojoj XI">
                      {draftedPicks.map(({ pick, slot }) => (
                        <li key={slot.id}>
                          <span
                            className={`mobile-squad-position ${positionGroupClass(
                              slot.label,
                            )}`}
                          >
                            {slot.label}
                          </span>
                          <strong>{pick.player.name}</strong>
                          <small
                            aria-label={
                              typeof pick.selectedRating === "number"
                                ? `Ocjena ${Math.round(pick.selectedRating)}`
                                : "Ocjena nije prikazana"
                            }
                          >
                            {typeof pick.selectedRating === "number"
                              ? Math.round(pick.selectedRating)
                              : "—"}
                          </small>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>Još nema odabranih igrača.</p>
                  )}
                </details>
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
                              <i
                                className={positionGroupClass(position)}
                                key={position}
                              >
                                {position}
                              </i>
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
                                  className={positionGroupClass(
                                    slot?.label ?? slotId,
                                  )}
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
    const text = `SHNL 36-0: ${me.name} — ${finish} mjesto, ${me.result.points} bodova (${me.result.wins}-${me.result.draws}-${me.result.losses}).`;
    try {
      if (navigator.share) {
        await navigator.share({ title: "SHNL 36-0", text, url: window.location.href });
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
        .slice(activeManagerFixture ? -4 : -5)
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
          <button
            type="button"
            className={`result-account-status${account ? " saved" : ""}`}
            onClick={openAccountSurface}
          >
            <span aria-hidden="true">{account ? "✓" : "＋"}</span>
            {account
              ? `Spremljeno na @${account.username} · otvori povijest`
              : "Sljedeću sezonu spremi na profil"}
          </button>
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
                    <span
                      className={positionGroupClass(
                        player.slotId ?? player.positions?.[0],
                      )}
                    >
                      {player.slotId?.toUpperCase() ??
                        player.positions?.[0] ??
                        "—"}
                    </span>
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
      <Header
        stage={stage}
        room={room}
        account={account}
        onHome={goHome}
        onAccount={openAccountSurface}
      />
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
      {accountDialogOpen ? (
        <AccountDialog
          mode={accountDialogMode}
          form={accountForm}
          busy={accountBusy}
          error={accountError}
          notice={accountNotice}
          onMode={(nextMode) => {
            setAccountDialogMode(nextMode);
            setAccountError("");
            setAccountNotice("");
            setAccountForm((current) => ({
              ...current,
              email:
                nextMode === "forgot" &&
                !current.email &&
                current.identifier.includes("@")
                  ? current.identifier
                  : current.email,
              password: "",
              passwordConfirmation: "",
              resetToken: current.resetToken,
            }));
          }}
          onChange={(field, value) =>
            setAccountForm((current) => ({ ...current, [field]: value }))
          }
          onSubmit={submitAccount}
          onClose={() => {
            setAccountDialogOpen(false);
            setAccountError("");
            setAccountNotice("");
            setAccountForm((current) => ({
              ...current,
              password: "",
              passwordConfirmation: "",
            }));
          }}
        />
      ) : null}
      {accountPanelOpen ? (
        <AccountPanel
          history={accountHistory}
          selectedSeason={selectedHistorySeason}
          selectedId={selectedHistoryId}
          loading={accountHistoryLoading}
          detailLoading={historyDetailLoading}
          error={accountHistoryError}
          publicView={publicProfileView}
          onClose={closeAccountPanel}
          onSelect={(id) => void selectHistorySeason(id)}
          onBack={() => {
            setSelectedHistoryId(null);
            setSelectedHistorySeason(null);
            setAccountHistoryError("");
          }}
          onLogout={() => void logoutAccount()}
          onCopyProfile={() => void copyPublicProfile()}
        />
      ) : null}
      <footer className="site-footer">
        <p>
          SHNL 36-0 je nezavisna fan-made HNL draft igra koju je napravio Josip
          Nigojević. Nije povezana s HNS-om, klubovima, igračima ili pružateljima
          ocjena. Grbovi se prikazuju isključivo radi identifikacije i ostaju
          vlasništvo svojih nositelja.
        </p>
        <span>Podaci: HNS Riznica / COMET + sekundarni povijesni izvori</span>
      </footer>
    </div>
  );
}
