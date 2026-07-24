# PromptAssembler checklist

This is an internal assembly checklist, not a source.

## Required report order

1. Title, snapshot date and citation convention.
2. Executive summary and explicit decision: official 36–0 mode vs branded
   non-canonical 38-match compatibility mode.
3. Research method and six-agent ledger.
4. Official format/rules and calibrated 2025/26 baseline.
5. Data inventory table, source precedence, gaps, access/licensing gate.
6. Unified schema plus compact source-to-unified mapping table.
7. Rating construction and rating→goal statistical model:
   exact equations, assumptions, uncertainty, chart/table and Mermaid workflow.
8. Simulation rules, pseudocode, Mermaid control flow and reproducibility.
9. Fixed-seed draft/example season: XI, inputs, complete table, scorers,
   validation totals and literal 38–0 showcase.
10. Game-mechanics evidence and product recommendations.
11. Limitations, validation plan and implementation roadmap.
12. Exact reproducibility commands and source/model/seed manifest.
13. Final appendix containing the user's complete UltraCode multi-agent prompt
    verbatim.

## Non-negotiable facts

- Latest rule frame: HNS 2026/27, 10 clubs, four cycles, 36 rounds.
- Calibration frame: completed HNS 2025/26, 180 matches, 479 goals,
  1.4611 home goals/match, 1.2000 away goals/match.
- Latest 2026/27 foreign-player maximum is five non-exempt players on the
  field; it was six in 2025/26. Do not copy the older value into current rules.
- Latest rules: at least six nationally trained players on the match sheet;
  12 named substitutes; five may enter in at most three in-play stoppages.
- Three points for a win, one for a draw. Ordinary tie: overall GD, goals
  scored. Critical final tie: head-to-head mini-table points, H2H GD, overall
  GD, fair play, draw of lots.
- Public Semafor detail begins with COMET (2004/05); the official HNL
  result/table archive begins in 1992.
- HNS/COMET does not publish the game's unified OVR. Market value and provider
  match ratings must remain distinct. Editorial OVR must be versioned.
- Null is not zero, especially for unreported assists and card subtypes.
- Current club is not the club on a historical player-season row.
- HNS Semafor and Transfermarkt public terms prohibit the unattended
  scraping/copying workflow contemplated by a production game. Require written
  permission/licensed data and do not provide evasion steps.

## Confidence rubric

| Band | Interpretation |
|---|---|
| 0.95–1.00 | Direct official rule/result or deterministic invariant |
| 0.80–0.94 | Directly observed source field or well-established model family |
| 0.60–0.79 | Cross-source field/access claim or plausible product inference |
| 0.30–0.59 | Editorial coefficient, sample ability rating, or illustrative run realism |
| below 0.30 | Unvalidated fatigue/injury/chemistry prior; do not present as fitted |

Every major section must contain a `Confidence:` line and a short
`Reproducibility:` note.

## Final verification

- All links use inline Markdown and no internal web reference IDs.
- Mermaid blocks parse syntactically and each numerical chart has a fallback
  Markdown table.
- No placeholder comments, TODOs or unfilled markers remain.
- Example invariants: 180 matches; 36/team; 2H+2A per pair; `P=W+D+L`;
  `Pts=3W+D`; league `sum(GF)=sum(GA)`; scorer allocation reconciles to team
  goals after own-goal handling.
- Same command and seed reproduce byte-identical result content.
- Literal 38–0 is labeled non-canonical and the seed-selection/showcase process
  is disclosed.
- The complete original prompt is the final content in the document.

