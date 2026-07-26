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
| Club-seasons | 216 | 0.98 |
| Player-season rows | 4,696 | 0.98 |
| Cited historical position overrides | 191 | 0.90 |
| Unresolved position rows | 16 | 0.99 |
| GK combined with an outfield role | 0 | 1.00 |
| Universal-position fallbacks | 0 | 1.00 |
| Blank emitted player names | 0 | 1.00 |
| API-loader player rows accepted | 4,696 of 4,696 | 1.00 |
| Legacy/supplemental squads able to field the default XI | 18 of 18 | 1.00 |

The 16 unresolved rows (14 unique names) remain visible as roster evidence but
cannot be drafted: Zoran Mamić, Krešimir Radić, Duje Špalj, Ante Tomić, Goran
Burčul, Mladen Ivančić, Matko Kalinić, Josip Bulat, Tomislav Grčić, Sandi
Dobrić, Ivan Bijelić, Marko Krešić, Johann Smith, and Jonatan Germano. Sandi
Dobrić and Ivan Bijelić each occur in two seasons. Multi-unit source
descriptions, identity conflicts, and names without a reliable position source
were not collapsed to an invented primary position.

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
emission. Consequently the API loader skips zero generated rows and its 4,696
loaded players exactly match `coverage.players`. Confidence: **1.00** for the
implemented behavior and generated counts.

## Remaining omitted club-seasons

The 46 remaining omissions are Transfermarkt-derived KR1 groups with fewer than
the generator's minimum eight named player rows. The partial rows are retained
in the catalog's `omitted` array, but the missing roster members are not
inferred.

| Season | Count | Source rows found per omitted club |
|---|---:|---|
| 2004/05 | 10 | GNK Dinamo Zagreb (6); NK Kamen Ingrad Velika (4); NK Pula 1856 (6); NK Osijek (5); NK Varteks Varazdin (4); Slaven Belupo Koprivnica (2); NK Zagreb (5); NK Zadar (1); NK Inter Zapresic (6); NK Medjimurje Cakovec (2) |
| 2005/06 | 8 | Slaven Belupo Koprivnica (7); NK Pula Staro Cesko (4); NK Kamen Ingrad Velika (5); NK Varteks Varazdin (4); NK Zagreb (5); NK Inter Zapresic (3); NK Medjimurje Cakovec (3); HNK Cibalia Vinkovci (3) |
| 2006/07 | 4 | NK Kamen Ingrad Velika (4); NK Zagreb (6); HNK Cibalia Vinkovci (4); NK Medjimurje Cakovec (2) |
| 2007/08 | 5 | NK Medjimurje Cakovec (5); NK Osijek (7); HNK Sibenik (4); NK Inter Zapresic (5); HNK Cibalia Vinkovci (3) |
| 2008/09 | 5 | HNK Cibalia Vinkovci (2); NK Osijek (7); HNK Sibenik (7); NK Croatia Sesvete (5); NK Zadar (7) |
| 2009/10 | 7 | HNK Cibalia Vinkovci (3); NK Inter Zapresic (7); NK Croatia Sesvete (6); HNK Sibenik (6); NK Osijek (7); NK Medjimurje Cakovec (3); NK Karlovac 1919 (3) |
| 2010/11 | 4 | HNK Cibalia Vinkovci (3); NK Karlovac 1919 (4); RNK Split (5); NK Varazdin (4) |
| 2011/12 | 3 | HNK Cibalia Vinkovci (5); NK Varazdin (7); NK Karlovac 1919 (5) |

Confidence that the omissions are represented faithfully: **0.98**. Confidence
that these are complete historical rosters: **0.20**; the source cache is
demonstrably partial, so the catalog explicitly reports
`completeHistoricalRosterArchive: false`.

## Reproduce and validate

Use the same raw input files and fixed paths:

```bash
python3 scripts/build_hnl_draft_catalog.py \
  --performances /private/tmp/tm_player_performances.csv \
  --profiles /private/tmp/tm_player_profiles.csv \
  --player-index /private/tmp/hnl_players.csv.gz \
  --hns-riznica-dir /private/tmp \
  --position-overrides data/historical_position_overrides.json \
  --supplemental-club-seasons data/supplemental_club_seasons.json \
  --output data/hnl_draft_catalog.json

python3 -m unittest discover -s tests -v
```

The generated catalog records SHA-256 checksums for all main inputs, the
position-override file, and the supplemental club-season file. The catalog
generation is deterministic except for its `generatedAt` timestamp.
