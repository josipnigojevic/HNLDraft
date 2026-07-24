# ExampleRunner Agent — reproducible HNL draft and season

**Research/simulation snapshot:** 2026-07-24 (Europe/Zagreb)  
**Status:** illustrative model run, not a forecast, betting product, official HNS
rating, or reconstruction of an actual historical XI.

## 1. What this example does

This example turns eleven exact `player × club × season` cards into one
fictional **Korisnikov XI**, places it in a ten-club 2026/27-style HNL, and runs
the official four-cycle schedule: every pair meets four times, twice at each
home ground, for **36 matches per club and 180 matches in total**. That is the
canonical HNL challenge, so its honest label is **36-0**. The literal 38-0
demonstration later in this file is a separate compatibility/showcase format
and is not an official HNL season.

The current format and points/tie-break rules come from the
[official 2026/27 HNS regulations](https://hns.family/files/documents/33080/Propozicije%20natjecanja%20SuperSport%20HNL%2026-27.pdf).
The engine's scoring intercept is anchored to the completed 2025/26
[HNS Semafor competition record](https://semafor.hns.family/en/competitions/100391485/supersport-hnl/details/):
180 matches, 479 goals, 1.4611 home goals and 1.2000 away goals per match.

**Confidence: 0.99** for the format and baseline aggregates; **0.45** for the
example's football realism because its player ratings and conversion
coefficients are editorial assumptions awaiting multi-season fitting.

## 2. Illustrative all-time HNL draft

### 2.1 Card selection

Formation: **4-3-3**. Every rating below was authored for this demonstration on
a 1–99 scale. Neither HNS, the clubs nor Transfermarkt supplied or endorsed the
ratings. A card freezes the player's age/club/season context; the simulation
must never substitute a current age or current market value.

| Slot | Exact draft card | HNL evidence used to check the card | Editorial OVR | Primary modeled contribution |
|---|---|---|---:|---|
| GK | Dominik Livaković — GNK Dinamo, **2020/21** | Dinamo's 2020/21 squad lists Livaković; the season page also lists the other selected Dinamo cards from that year. [Transfermarkt season squad](https://www.transfermarkt.com/gnk-dinamo-zagreb/startseite/verein/419/saison_id/2020) | 87 | GK |
| RB | Darijo Srna — HNK Hajduk, **2002/03** | Hajduk's historical shirt-number page places Srna at the club in 2002/03. [Transfermarkt number history](https://www.transfermarkt.com/hnk-hajduk-split/rueckennummern/verein/447) | 88 | DEF/MID |
| RCB | Josip Šimunić — GNK Dinamo, **2012/13** | Dinamo's detailed 2012/13 squad includes Šimunić at centre-back. [Transfermarkt season squad](https://www.transfermarkt.com/gnk-dinamo-zagreb/kader/verein/419/saison_id/2012/plus/1) | 87 | DEF |
| LCB | Joško Gvardiol — GNK Dinamo, **2020/21** | The season-specific record reports 25 HNL appearances and two goals. [Transfermarkt 2020/21 stats](https://www.transfermarkt.com/josko-gvardiol/leistungsdaten/spieler/475959/saison/2020) | 88 | DEF/MID |
| LB | Danijel Pranjić — NK Osijek, **2003/04** | The transfer history places Pranjić at Osijek until his 1 July 2004 move to Dinamo; detailed pre-COMET coverage is secondary. [Transfermarkt career record](https://www.transfermarkt.com/danijel-pranjic/leistungsdaten/spieler/25617) | 84 | MID/DEF |
| DM | Marcelo Brozović — GNK Dinamo, **2013/14** | Dinamo's 2013/14 squad lists Brozović and the season record shows six goals and six assists across the provider's displayed competition scope. [Transfermarkt season page](https://www.transfermarkt.com/gnk-dinamo-zagreb/startseite/verein/419/saison_id/2013) | 87 | MID/DEF |
| CM | Luka Modrić — GNK Dinamo, **2007/08** | The season-specific record reports 25 HNL appearances, 13 goals and 11 assists. [Transfermarkt 2007/08 stats](https://www.transfermarkt.com/luka-modric/leistungsdaten/spieler/27992/saison/2007) | 91 | MID/ATT |
| AM | Dani Olmo — GNK Dinamo, **2018/19** | Dinamo's 2018/19 squad and season summary include Olmo. [Transfermarkt season page](https://www.transfermarkt.com/gnk-dinamo-zagreb/startseite/verein/419/saison_id/2018) | 89 | MID/ATT |
| RW | Marko Pjaca — GNK Dinamo, **2015/16** | Dinamo's 2015/16 squad lists Pjaca at left wing; RW is treated as a compatible rather than natural role. [Transfermarkt season page](https://www.transfermarkt.com/gnk-dinamo-zagreb/startseite/verein/419/saison_id/2015) | 85 | ATT |
| ST | Mario Mandžukić — GNK Dinamo, **2008/09** | The 2008/09 HNL record identifies Mandžukić as the 16-goal league leader. [Transfermarkt HNL season](https://www.transfermarkt.com/supersport-hnl/startseite/wettbewerb/KR1/saison_id/2008) | 88 | ATT |
| LW | Mislav Oršić — GNK Dinamo, **2020/21** | Dinamo's 2020/21 squad-stat page reports 35 appearances and 16 goals in its displayed scope. [Transfermarkt squad statistics](https://www.transfermarkt.com/gnk-dinamo-zagreb/leistungsdaten/verein/419/reldata/KR1%262020) | 87 | ATT |

This set deliberately spans the league archive rather than claiming the
objectively strongest possible XI. The official
[HNL results/standings archive](https://www.hnl.hr/povijest/rezultati-i-poretci/?sid=1)
starts with the inaugural 1992 season, while public COMET detail starts later;
therefore early card membership needs a secondary source and lower confidence.
Transfermarkt's values are secondary/editorial and its
[terms prohibit automated copying](https://www.transfermarkt.com/intern/anb);
the links above were inspected as small cited records, not bulk-scraped.

**Confidence: 0.91** that the eleven club-season memberships are plausible;
**0.70** for the two pre-COMET cards' exact statistical completeness;
**0.35** for the OVR values as calibrated measures of ability.

### 2.2 From cards to team components

The engine consumes four team components rather than averaging OVR blindly.
The cards contribute by role, are weighted by expected minutes, and receive the
published position-fit multiplier. Pjaca at RW is compatible rather than
natural, so his contribution is discounted; no other starter is knowingly out
of position.

| Component | Main cards | Draft value supplied to engine | Interpretation |
|---|---|---:|---|
| ATT | Mandžukić, Oršić, Pjaca, Olmo, Modrić | **92.0** | Shot volume/quality and scorer weights |
| MID | Modrić, Olmo, Brozović, Srna, Pranjić | **90.0** | Chance creation, control, fatigue resistance |
| DEF | Gvardiol, Šimunić, Srna, Pranjić, Brozović | **88.5** | Suppresses opponent scoring intensity |
| GK | Livaković | **88.0** | Additional suppression of opponent intensity |

The component vector—not the displayed 87.4 mean OVR—is the direct simulation
input. The XI has a neutral chemistry factor in this demonstration: historical
club overlap is shown to users but not rewarded until a fitted chemistry
coefficient exists. A replacement-level abstract bench is used because only
eleven cards were drafted.

**Confidence: 0.99** that these are the values passed to the example
configuration; **0.30** that their absolute scale is properly calibrated.

## 3. Fixed-seed official-format season

### 3.1 Run configuration

| Setting | Fixed value |
|---|---|
| Engine | `sim_engine.py` v0.1.0, standard library only |
| Mode | `official_hnl_36_round` |
| Master seed | `38020261743` |
| Rules season | 2026/27 |
| Calibration season | completed 2025/26 |
| Scoring intercepts | home `1.4611`; away `1.2000` |
| Rating slopes | attack `0.13`; defence `0.11`; cohesion `0.04` |
| Low-score correction | independent Poisson, `rho = 0` until fitted |
| Squad policy | components and abstract bench frozen at season start; no transfers |
| User components | ATT `92.0`, MID `90.0`, DEF `88.5`, GK `88.0`, bench `75.0`, position fit `0.985` |
| Random streams | SHA-256-derived event, score, scorer and tie-lot streams |

The seed is a **selected regression example**, not an unbiased draw. Starting
at seed `38020260724`, a sequential search selected the first seed satisfying
predeclared readability checks: Korisnikov XI first; Rudeš tenth; Hajduk and
Rijeka in the top four; user points `78–94`, GF `68–95`, GA `22–46`; and league
goals `455–505`. The first passing offset was `1019`, hence seed
`38020261743`. These gates make the report easy to inspect, but invalidate any
claim that this one run estimates outcome probability.

The official schedule uses the
[HNS 2026/27 four-cycle rules](https://hns.family/files/documents/33080/Propozicije%20natjecanja%20SuperSport%20HNL%2026-27.pdf);
the model intercepts use the completed
[HNS 2025/26 Semafor results](https://semafor.hns.family/en/competitions/100391485/supersport-hnl/details/).
All club components, OVRs, fit, bench, injury and fatigue parameters are
editorial.

**Confidence: 1.00** that these values are the saved run inputs; **0.38** that
the unfitted rating coefficients have the right magnitude.  
**Reproducibility:** rerun the `season` command in Section 6 with the same seed
and engine; compare the canonical content hash.

### 3.2 Complete final table

| Pos | Club | P | W | D | L | GF | GA | GD | Pts |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | **Korisnikov XI** | 36 | 25 | 9 | 2 | 78 | 29 | +49 | **84** |
| 2 | HNK Hajduk | 36 | 18 | 6 | 12 | 55 | 43 | +12 | 60 |
| 3 | HNK Rijeka | 36 | 18 | 5 | 13 | 59 | 45 | +14 | 59 |
| 4 | NK Osijek | 36 | 15 | 8 | 13 | 42 | 41 | +1 | 53 |
| 5 | NK Lokomotiva | 36 | 14 | 10 | 12 | 50 | 49 | +1 | 52 |
| 6 | NK Istra 1961 | 36 | 14 | 6 | 16 | 39 | 53 | -14 | 48 |
| 7 | HNK Gorica | 36 | 13 | 8 | 15 | 50 | 48 | +2 | 47 |
| 8 | NK Varaždin | 36 | 9 | 12 | 15 | 34 | 45 | -11 | 39 |
| 9 | NK Slaven Belupo | 36 | 8 | 7 | 21 | 40 | 73 | -33 | 31 |
| 10 | NK Rudeš | 36 | 7 | 7 | 22 | 39 | 60 | -21 | 28 |

The complete machine-readable match/event log is in the saved
[season JSON](../outputs/season_38020261743/season_seed_38020261743.json), with
a compact human-readable
[Markdown rendering](../outputs/season_38020261743/season_seed_38020261743.md).

**Confidence: 1.00** that the table is an exact rendering of the fixed-seed
output; **0.25** that it predicts a real future table.  
**Reproducibility:** the output records engine `0.1.0`, seed `38020261743` and
canonical hash `5844d69f1d654c8c9a2dfe6e5b6a28589725a82159a55abdacbac66d60b1cfc4`.

### 3.3 Points leaderboard and title summary

- **Champion:** Korisnikov XI, 84 points (`2.333` per match), 24 points clear
  of HNK Hajduk.
- **Home:** `13-5-0`, goals `46-13`; **away:** `12-4-2`, goals `32-16`.
- **Title record:** `25-9-2`, 78 scored, 29 conceded, goal difference `+49`.
- The next four point totals were Hajduk `60`, Rijeka `59`, Osijek `53` and
  Lokomotiva `52`. No equal-points critical-position tie required the HNS
  head-to-head/fair-play/lot resolver in this run.
- The selected XI was not 36-0: its two losses were away to Rijeka in round 8
  (`0-1`) and Hajduk in round 18 (`2-3`). This is useful evidence that a strong
  component vector still retains match randomness.

This is a **realized points leaderboard from one selected seed**, not the mean
of many simulations. A production result screen should add rank/points
intervals from at least 10,000 unselected seeds.

**Confidence: 1.00** for the arithmetic; **0.30** for the qualitative strength
ordering and **0.00** for interpreting the 24-point margin as a forecast.  
**Reproducibility:** filter the saved JSON `matches` for `Korisnikov XI`; the
home and away rows reconcile to the final table.

### 3.4 Top scorers

Top 15 overall:

| Rank | Player/placeholder bucket | Club | Goals |
|---:|---|---|---:|
| 1 | **Mario Mandžukić (Dinamo 2008/09)** | Korisnikov XI | **26** |
| 2 | HNK Gorica — ostali | HNK Gorica | 18 |
| 3 | HNK Rijeka — CF | HNK Rijeka | 17 |
| 4 | HNK Hajduk — CF | HNK Hajduk | 15 |
| 5 | HNK Hajduk — ostali | HNK Hajduk | 15 |
| 6 | HNK Gorica — CF | HNK Gorica | 14 |
| 7 | HNK Rijeka — ostali | HNK Rijeka | 14 |
| 8 | NK Istra 1961 — CF | NK Istra 1961 | 14 |
| 9 | NK Rudeš — CF | NK Rudeš | 14 |
| 10 | NK Lokomotiva — ostali | NK Lokomotiva | 13 |
| 11 | NK Osijek — ostali | NK Osijek | 12 |
| 12 | NK Rudeš — RW | NK Rudeš | 12 |
| 13 | HNK Rijeka — AM | HNK Rijeka | 11 |
| 14 | HNK Rijeka — RW | HNK Rijeka | 11 |
| 15 | NK Lokomotiva — CF | NK Lokomotiva | 11 |

The opponent labels are deliberately **synthetic role buckets**, not claims
about 2026/27 players. Licensed frozen rosters should replace them before any
public game release.

Drafted-XI scorer reconciliation:

| Draft card | Goals |
|---|---:|
| Mario Mandžukić — Dinamo 2008/09 | 26 |
| Dani Olmo — Dinamo 2018/19 | 9 |
| Mislav Oršić — Dinamo 2020/21 | 9 |
| Marko Pjaca — Dinamo 2015/16 | 8 |
| Luka Modrić — Dinamo 2007/08 | 7 |
| Danijel Pranjić — Osijek 2003/04 | 6 |
| Marcelo Brozović — Dinamo 2013/14 | 6 |
| Josip Šimunić — Dinamo 2012/13 | 3 |
| Darijo Srna — Hajduk 2002/03 | 2 |
| Joško Gvardiol — Dinamo 2020/21 | 2 |
| Dominik Livaković — Dinamo 2020/21 | 0 |
| **Total** | **78** |

All 78 Korisnikov XI goals and all 486 league goals have one scorer allocation;
the engine does not model own goals in this prototype.

**Confidence: 1.00** for reproduction of the generated ledger; **0.20** for
the scorer distribution as football calibration.  
**Reproducibility:** sum `top_scorers[].goals` by team in the JSON; it equals
each table row's GF.

### 3.5 How the draft affected the result

The causal chain is transparent but counterfactual:

| Stage | Korisnikov XI | Nine-opponent mean | Difference |
|---|---:|---:|---:|
| ATT input | 92.00 | 74.22 | +17.78 |
| MID input | 90.00 | 74.33 | +15.67 |
| DEF input | 88.50 | 73.83 | +14.67 |
| GK input | 88.00 | 73.50 | +14.50 |
| Abstract bench | 75.00 | 69.06 | +5.94 |
| Derived attack strength \(A\), before match state | +1.616 | -0.073 | +1.689 |
| Derived defence strength \(D\), before match state | +1.333 | -0.128 | +1.461 |

Against the average opponent and before fit, fatigue, injuries, substitutions
or cards, those strengths imply approximately:

| Venue | User expected goals | Opponent expected goals |
|---|---:|---:|
| User home | 1.828 | 1.027 |
| User away | 1.502 | 1.250 |

The engine then applies Pjaca's compatible-role fit through team position fit
`0.985`, plus the stateful event layer. Across the 36 realized fixtures it
recorded summed model means of `59.939` for and `40.954` against, average user
fatigue `0.217`, four unavailable-player match instances, three user red cards
and 143 substitutions.

The realized `78-29` goal record was much more favorable than the `59.9-41.0`
mean total: about `+18.1` goals scored and `-12.0` conceded relative to the
conditional means. That gap is random variation amplified by selecting a
readable seed; it must not be credited to the draft as a deterministic effect.
The defensible inference is narrower: the editorial component gaps raised
Korisnikov XI's goal intensities before the random draws.

**Confidence: 1.00** for the calculations from the saved inputs/events;
**0.38** for the coefficient interpretation and **0.20** for dynamic-effect
calibration.  
**Reproducibility:** apply the equations in `research/sim_engine.md` to the
saved `teams` rows, then aggregate `home_xg`/`away_xg` over the 36 user matches.

### 3.6 Validation totals

| Invariant | Fixed-seed result |
|---|---:|
| Match count | `180` |
| Round count | `36` |
| Five matches and every club once per round | `true` |
| Every club plays 36 | `true` |
| Every pair meets four times | `true` |
| Every pair has two home fixtures each | `true` |
| `P = W + D + L` and `Pts = 3W + D` | `true` |
| League `sum(GF) = sum(GA)` | `486 = 486` |
| Scorer goals reconcile to league goals | `486 = 486` |
| Same-seed output is identical | unit test passed |
| Different seed changes the run | unit test passed |

League scoring was `486 / 180 = 2.700` goals per match, close to but not forced
to equal the 2025/26 HNS anchor of `479 / 180 = 2.661`.

**Confidence: 1.00** for these deterministic checks; **0.93** that the test
suite covers the prototype's principal accounting paths.  
**Reproducibility:** `python3 -m unittest -v` runs four tests covering schedule,
same/different seed behavior, and the disclosed golden path.

## 4. Literal 38-0 compatibility/showcase

The separate compatibility run demonstrates a literal perfect record:

| Field | Golden-path output |
|---|---:|
| Mode | `noncanonical_38_match_showcase` |
| Search | sequential seeds `1..100000` |
| First perfect seed | **474** |
| Test-only component boost | **+41.0** |
| Record | **38-0-0** |
| Points | **114** |
| Goals | **119-27** |
| Goal difference | **+92** |
| Canonical content SHA-256 | `940c7dc60c0c2f56c4b2efdbae9db4f3d44c21ec9b480d10b00c2b55ad640198` |

This is explicitly a **non-canonical, selected golden-path regression test**.
Current HNL clubs play 36 league matches, not 38, and the `+41` component
offset pushes the user team outside the calibrated domain. Seed 474 was found
by searching for a perfect result; it is therefore intentionally cherry-picked
and has no predictive meaning. Its valid purpose is to prove that the product
can render a 38-win state, 114 points, its fixture log and scorer ledger
reproducibly. The complete output is available as
[JSON](../outputs/challenge_seed_474/challenge_seed_474.json) and
[Markdown](../outputs/challenge_seed_474/challenge_seed_474.md).

**Confidence: 1.00** that seed 474 reproduces the golden path with engine
v0.1.0; **0.00** that the outcome estimates real HNL performance.  
**Reproducibility:** run `find-perfect` to rediscover seed 474, then run the
fixed-seed `challenge` command in Section 6.

## 5. Confidence and interpretation

| Claim layer | Confidence | Interpretation |
|---|---:|---|
| 10 clubs / 36 rounds / 180 matches and official points rules | 0.99 | Direct HNS rules |
| Saved table, scorers, arithmetic and fixed-seed reproduction | 1.00 | Deterministic artifacts and passing tests |
| Poisson attack/defence model family | 0.82 | Established statistical starting point |
| One-season HNS intercept applied to a cross-era draft | 0.55 | Useful anchor, not a cross-era fit |
| Editorial player/team components and OVRs | 0.35 | Plausible game inputs, not official ratings |
| Fatigue, injury, bench, fit and red-card effects | 0.18–0.30 | Mechanics priors awaiting validation |
| This selected season as a prediction | 0.25 | Seed-selection bias plus unfitted parameters |
| Literal `38-0` golden path as a prediction | 0.00 | Deliberately boosted and seed-searched test |

The example answers “can this pipeline turn a sourced draft into a transparent,
repeatable season?”—yes. It does not yet answer “how likely is this team to win
the real league?” That needs licensed multi-season lineups, versioned ratings,
rolling-origin fitting and thousands of unselected simulation seeds.

**Reproducibility:** preserve the rules/data snapshot date, code hash, Python
version, model configuration, player cards and master seed together; changing
any one of them creates a different experiment.

## 6. Exact reproduction commands

Tested on Python `3.13.7` (`Darwin 24.6.0 arm64`):

```bash
cd /Users/josipnigojevic/380HNL

python3 -m unittest -v

python3 sim_engine.py season \
  --seed 38020261743 \
  --output-dir outputs/season_38020261743

python3 sim_engine.py find-perfect \
  --start-seed 1 \
  --max-seeds 100000 \
  --matches 38 \
  --showcase-boost 41

python3 sim_engine.py challenge \
  --seed 474 \
  --matches 38 \
  --showcase-boost 41 \
  --output-dir outputs/challenge_seed_474

shasum -a 256 \
  outputs/season_38020261743/season_seed_38020261743.json \
  outputs/season_38020261743/season_seed_38020261743.md \
  outputs/challenge_seed_474/challenge_seed_474.json \
  outputs/challenge_seed_474/challenge_seed_474.md
```

Expected hashes:

| Artifact/hash type | SHA-256 |
|---|---|
| Official run canonical content | `5844d69f1d654c8c9a2dfe6e5b6a28589725a82159a55abdacbac66d60b1cfc4` |
| Official JSON file | `636d28b8bbedaa02f89dfc7dc0ae5388a90ec7306bf34df6ae837b19a8136fd0` |
| Official Markdown file | `7f91a8ecf55b61262ddf5d06ccd672288d1f8ba8788ca5794d82ef674e828e9d` |
| Showcase canonical content | `940c7dc60c0c2f56c4b2efdbae9db4f3d44c21ec9b480d10b00c2b55ad640198` |
| Showcase JSON file | `0cb1894f3b0b25b993a9536f4bd634bc006e6c7357f46ff49f6df6655e917382` |
| Showcase Markdown file | `ecdb385bb33ec71a46d9c7f3d0a726bbb4a3ff015b5d0e68962e1259f2d6a917` |
| `sim_engine.py` | `9efdcdcc7d7eac147ffabc7c4432450985c19973732d1a2f77088053c4306d90` |
| `test_sim_engine.py` | `bc402f80d23a982f71df0a6f0bea70ca6c7f12f677e16a0fd01fe7d24c10a1d5` |

The engine's “canonical content” hash covers the payload before the
`content_sha256` field is inserted; the whole-file hashes cover the final
serialized files. Repeating the commands with unchanged code/runtime should
reproduce both.

**Confidence: 0.99** for same-runtime reproducibility; **0.92** across future
Python versions unless the runtime is pinned.  
**Reproducibility:** for archival runs, store `python3 --version`, OS/architecture,
the two code hashes above, source snapshot hashes, model configuration and seeds
in one manifest.
