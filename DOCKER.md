# Local Docker stack

This stack runs the HNL club-season draft locally:

- `web`: Croatian room/draft interface at <http://localhost:3001>
- `api`: server-authoritative room service at <http://localhost:8002>
- `hnl_rooms`: a named Docker volume containing the SQLite room database

The browser creates or joins a six-character room. Every manager spins and
drafts independently, while room state, tokens, versions, deterministic seeds,
and completed results remain authoritative in the API.

## Run

```bash
docker compose up --build -d
```

Open <http://localhost:3001>. Stop the containers without deleting saved room
data:

```bash
docker compose down
```

Change ports and the browser-facing API URL together when needed:

```bash
WEB_PORT=3010 API_PORT=8010 \
NEXT_PUBLIC_SIM_API_URL=http://localhost:8010 \
HNL_ALLOWED_ORIGINS=http://localhost:3010 \
docker compose up --build -d
```

## API smoke test

Health and catalog metadata:

```bash
curl http://localhost:8002/health
curl 'http://localhost:8002/catalog?includePlayers=false'
```

Create a solo room:

```bash
curl -sS http://localhost:8002/rooms \
  -H 'Content-Type: application/json' \
  -d '{
    "mode":"solo",
    "name":"Josip",
    "seed":3802026,
    "settings":{
      "formation":"4-3-3",
      "difficulty":"normal",
      "draftMode":"squad-first",
      "ratingsMode":"season",
      "seasonStart":1995,
      "seasonEnd":2025
    }
  }'
```

Live rooms use the same endpoint with `"mode":"live"`. Friends join with
`POST /rooms/{CODE}/join`; the host starts with `POST /rooms/{CODE}/start`.
Authenticated room state is available at `GET /rooms/{CODE}` using the
returned participant token as a Bearer token.

## Data and reproducibility

The image bundles `data/hnl_draft_catalog.json`; the API reports its exact
coverage in `/catalog`. Club-season spins derive from the room seed, manager
seat, draft turn, and reroll count. Reusing the same catalog, settings, and
seed reproduces the same spins and editorial season result.

Player ratings and the final 36-round season are game estimates, not official
HNS ratings or sporting predictions. The current catalog also identifies its
historical roster gaps instead of presenting partial source coverage as
complete.
