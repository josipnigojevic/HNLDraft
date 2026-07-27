# HNL historical catalog audit

Generated catalog: `data/hnl_draft_catalog.json`

## Position-integrity repair

The legacy HNS fallback previously assigned every unresolved player all ten
positions, including goalkeeper and outfield roles. That made 192 player rows
universally selectable. The generator now applies this precedence:

1. Transfermarkt-derived player profile or index position.
2. A conservative, cited historical override.
3. `UNVERIFIED` / `["UNK"]` with `draftEligible: false`.

Generic source roles stay generic (`DEF`, `MID`, or `FWD`). Specific profile
roles now map only to the stated code: for example, left-back to `LB`, central
midfield to `CM`, and left winger to `LW`. No secondary roles are inferred.

Current result:

| Check | Result | Confidence |
|---|---:|---:|
| Playable club-seasons | 255 | 0.98 |
| Playable player-season rows | 8,196 | 0.98 |
| Cited historical position overrides | 191 | 0.90 |
| Unresolved position rows | 16 | 0.99 |
| GK combined with an outfield role | 0 | 1.00 |
| Universal-position fallbacks | 0 | 1.00 |
| Blank emitted player names | 0 | 1.00 |
| Playable squads with at least 11 eligible players | 255 of 255 | 1.00 |
| Playable squads able to field all 12 formations | 255 of 255 | 1.00 |

The 16 unresolved rows (14 unique names) remain visible as roster evidence but
cannot be drafted: Zoran Mamić, Krešimir Radić, Duje Špalj, Ante Tomić, Goran
Burčul, Mladen Ivančić, Matko Kalinić, Josip Bulat, Tomislav Grčić, Sandi
Dobrić, Ivan Bijelić, Marko Krešić, Johann Smith, and Jonatan Germano. Sandi
Dobrić and Ivan Bijelić each occur in two seasons. Multi-unit source
descriptions, identity conflicts, and names without a reliable position source
were not collapsed to an invented primary position.

## Playability gate and full-squad enrichment

Catalog generation no longer treats the old eight-row ingestion threshold as
proof that a club-season is playable. Before a candidate enters
`clubSeasons`, the generator now requires:

1. at least 11 distinct source-backed people;
2. at least 11 distinct players with verified draft eligibility; and
3. a one-player-per-slot assignment for **every** formation selectable before
   a spin.

The third check uses maximum bipartite matching with the same exact-role and
broad-unit compatibility rules as the runtime. A test compares all generator
slot definitions with the API definitions so formation changes cannot drift
silently. Each candidate receives a machine-readable
`coverage.playability` report containing unique counts, legal and missing
formations, failure reasons, and the validation method. Failed candidates are
retained with all source rows under `incompleteClubSeasons` and summarized in
`omitted`; they are not put on the playable reel.

`data/transfermarkt_squad_supplements.json` is an optional full-squad
enrichment input. Its `clubSeasons` records use the same source-cited player
row format as `supplemental_club_seasons.json`. The merge resolves a
club-season by club ID plus season first, then normalized club name plus
season. Players match by source player ID first and normalized name second.
Existing performance statistics and ratings remain authoritative; cited exact
positions repair only unresolved or broad-only roles, while missing roster
members are appended with null unpublished statistics. Even an enriched record
must pass the playability gate before promotion. Confidence: **0.99** for the
implemented validation and merge behavior.

The checked-in snapshot contains 143 source groups: 127 Transfermarkt
historical squad pages, seven FootballSquads roster fallbacks, and nine
combined records. FootballSquads is used only when the detailed historical
page is absent or its single primary positions cannot cover every selectable
formation. Its broad role remains inside the cited unit (`GK`, `DEF`, `MID`,
or `FWD`); it never grants cross-unit eligibility. The source acquisition is
offline and reproducible—the Docker application reads the checked-in JSON and
does not scrape either site at runtime.

## Source-backed club-season additions

