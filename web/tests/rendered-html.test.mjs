import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the Croatian HNL club-season draft entry", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<html[^>]*lang="hr"/i);
  assert.match(html, /<title>SHNL 36-0 — Povijesni HNL draft<\/title>/i);
  assert.match(
    html,
    /<meta[^>]+name="application-name"[^>]+content="SHNL 36-0"/i,
  );
  assert.match(
    html,
    /<link[^>]+rel="canonical"[^>]+href="https:\/\/hnldraft\.com\/"/i,
  );
  assert.match(
    html,
    /<meta[^>]+property="og:site_name"[^>]+content="SHNL 36-0"/i,
  );
  assert.match(html, /type="application\/ld\+json"/i);
  assert.match(html, /"name":"SHNL 36-0"/);
  assert.match(html, /Zavrti sezonu/);
  assert.match(html, /Live draft/);
  assert.match(html, /Igraj sam/);
  assert.match(html, /Imaš kod sobe/);
  assert.match(html, /Zavrti[\s\S]*Odaberi[\s\S]*Postavi[\s\S]*Simuliraj/);
  assert.match(html, /Preskoči na sadržaj/);
  assert.doesNotMatch(html, /Your site is taking shape|Codex is working/);
});

test("keeps room flows, disclosures, and accessible structure in source", async () => {
  const [page, layout, css, packageJson] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
    readFile(new URL("../package.json", import.meta.url), "utf8"),
  ]);

  assert.match(page, /\/rooms\/\$\{auth\.roomCode\}\/start/);
  assert.match(page, /\/rooms\/\$\{room\.code\}\/spin/);
  assert.match(page, /\/rooms\/\$\{room\.code\}\/pick/);
  assert.match(page, /function ClubSeasonReel/);
  assert.match(page, /club-season-reel/);
  assert.match(page, /const CLUB_CREST_IDS = new Set/);
  assert.match(page, /const CLUB_CREST_ALIASES/);
  assert.match(page, /"hnk-gorica": "24575"/);
  assert.match(page, /CLUB_CREST_ALIASES\[sourceId\]/);
  assert.match(page, /className="club-logo"/);
  assert.match(page, /Grbovi se prikazuju[\s\S]*radi identifikacije/);
  assert.doesNotMatch(page, /className="reel-focus"/);
  assert.match(page, /Kotač se vrti/);
  assert.match(page, /Simuliraj sezonu/);
  assert.match(page, /Preskoči sve/);
  assert.match(page, /Svih 36 utakmica/);
  assert.match(page, /me\?\.result\?\.matches/);
  assert.match(page, /navigator\.clipboard/);
  assert.match(page, /sessionStorage/);
  assert.match(page, /aria-live="polite"/);
  assert.match(page, /Ocjene su[\s\S]*ne službene ocjene HNS-a/);
  assert.match(
    page,
    /ne\s+glumi da je svaka povijesna registracija već potpuna/,
  );
  assert.match(page, /ne službena HNS prognoza/);
  assert.doesNotMatch(page, />SEED</);
  assert.doesNotMatch(page, /SEZONA ZAVRŠENA · SEED/);
  assert.doesNotMatch(page, /seed-a sobe/);
  assert.doesNotMatch(page, /Seed \$\{room\.seed\}/);
  assert.match(layout, /<html lang="hr">/);
  assert.match(css, /@keyframes clubReelStop/);
  assert.match(css, /@keyframes clubReelLoop/);
  assert.match(css, /\.reel-pending \.reel-track/);
  assert.match(css, /\.reel-settled \.reel-item\.is-selected/);
  assert.match(css, /\.reel-settled \.reel-item\.is-neighbor/);
  assert.match(css, /grid-template-areas:\s*"club times season"/);
  assert.match(css, /\.matchweek-console/);
  assert.match(css, /\.match-card\.featured/);
  assert.match(css, /\.season-record-grid/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /forced-colors:\s*active/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});

test("ships a consistent SHNL 36-0 search and install identity", async () => {
  const [page, layout, manifest, robots, sitemap, favicon] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/manifest.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/robots.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/sitemap.ts", import.meta.url), "utf8"),
    readFile(new URL("../public/favicon.svg", import.meta.url), "utf8"),
  ]);

  assert.match(page, /aria-label="SHNL 36-0 naslovnica"/);
  assert.match(page, />SHNL</);
  assert.match(page, /SHNL 36-0 · HRVATSKA LIGA/);
  assert.match(page, /SHNL 36-0 je nezavisna fan-made HNL draft igra/);
  assert.match(layout, /const siteName = "SHNL 36-0"/);
  assert.match(layout, /alternates:\s*\{\s*canonical:\s*"\/"/);
  assert.match(layout, /siteName/);
  assert.match(layout, /"@type": "WebSite"/);
  assert.match(layout, /"@type": "VideoGame"/);
  assert.match(manifest, /name: "SHNL 36-0"/);
  assert.match(manifest, /short_name: "SHNL 36-0"/);
  assert.match(robots, /sitemap: `\$\{siteUrl\}\/sitemap\.xml`/);
  assert.match(sitemap, /url: `\$\{siteUrl\}\/`/);
  assert.match(favicon, /#B6FF24/i);
});

