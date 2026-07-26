import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
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
  assert.match(html, /<title>36–0 — HNL Club × Season Draft<\/title>/i);
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
  assert.match(css, /grid-template-areas:\s*"club times season"/);
  assert.match(css, /\.matchweek-console/);
  assert.match(css, /\.match-card\.featured/);
  assert.match(css, /\.season-record-grid/);
  assert.match(css, /prefers-reduced-motion:\s*reduce/);
  assert.match(css, /forced-colors:\s*active/);
  assert.doesNotMatch(packageJson, /react-loading-skeleton/);
});

test("ships a validated local crest for every catalog club identity", async () => {
  const expectedIds = [
    "144",
    "223",
    "2362",
    "24575",
    "2566",
    "314",
    "327",
    "419",
    "420",
    "447",
    "456",
    "485",
    "5107",
    "599",
    "918",
    "999",
    "11083",
    "11194",
    "12109",
  ].sort();
  const sourceManifest = JSON.parse(
    await readFile(
      new URL("../public/clubs/sources.json", import.meta.url),
      "utf8",
    ),
  );
  assert.deepEqual(
    sourceManifest.crests.map((crest) => crest.id).sort(),
    expectedIds,
  );

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
