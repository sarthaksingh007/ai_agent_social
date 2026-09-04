# Autonomous Multi-Agent Social Media Agency Pipeline

Free / open-source build of the PRD. Docker-based, with a React control panel.

## Stack

| Layer | Tech |
|-------|------|
| Orchestration | CrewAI + CrewAI Flows |
| LLM | litellm (Ollama local by default; Groq / OpenAI / Anthropic supported) |
| Schemas | Pydantic |
| Web search | duckduckgo-search |
| Image gen | Pollinations.ai / OpenAI / Cloudflare + Pillow (text overlay) |
| Database | PostgreSQL 18 (Docker) |
| API | FastAPI + Uvicorn |
| Approval UI | React 18 + TypeScript + Vite, Material 3 design tokens |
| Serving | nginx (static SPA + `/api` reverse proxy) |
| Publish trigger | Python (replaces Make.com) |

## Prerequisites

- Docker Desktop
- An LLM: either local Ollama (`ollama pull qwen2.5:7b`) or an API key for
  Groq / OpenAI / Anthropic

## Dev mode

No Cloudflare account, tunnel or credentials required — the base compose file
is the dev stack.

```bash
# 1. Configure environment
cp .env.example .env
#    then edit .env — pick LLM_MODEL and paste the matching API key

# 2. Build and start everything
docker compose up --build -d

# Handy
docker compose logs -f worker     # watch agents run
docker compose ps                 # what's up
docker compose restart api        # after editing src/ (it's bind-mounted)
docker compose down               # stop
docker compose down -v            # stop and wipe the database volume
```

Then open **http://localhost:8095**.

## Release mode

Same stack plus the public Cloudflare tunnel. This is the only mode that needs
`cloudflared/credentials.json`.

```bash
./scripts/deploy.sh          # Linux / macOS
.\scripts\deploy.ps1         # Windows

# or by hand
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

The deploy scripts check for the tunnel files first and tell you what's missing
instead of letting cloudflared crash-loop. The check lives in the script rather
than inside the container because `cloudflare/cloudflared` is distroless — it
has no shell to run a guard with.

`docker-compose.prod.yml` is deliberately **not** named `docker-compose.override.yml`
— Compose auto-loads that name, which would make the tunnel mandatory for
everyone.

Services that come up:

| Service | What it does | Where |
|---------|--------------|-------|
| `db` | PostgreSQL, auto-creates the `posts` table (`db/init.sql`) | `localhost:5432` |
| `api` | FastAPI REST layer over the DB and job queue | `localhost:8000` |
| `web` | React control panel served by nginx, proxies `/api` → `api` | `localhost:8095` |
| `worker` | Runs the agent jobs one at a time (capped at 2 CPU / 2 GB) | — |
| `app` | One-shot setup check, exits 0 | — |

`psql` access:

```bash
docker exec -it sma_postgres psql -U sma -d social_agency
```

## Frontend development

The container serves a production build. For hot-reload, run Vite directly —
it proxies `/api` to the published API port, so only `web` needs to be stopped:

```bash
cd web
npm install
npm run dev        # http://localhost:5173
npm run typecheck
```

## Public hosting (Cloudflare Tunnel)

`docker-compose.override.yml` adds a `cloudflared` service that publishes the
`web` container at a public hostname. It needs two files:

- `cloudflared/config.yml` — tunnel id + ingress rules (committed)
- `cloudflared/credentials.json` — tunnel secret (**gitignored**, never commit)

To set up your own:

```bash
cloudflared tunnel login
cloudflared tunnel create <name>
cloudflared tunnel route dns <name> <hostname>
# copy the generated ~/.cloudflared/<uuid>.json to cloudflared/credentials.json
# and point cloudflared/config.yml at that tunnel id + hostname
```

> The dashboard has **no authentication**. Put Cloudflare Access (or equivalent)
> in front of it before exposing it publicly — anyone with the URL can approve
> and publish posts.

## CI/CD (GitHub Actions)

**`.github/workflows/ci.yml`** runs on pushes to `web-ui`, PRs targeting
`web-ui`, and manual dispatch — no secrets needed:

| Job | What it checks |
|-----|----------------|
| `frontend` | `npm ci`, `tsc --noEmit`, `vite build`, uploads `dist` |
| `backend` | ruff (error rules), then the real FastAPI app against a live Postgres service container — every endpoint, plus 404s and the image path-traversal guard |
| `images` | builds both Docker images with layer caching, and asserts the **dev stack resolves without cloudflared** while the release stack includes it |

**`.github/workflows/deploy.yml`** deploys on push to `main`. Because the host
sits behind a Cloudflare tunnel with no inbound port, a cloud runner cannot
reach it — deployment uses a **self-hosted runner on the host machine**. One-time
setup:

1. GitHub → repo → Settings → Actions → Runners → *New self-hosted runner*
2. Install it on the host, giving it the labels `windows` and `agency-host`
3. Run it as a service so it survives reboots
4. Settings → Environments → create `production` (add required reviewers here if
   you want deploys gated on approval)

The workflow then checks out, verifies `cloudflared/credentials.json` exists on
the host, runs `scripts/deploy.ps1`, polls `/api/health` until it is green, and
confirms the public hostname returns 200 before finishing.

Until a runner is registered the deploy job just queues — CI is unaffected.

> Alternative if you'd rather not run a self-hosted runner: push images to GHCR
> from CI and have the host pull them on a timer (e.g. Watchtower). That trades
> the runner for a polling delay.

## Project layout

```
├── docker-compose.yml          # dev stack: db + api + web + worker + app
├── docker-compose.prod.yml     # release overlay: adds the cloudflared tunnel
├── scripts/deploy.sh|ps1       # release deploy with a credentials preflight
├── .github/workflows/          # ci.yml (always) + deploy.yml (self-hosted)
├── Dockerfile                  # Python image for api / worker / app
├── requirements.txt
├── db/
│   └── init.sql                # posts table (the "content conveyor belt")
├── src/
│   ├── api.py                  # FastAPI REST layer (thin wrapper over db.py)
│   ├── config.py               # env loading + setup checks
│   ├── db.py                   # SQLAlchemy engine + queries
│   ├── jobs.py                 # job → agent dispatch
│   ├── worker.py               # background queue consumer
│   ├── agents.py / pipeline.py / content.py / images.py / validator.py
│   ├── schemas.py              # the Pydantic handoff contracts
│   └── publish.py              # outbox + webhook publish trigger
└── web/
    ├── Dockerfile              # Vite build → nginx
    ├── nginx.conf              # SPA fallback + /api proxy
    └── src/
        ├── api/                # React Query hooks — the only network layer
        ├── components/         # ui primitives, icons, layout, feedback
        ├── features/           # wizard, approval, brandkit, queue
        ├── styles/globals.css  # Material 3 tokens + component styles
        ├── theme/              # light / dark / system switching
        └── types/domain.ts     # mirrors src/schemas.py
```

## Architecture notes

- **The worker is isolated.** The API only enqueues jobs and reads the DB; the
  CrewAI/Pillow stack never loads in the web-facing process, so an agent crash
  can't take down the UI.
- **Schema gating.** Agents hand off validated Pydantic objects, never raw text
  (`src/schemas.py`). `web/src/types/domain.ts` mirrors those contracts.
- **Project state has two writers.** The UI and the worker both merge into
  `projects.state`, so the frontend always patches onto the freshest fetched
  state rather than PUTting a locally-held copy.
