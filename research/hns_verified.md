# HNS / COMET verified findings

Research date: 2026-07-24 (Europe/Zagreb).

## Competition format and rules

- The latest official 2026/27 HNL competition regulations specify a four-cycle
  points system, `9 + 9 + 9 + 9 = 36` rounds; they list the ten participating
  clubs and set the season from 31 July 2026 to 23 May 2027. Source:
  [HNS 2026/27 regulations, Article 3](https://hns.family/files/documents/33080/Propozicije%20natjecanja%20SuperSport%20HNL%2026-27.pdf).
- The official 2025/26 HNL competition regulations likewise specify a four-cycle points
  system, `9 + 9 + 9 + 9 = 36` rounds. Source:
  [HNS 2025/26 regulations, Article 3](https://hns.family/files/documents/31403/Propozicije%20natjecanja%20SuperSport%20HNL%202025-26.pdf).
- The latest 2026/27 rules retain 3 points for a win, 1 for a draw, the same
  ordinary and critical-position tiebreak sequence, 12 named substitutes, at
  most 5 used in at most 3 stoppages, and a minimum of 6 nationally trained
  players on the match sheet. The allowed number of non-exempt foreign players
  on the field is **5** in 2026/27, down from **6** in 2025/26. Source:
  [HNS 2026/27 regulations, Articles 14, 16 and 34](https://hns.family/files/documents/33080/Propozicije%20natjecanja%20SuperSport%20HNL%2026-27.pdf).
- A win is worth 3 points and a draw 1 point. The ordinary table first separates
  equal points by overall goal difference and then goals scored. For the title,
  UEFA places, or relegation after round 36, the regulations instead introduce a
  mini-table among the tied clubs: head-to-head points, head-to-head goal
  difference, overall goal difference, fair-play (yellow = 1 minus point; sending
  off = 3), and finally a draw by the competition commissioner. Source:
  [HNS 2025/26 regulations, Article 45](https://hns.family/files/documents/31403/Propozicije%20natjecanja%20SuperSport%20HNL%202025-26.pdf).
- Up to 12 substitutes may be named; at most 5 may enter, using at most 3
  stoppages (half-time does not consume a stoppage). Source:
  [HNS 2025/26 regulations, Article 17](https://hns.family/files/documents/31403/Propozicije%20natjecanja%20SuperSport%20HNL%202025-26.pdf).
- The HNL official archive exposes results and final standings for every season
  from the inaugural 1992 competition through 2025/26. Source:
  [HNL results and standings archive](https://www.hnl.hr/povijest/rezultati-i-poretci/?sid=1).

Confidence: **0.99** for the stated 2025/26 and 2026/27 rules; **0.97** for
archive availability as observed.

## Semafor / COMET fields observed

The official 2025/26 competition page exposes these competition tabs and fields:

- Fixtures/results: round, kickoff date/time, home club, home club ID, score,
  away club, away club ID, venue, stable match page/ID.
- Table: position, club, played (`Tot`), wins, draws, losses, goals for (`G+`),
  goals against (`G-`), goal difference, points, form.
- Goalscorers: rank, player/ID, club, goals.
- Cards: rank, player/ID, club, yellow cards, red cards.
- Apps/minutes: rank, player/ID, club, appearances, minutes.
- Aggregate stats: goals and average goals per round, accumulated cards and
  unserved suspensions.
- Match page: competition/round, clubs and score, status, venue, kickoff,
  attendance, referees and VAR, goal/card/substitution events with minute,
  starters, substitutes, shirt numbers, captain marker, goalkeeper/player role,
  and coach.
- Player profile: stable player ID/URL, name, shirt number, current club, date
  and place of birth, current-season appearances, starts, substitute
  appearances, goals, yellow/red cards, plus per-season/per-competition
  breakdowns where present.

Source:
[HNS Semafor 2025/26 competition](https://semafor.hns.family/en/competitions/100391485/supersport-hnl/details/),
[example match record](https://semafor.hns.family/en/matches/100399759/nk-lokomotiva-z-hnk-vukovar-1991-1-0/),
[example player record](https://semafor.hns.family/en/players/127083/josip-posavec/).

Confidence: **0.98** (direct page inspection).

## 2025/26 calibration baseline

Computed from all 180 result rows on the official 2025/26 Semafor competition
page:

| Quantity | Value |
|---|---:|
| Matches | 180 |
| Total goals | 479 |
| Goals per match | 2.6611 |
| Home goals per match | 1.4611 |
| Away goals per match | 1.2000 |
| Home wins | 82 (45.56%) |
| Draws | 47 (26.11%) |
| Away wins | 51 (28.33%) |
| Credited player goals in goalscorer list | 469 |
| Yellow cards in competition card list | 979 (5.4389/match) |
| Red cards in competition card list | 37 (0.2056/match) |

The 10-goal gap between total goals and credited goals is not labeled here; do
not automatically call all ten own goals without event-level verification.

Source:
[HNS Semafor 2025/26 competition](https://semafor.hns.family/en/competitions/100391485/supersport-hnl/details/).

Confidence: **0.99** for fixture/table aggregation; **0.95** for the card
aggregation because the page UI, rather than a published data dictionary,
defines the two card columns.

## Access and licensing constraint

Semafor's terms state that the app/data are licensed for personal,
non-commercial use and prohibit copying/distribution without consent,
commercial use, and automated systems such as bots or spiders. Transfermarkt's
terms similarly prohibit bots, spiders, screen scraping, and other automated
copying. Therefore a production game should obtain written permission or a
licensed feed; this research only inventories public page fields and records
small, cited aggregates rather than shipping a bulk scraper.

Sources:
[HNS Semafor terms](https://hns.family/en/hns/info/terms-of-use-semafor-app/),
[Transfermarkt terms](https://www.transfermarkt.com/intern/anb).

Confidence: **0.98** that the cited terms contain these restrictions; legal
effect and any exception depend on jurisdiction and counsel.
