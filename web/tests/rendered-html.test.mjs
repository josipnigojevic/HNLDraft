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
