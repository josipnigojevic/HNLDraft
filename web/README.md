# 36–0 HNL draft frontend

Croatian club-season adaptation of the social 38–0 draft format. A manager
spins an HNL club in an exact season, chooses one player from that squad, and
places the player into a compatible formation slot. Eleven rounds produce a
drafted XI and a deterministic 36-match editorial result.

The interface supports:

- solo rooms and 2–4-manager live rooms
- six-character invite codes and shareable room URLs
- 12 formations
- squad-first and position-first draft flows
- easy, normal, and hard reroll/visibility rules
- season or career-prime editorial ratings
- player repositioning and swapping
- live progress, completed-manager waiting state, and final leaderboard

## Local development

Run the room API from the repository root:

```bash
HNL_API_PORT=8002 python3 api_rooms.py
```

Then run the frontend:

```bash
npm install
NEXT_PUBLIC_SIM_API_URL=http://localhost:8002 npm run dev
```

For the tested production-like setup, use `docker compose up --build -d` from
the repository root and open <http://localhost:3001>.

## Verification

```bash
npm run lint
npm test
```

The browser stores only its participant credential in `sessionStorage`.
Authoritative room state is stored by the Python API in SQLite. Player ratings
and simulated results are original game estimates—not official HNS ratings or
sporting predictions.
