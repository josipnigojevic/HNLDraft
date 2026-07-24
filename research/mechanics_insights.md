# Mechanics evidence for an HNL “38–0” adaptation

**Research snapshot:** 2026-07-24.  
**Purpose:** separate documented game mechanics from community suggestions and
from the statistical match model. This is product-design evidence, not a source
of HNL player ability.

## Observed mechanics

| Evidence | Mechanics or issue observed | HNL design consequence | Confidence |
|---|---|---|---:|
| [38-0 Football — how to play](https://www.38-0football.com/) | Setup → formation → one club-season spin per round → one historical player pick → 11-player XI → seeded season simulation. The site describes Classic/Expert modes, positional fitness, overall/attribute ratings, formation synergy and randomness. | Preserve the short draft loop, a visible Classic mode and a hidden-rating Expert mode. Store the spun `Club + Season` card so player eligibility is auditable. | **0.95** that the page describes these mechanics; **0.55** that its unpublished balance is suitable for HNL |
| [38-0 Football — positional fitness](https://www.38-0football.com/) | The published page gives an illustrative natural/compatible/wrong-position scale of 100/75/30. | Use a versioned compatibility matrix rather than hard-code a player's displayed position; make the penalty visible before the pick is locked. The exact 100/75/30 values are product defaults, not empirical HNL estimates. | **0.94** observation; **0.35** numerical fitness calibration |
| [WebGames Poisson-engine post](https://www.reddit.com/r/WebGames/comments/1uremro/380_draft_an_alltime_premier_league_xi_simulate_a/) | A creator describes Poisson scoring with formation and position fit. | Poisson is consistent with the genre, but the HNL implementation should be calibrated to official HNS scoring rates and documented independently. | **0.75** description; **0.30** as evidence of engine quality |
| [Serie A adaptation feedback](https://www.reddit.com/r/soccer/comments/1tysf91/check_out_this_serie_a_version_of_380/) | Players reported invalid historical team-season memberships, wrong positions, repeated spins, and an unwinnable final-slot state. The creator described recent-team avoidance, valid-pick checks, ATT/MID/DEF/GK panels, scorer tracking and position compatibility. | Validate every card as `player × club × season`; exclude spins with no valid remaining position; use a recent-spin cooldown; expose component ratings and scorers; retain a correction/report mechanism. | **0.65** as anecdotal UX evidence |
| [FootballClichés discussion](https://www.reddit.com/r/footballcliches/comments/1tyi8d1/380_build_the_greatest_premier_league_xi/) | Players questioned ratings, positional effects, excessive scorer totals and surprising final positions. | Version and explain editorial OVRs, show fit/chemistry effects, publish the seed, and provide expected finish plus an uncertainty band so one random season is not mistaken for a forecast. | **0.60** as anecdotal UX evidence |
| [Alpha/Beta player feedback](https://www.reddit.com/r/alphaandbetausers/comments/1u0losr/looking_for_testers_for_a_football_draft_game_i/) | The creator solicited checks for player ratings, eligibility, difficulty and balance; a response challenged an implausible rating. | Build a moderation ledger: rating value, rubric version, evidence, editor, reviewer, effective date and user-submitted correction status. | **0.55** as anecdotal UX evidence |

## Recommended HNL loop

1. Choose authentic **36-round HNL** or explicitly non-canonical **38-match
   compatibility challenge**, formation, era filter, rating visibility and
   roster-rule mode.
2. Spin an eligible HNL `club-season`; offer only players proven to belong to
   that exact season card and able to fill at least one unfilled slot.
3. Lock one player. Preserve the source observation and editorial-rating version.
4. Repeat until the XI is complete. Optional authentic mode checks the
   season-specific nationally-trained and foreign-player rules against a
   match-sheet/bench configuration.
5. Show ATT/MID/DEF/GK, positional fitness, chemistry and uncertainty before
   simulation, but not the random draws.
6. Simulate with a disclosed seed. Report the full table, match log, scorers,
   injuries/cards, and the difference between expected and realized results.

The historical HNL card pool should begin in 1992 because the
[official HNL archive](https://www.hnl.hr/povijest/rezultati-i-poretci/?sid=1)
starts with the inaugural season. Detailed official COMET player coverage begins
later, so early cards need secondary provenance and lower confidence.

**Confidence: 0.84** for the loop as a usability recommendation; **0.99** for
the need to label 36-match and 38-match modes separately under current HNL rules.

## Evidence limits

- The targeted web search did not identify a credible HNL-specific 38–0
  mechanics implementation or a Croatian-language YouTube source that disclosed
  an engine. Absence from this search is not proof that none exists.
- Reddit posts are useful for failure modes and desired features, not for player
  facts, coefficients, or league rules.
- A public game's description is not an independently audited specification of
  its internal engine.

**Confidence: 0.70** that the search captured the prominent English-language
genre examples available on the research date; **0.35** for coverage of
Croatian-language social/video material.

## Reproducibility note

Rerun the targeted searches with the snapshot date in the research manifest and
archive only links/short notes allowed by each platform. Record query, locale,
retrieval time and final URL. Treat newly discovered mechanics as a proposed
product change until they pass an explicit design review.