test("ships cookie-authenticated accounts with durable season history", async () => {
  const [page, css] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  assert.match(page, /credentials:\s*"include"/);
  assert.match(page, /"\/account\/register"/);
  assert.match(page, /"\/account\/login"/);
  assert.match(page, /"\/account\/logout"/);
  assert.match(page, /"\/account\/me"/);
  assert.match(page, /\/account\/history\?limit=100&offset=0/);
  assert.match(page, /`\/account\/history\/\$\{encodeURIComponent\(historyId\)\}`/);
  assert.match(page, /`\/profiles\/\$\{encodeURIComponent\(cleanUsername\)\}`/);
  assert.match(page, /`\/rooms\/\$\{room\.code\}\/claim`/);
  assert.match(page, /JSON\.stringify\(\{\s*participantToken\s*\}\)/);
  assert.match(page, /function AccountDialog/);
  assert.match(page, /function AccountPanel/);
  assert.match(page, /setAccountStats\(normalized\.stats\)/);
  assert.doesNotMatch(page, /\.\.\.\(currentStats \?\? accountStats/);
  assert.match(page, /Povijest sezona/);
  assert.match(page, /Kopiraj javni profil/);
  assert.match(page, /minLength=\{registering \? 15 : undefined\}/);
  assert.match(page, /Račun nije obavezan za igru/);
  assert.match(css, /\.account-modal-backdrop/);
  assert.match(css, /\.account-stat-grid/);
  assert.match(css, /\.account-season-list/);
  assert.match(css, /\.history-pitch-player/);
});

test("retries simultaneous stale spins without duplicate submissions", async () => {
  const page = await readFile(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(
    page,
    /SPIN_CONFLICT_CODES = new Set\(\["version_conflict", "turn_conflict"\]\)/,
  );
  assert.match(
    page,
    /SPIN_CONFLICT_RETRY_DELAYS_MS = \[90, 180, 360, 720\]/,
  );
  assert.match(page, /spinRequestInFlightRef\.current/);
  assert.match(page, /SPIN_CONFLICT_CODES\.has\(requestError\.code\)/);
  assert.match(page, /const freshRoom = await apiRequest<Room>/);
  assert.match(page, /acceptRoomState\(freshRoom\)/);
  assert.match(page, /const simultaneousSpinCompleted = reroll/);
  assert.match(page, /const terminalState =/);
  assert.match(page, /for \(let attempt = 0; ; attempt \+= 1\)/);
  assert.match(page, /Math\.min\(\s*attempt,\s*SPIN_CONFLICT_RETRY_DELAYS_MS\.length - 1/);
  assert.match(page, /await waitForRetry\(retryDelay\)/);
  assert.match(page, /throw requestError/);
  assert.doesNotMatch(page, /"spin_retry_exhausted"/);
  assert.doesNotMatch(
    page,
    /setError\(requestError instanceof Error \? requestError\.message/,
  );
});

test("resyncs and retries stale room mutations without committing twice", async () => {
  const page = await readFile(
    new URL("../app/page.tsx", import.meta.url),
    "utf8",
  );

  assert.match(
    page,
    /ROOM_MUTATION_CONFLICT_CODES = new Set\(\[\s*"version_conflict",\s*"turn_conflict",\s*\]\)/,
  );
  assert.match(
    page,
    /ROOM_MUTATION_RETRY_DELAYS_MS = \[90, 180, 360, 720, 1_000\]/,
  );
  assert.match(page, /async function mutateRoomWithRetry/);
  assert.match(page, /requestError\.status === 409/);
  assert.match(
    page,
    /ROOM_MUTATION_CONFLICT_CODES\.has\(requestError\.code\)/,
  );
  assert.match(
    page,
    /attempt <= ROOM_MUTATION_RETRY_DELAYS_MS\.length/,
  );
  assert.match(page, /JSON\.stringify\(buildPayload\(requestRoom\)\)/);
  assert.match(page, /`\/rooms\/\$\{initialRoom\.code\}`/);
  assert.match(page, /if \(isApplied\(freshRoom\)\) return freshRoom/);
  assert.match(page, /if \(!canRetry\(freshRoom\)\)/);
  assert.match(page, /requestRoom = freshRoom/);
  assert.match(
    page,
    /await waitForRetry\(ROOM_MUTATION_RETRY_DELAYS_MS\[attempt\]\)/,
  );
  assert.match(page, /const ACTIVE_ROOM_MUTATIONS = new Set<string>\(\)/);
  assert.match(page, /if \(!beginRoomMutation\(mutationKey\)\) return/);
  assert.match(page, /finishRoomMutation\(mutationKey\)/);
  assert.match(
    page,
    /path: `\/rooms\/\$\{room\.code\}\/pick`[\s\S]*pick\.turn === requestedTurn[\s\S]*pick\.player\.id === player\.id[\s\S]*pick\.slotId === requestedSlotId/,
  );
  assert.match(
    page,
    /spinIdentity\(latestManager\.currentSpin\) ===\s*requestedSpinIdentity/,
  );
  assert.match(
    page,
    /path: `\/rooms\/\$\{room\.code\}\/move`[\s\S]*latestTarget\?\.player\.id !== sourcePick\.player\.id/,
  );
  assert.match(
    page,
    /path: `\/rooms\/\$\{room\.code\}\/start`[\s\S]*expectedVersion: latestRoom\.version/,
  );
});

test("keeps the reel moving while waiting and shows distinct rows after landing", async () => {
  const [page, css] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);

  assert.match(page, /function buildPendingSpinItems/);
  assert.match(page, /const reelSeed = Math\.abs\(seed % 2_147_483_647\)/);
  assert.match(page, /const landingIndex = 17/);
  assert.match(page, /for \(let index = 0; index < 2; index \+= 1\)/);
  assert.match(page, /const avoidedNeighbors = \[selectedItem, \.\.\.previousTailItems\]/);
  assert.match(page, /"--reel-index": animation\.landingIndex/);
  assert.doesNotMatch(
    page,
    /"--reel-index": animation\.items\.length - 1/,
  );
  assert.match(page, /phase: "pending"/);
  assert.match(page, /phase: "settled"/);
  assert.match(page, /loopLength: pendingStrip\.loopLength/);
  assert.match(page, /Čekamo potvrdu poslužitelja\. Kotač ostaje u pokretu\./);
  assert.match(page, /window\.setTimeout\(resolve, reducedMotion \? 1_000 : 4_700\)/);
  assert.match(css, /animation: clubReelLoop 620ms linear infinite/);
  assert.match(css, /transform: translateY\(var\(--reel-loop-offset\)\)/);
});

test("ships a validated local crest for every catalog club identity", async () => {
  const [catalog, page, assetFiles] = await Promise.all([
    readFile(
      new URL("../../data/hnl_draft_catalog.json", import.meta.url),
      "utf8",
    ).then(JSON.parse),
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readdir(new URL("../public/clubs/", import.meta.url)),
  ]);
  const expectedIds = [
    ...new Set(catalog.clubSeasons.map((record) => String(record.clubId))),
  ].sort();
  const crestSetSource = page.match(
    /const CLUB_CREST_IDS = new Set\(\[([\s\S]*?)\]\);/,
  )?.[1];
  assert.ok(crestSetSource, "CLUB_CREST_IDS is missing");
  const mappedIds = [
    ...crestSetSource.matchAll(/"([0-9]+)"/g),
  ].map((match) => match[1]).sort();
  const aliasSetSource = page.match(
    /const CLUB_CREST_ALIASES:[^{]+\{([\s\S]*?)\n\};/,
  )?.[1];
  assert.ok(aliasSetSource, "CLUB_CREST_ALIASES is missing");
  const aliases = Object.fromEntries(
    [...aliasSetSource.matchAll(/"([^"]+)": "([0-9]+)"/g)].map((match) => [
      match[1],
      match[2],
    ]),
  );
  const sourceManifest = JSON.parse(
    await readFile(
      new URL("../public/clubs/sources.json", import.meta.url),
      "utf8",
    ),
  );
  assert.deepEqual(mappedIds, expectedIds);
  assert.deepEqual(
    sourceManifest.crests.map((crest) => crest.id).sort(),
    expectedIds,
  );
  assert.deepEqual(
    assetFiles
      .filter((file) => file.endsWith(".png"))
      .map((file) => file.replace(/\.png$/, ""))
      .sort(),
    expectedIds,
  );

  const slug = (value) =>
    value
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
  for (const record of catalog.clubSeasons) {
    assert.equal(
      aliases[slug(record.club)],
      String(record.clubId),
      `crest alias is missing for ${record.club}`,
    );
  }

  for (const id of expectedIds) {
    const image = await readFile(
      new URL(`../public/clubs/${id}.png`, import.meta.url),
    );
    assert.ok(image.length > 1_000, `${id}.png is unexpectedly small`);
    assert.equal(
      image.subarray(0, 8).toString("hex"),
      "89504e470d0a1a0a",
      `${id}.png is not a PNG`,
    );
    const manifestEntry = sourceManifest.crests.find(
      (crest) => crest.id === id,
    );
    assert.equal(manifestEntry?.file, `${id}.png`);
    assert.equal(manifestEntry?.bytes, image.length);
    assert.equal(
      manifestEntry?.sourceUrl,
      `https://tmssl.akamaized.net/images/wappen/head/${id}.png`,
    );
  }
});

test("uses formation-specific pitch geometry and paced live match reveals", async () => {
  const [page, css] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/globals.css", import.meta.url), "utf8"),
  ]);
  const geometrySource = page.match(
    /const FORMATION_COORDINATES:[^=]+=\s*(\{[\s\S]*?\n\});\n\nconst AI_MATCH_REVEAL_MS/,
  );
  assert.ok(geometrySource, "formation coordinate map is missing");
  const geometry = JSON.parse(
    geometrySource[1].replace(/,\s*([}\]])/g, "$1"),
  );
  const symmetry = {
    "4-3-3": { pairs: [[1, 4], [2, 3], [6, 7], [8, 10]], centre: [0, 5, 9] },
    "4-4-2": { pairs: [[1, 4], [2, 3], [5, 8], [6, 7], [9, 10]], centre: [0] },
    "4-2-3-1": { pairs: [[1, 4], [2, 3], [5, 6], [7, 9]], centre: [0, 8, 10] },
    "4-5-1": { pairs: [[1, 4], [2, 3], [5, 9], [6, 8]], centre: [0, 7, 10] },
    "3-4-3": { pairs: [[1, 3], [4, 7], [5, 6], [8, 10]], centre: [0, 2, 9] },
    "3-5-2": { pairs: [[1, 3], [4, 8], [6, 7], [9, 10]], centre: [0, 2, 5] },
    "5-4-1": { pairs: [[1, 5], [2, 4], [6, 9], [7, 8]], centre: [0, 3, 10] },
    "4-1-2-1-2": { pairs: [[1, 4], [2, 3], [6, 7], [9, 10]], centre: [0, 5, 8] },
    "4-4-1-1": { pairs: [[1, 4], [2, 3], [5, 8], [6, 7]], centre: [0, 9, 10] },
    "5-3-2": { pairs: [[1, 5], [2, 4], [6, 8], [9, 10]], centre: [0, 3, 7] },
    "3-4-1-2": { pairs: [[1, 3], [4, 7], [5, 6], [9, 10]], centre: [0, 2, 8] },
    "4-2-2-2": { pairs: [[1, 4], [2, 3], [5, 6], [7, 8], [9, 10]], centre: [0] },
  };

  assert.deepEqual(Object.keys(geometry).sort(), Object.keys(symmetry).sort());
  for (const [formation, points] of Object.entries(geometry)) {
    assert.equal(points.length, 11, `${formation} must place all eleven slots`);
    for (const [x, y] of points) {
      assert.ok(x >= 0 && x <= 100, `${formation} has an invalid x coordinate`);
      assert.ok(y >= 0 && y <= 100, `${formation} has an invalid y coordinate`);
    }
    for (const [left, right] of symmetry[formation].pairs) {
      assert.equal(
        points[left][0] + points[right][0],
        100,
        `${formation} pair ${left}/${right} is not horizontally symmetric`,
      );
      assert.equal(
        points[left][1],
        points[right][1],
        `${formation} pair ${left}/${right} is not level`,
      );
    }
    for (const index of symmetry[formation].centre) {
      assert.equal(
        points[index][0],
        50,
        `${formation} central slot ${index} is not centred`,
      );
    }
  }

  assert.match(page, /normal:\s*1_400/);
  assert.match(page, /normal:\s*4_400/);
  assert.match(page, /function isManagerFixture/);
  assert.match(page, /opponentGoalMinutes/);
  assert.match(page, /revealMinute=\{displayedActiveMatchMinute\}/);
  assert.match(
    page,
    /Math\.min\(90, displayedActiveMatchMinute\) \/ 90/,
  );
  assert.match(css, /\.manager-match-progress/);
  assert.match(css, /\.match-card\.outcome-live/);
});