| Club | Rows | Fields used | Coverage note | Source | Confidence |
|---|---:|---|---|---|---:|
| Hajduk Split | 32 | league appearances, league goals | Named competitive participants; cited page links to Hajduk history, RSSSF and HRnogomet | [Croatian Wikipedia season supplement](https://hr.wikipedia.org/wiki/Dodatak:HNK_Hajduk_Split_2001./02.) | 0.78 |
| HNK Rijeka | 25 | league starts, substitute appearances, league goals | Complete squad-statistics participant table; total appearances are starts plus the bracketed substitute count | [2001–02 HNK Rijeka season](https://en.wikipedia.org/wiki/2001%E2%80%9302_HNK_Rijeka_season) | 0.80 |
| Dinamo Zagreb | 26 | September squad membership and broad position, full-season league goals | Explicitly a September snapshot plus five later named scorers; league appearances are absent and remain `null` | [2001–02 NK Dinamo Zagreb season](https://en.wikipedia.org/wiki/2001%E2%80%9302_NK_Dinamo_Zagreb_season) | 0.65 |
| HNK Rijeka, 2004/05–2009/10 | 177 | league starts, substitute appearances, league goals | Six published competitive-player tables. The 2004/05 start total is internally inconsistent and is retained exactly as published. Sixty of 65 initially unresolved unique names received source-cited positions; all six squads can field the default XI. | [2004/05](https://en.wikipedia.org/wiki/2004%E2%80%9305_HNK_Rijeka_season), [2005/06](https://en.wikipedia.org/wiki/2005%E2%80%9306_HNK_Rijeka_season), [2006/07](https://en.wikipedia.org/wiki/2006%E2%80%9307_HNK_Rijeka_season), [2007/08](https://en.wikipedia.org/wiki/2007%E2%80%9308_HNK_Rijeka_season), [2008/09](https://en.wikipedia.org/wiki/2008%E2%80%9309_HNK_Rijeka_season), [2009/10](https://en.wikipedia.org/wiki/2009%E2%80%9310_HNK_Rijeka_season) | 0.80 |

The four-digit season parser was repaired so `2001/02` produces
`seasonStart: 2001` and IDs such as `supplement-447-2001`. Before the repair,
the supplement incorrectly produced year 3901 and was excluded by the game's
1995–2025 filter.

### Empty-name handling

Performance rows now use a source-backed display-name chain: cleaned profile
name, profile first plus last name, then the matching player-index full name.
Jordan N'Kololo (`sourcePlayerId: 228434`) is recovered from the local player
index. The single row for `sourcePlayerId: 427502` has no usable name in the
configured profile or player-index inputs and is skipped before catalog
emission. Confidence: **1.00** for the implemented behavior and generated
counts.

## Remaining omitted club-seasons

Full-squad enrichment promoted 39 previously omitted sparse groups and repaired
every club-season that had been selectable with fewer than 11 players. Seven
2004/05 groups remain explicitly omitted because neither checked source
provides enough cited roster evidence:

| Club-season | Cited rows | Status |
|---|---:|---|
| Kamen Ingrad 2004/05 | 17 | Full XI for nine formations; lacks enough cited defenders for three five-defender formations |
| Međimurje 2004/05 | 3 | Below 11 verified players |
| Osijek 2004/05 | 5 | Below the source-ingestion threshold |
| Pula 1856 2004/05 | 6 | Below the source-ingestion threshold |
| Varteks Varaždin 2004/05 | 4 | Below the source-ingestion threshold |
| Zadar 2004/05 | 1 | Below the source-ingestion threshold |
| Zagreb 2004/05 | 5 | Below the source-ingestion threshold |

The incomplete records and every reason are preserved under
`incompleteClubSeasons` / `omitted`; none can appear on the wheel. Confidence
that no incomplete squad is selectable: **1.00**. The catalog still reports
`completeHistoricalRosterArchive: false` because those seven source gaps are
not filled with invented names or roles.

## Reproduce and validate

Use the same raw input files and fixed paths:

```bash
python3 scripts/fetch_transfermarkt_squad_supplements.py --dry-run
# Run the acquisition only when intentionally refreshing the checked-in
# snapshot; the game itself has no live scraping dependency.
python3 scripts/fetch_transfermarkt_squad_supplements.py

python3 scripts/build_hnl_draft_catalog.py \
  --performances /private/tmp/tm_player_performances.csv \
  --profiles /private/tmp/tm_player_profiles.csv \
  --player-index /private/tmp/hnl_players.csv.gz \
  --hns-riznica-dir /private/tmp \
  --position-overrides data/historical_position_overrides.json \
  --supplemental-club-seasons data/supplemental_club_seasons.json \
  --club-season-enrichments data/transfermarkt_squad_supplements.json \
  --output data/hnl_draft_catalog.json

python3 -m unittest discover -s tests -v
```

The generated catalog records SHA-256 checksums for all main inputs, the
position-override file, and the supplemental club-season file. The catalog
generation is deterministic except for its `generatedAt` timestamp.
