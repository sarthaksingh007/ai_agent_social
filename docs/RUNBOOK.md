# Runbook — dev & release commands

Two modes, one difference: **release adds the Cloudflare tunnel, dev doesn't.**
Dev needs no Cloudflare account, tunnel, or credentials.

| | Dev | Release |
|---|---|---|
| Command | `docker compose up -d` | `./scripts/deploy.sh` |
| Compose files | `docker-compose.yml` | `docker-compose.yml` + `docker-compose.prod.yml` |
| Services | db, api, web, worker, app | + cloudflared |
| Cloudflare creds | not needed | **required** |
| Reachable at | http://localhost:8095 | https://agency.paediaconnect.com |

`docker-compose.prod.yml` is deliberately not called `docker-compose.override.yml`
— Compose auto-loads that name, which would make the tunnel mandatory for
everyone who clones the repo.

---

## 1. First-time setup

```bash
git clone https://github.com/sarthak-nitro/agentic_agency.git
cd agentic_agency
cp .env.example .env            # then edit: pick LLM_MODEL + matching API key
```

You need a working LLM. Either:

```bash
# Option A — local, free, no key
ollama serve
ollama pull qwen2.5:7b
#   .env: LLM_MODEL=ollama_chat/qwen2.5:7b

# Option B — cloud
#   .env: LLM_MODEL=groq/llama-3.3-70b-versatile   + GROQ_API_KEY=...
#   .env: LLM_MODEL=openai/gpt-4o-mini             + OPENAI_API_KEY=...
#   .env: LLM_MODEL=anthropic/claude-sonnet-4-6    + ANTHROPIC_API_KEY=...
```

If the model is unreachable the UI shows a warning banner at the top and every
agent run fails, so fix this before running the wizard.

---

## 2. Dev mode

```bash
docker compose up --build -d        # build + start everything
docker compose up -d                # start (no rebuild)
```

Open **http://localhost:8095**. The API is also published on
**http://localhost:8000** (`/docs` gives interactive Swagger).

### Day-to-day

```bash
docker compose ps                          # what's running
docker compose logs -f worker              # watch agents work
docker compose logs -f api web             # follow several services
docker compose restart api                 # after editing src/ (bind-mounted)
docker compose restart worker
docker compose up -d --build web           # after editing web/ (baked into image)
docker compose stop                        # stop, keep containers
docker compose down                        # stop + remove containers
docker compose down -v                     # ...and wipe the database volume
```

### Frontend hot-reload

The `web` container serves a production build. For live reload, run Vite on the
host — it proxies `/api` to the published API port, so only stop `web`:

```bash
docker compose stop web
cd web
npm install
npm run dev            # http://localhost:5173
npm run typecheck      # tsc --noEmit
npm run build          # production build
```

### Database

```bash
docker exec -it sma_postgres psql -U sma -d social_agency

# useful queries
\dt
SELECT id, name, updated_at FROM projects ORDER BY updated_at DESC;
SELECT id, job_type, status, agent, left(coalesce(error,''),200) FROM job_queue ORDER BY created_at DESC LIMIT 10;
SELECT post_id, client_name, status FROM posts ORDER BY created_at DESC LIMIT 10;

# reset just the queue
DELETE FROM job_queue;
```

### Health checks

```bash
curl http://localhost:8000/api/health     # {"ok":true,"database":"up"}
curl http://localhost:8000/api/config     # agents, models, setup problems
curl http://localhost:8000/api/status     # running job + queue depth
curl http://localhost:8095/               # SPA through nginx
```

---

## 3. Release mode

```bash
./scripts/deploy.sh          # Linux / macOS
.\scripts\deploy.ps1         # Windows PowerShell
```

The script refuses to start and tells you what's missing if the tunnel files
aren't there. Equivalent by hand:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f cloudflared
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
```

### One-time tunnel setup

```bash
cloudflared tunnel login
cloudflared tunnel create <name>
cloudflared tunnel route dns <name> agency.example.com

cp ~/.cloudflared/<uuid>.json cloudflared/credentials.json
cp cloudflared/config.example.yml cloudflared/config.yml
#   then set `tunnel:` to the UUID and `hostname:` to your domain
```

`cloudflared/credentials.json` is gitignored — never commit it.

### Verify a release

```bash
cloudflared tunnel list                                   # connections should be non-zero
docker logs sma_cloudflared --tail 20
curl -I https://agency.paediaconnect.com                  # 200
curl https://agency.paediaconnect.com/api/health          # {"ok":true,...}
```

If credentials are missing, `scripts/deploy.*` stops before starting anything
and prints what to do. (The check has to live in the script: the
`cloudflare/cloudflared` image is distroless, so an in-container shell guard
cannot run — it fails with `stat /bin/sh: no such file or directory` and takes
the tunnel down.)

> The UI has **no authentication**. Put Cloudflare Access in front of the
> hostname before sharing it: anyone with the URL can approve and publish.

---

## 4. Ports

| Port | Service | Notes |
|------|---------|-------|
| 8095 | web (nginx) | the UI; 8080/8090 were taken by the unrelated paedia stack |
| 8000 | api | published so `npm run dev` can proxy to it |
| 5432 | db | |
| 5173 | Vite dev server | host only, not containerised |

---

## 5. Troubleshooting

| Symptom | Cause & fix |
|---|---|
| Dossier shows `agent could not run — …` | The LLM is unreachable. Check the banner at the top of the UI; start Ollama or switch `LLM_MODEL` in `.env`, then `docker compose restart worker`. |
| Banner: "Ollama is not reachable" | `ollama serve` on the host, or set a cloud model. From Docker the host is `host.docker.internal`. |
| `502 Bad Gateway` from nginx | The api container is down or still starting: `docker compose logs api`. (nginx re-resolves the api hostname per request, so a restart alone no longer causes this.) |
| `port is already allocated` | Something else owns the port: `docker ps --format "{{.Names}}\t{{.Ports}}"`. Change the host side of the mapping in `docker-compose.yml`. |
| Jobs stay `queued` forever | The worker is down or wedged: `docker compose logs -f worker`, then `docker compose restart worker`. |
| `deploy.ps1` says credentials missing | Put a real `cloudflared/credentials.json` in place, or just use dev mode. |
| cloudflared: `stat /bin/sh: no such file or directory` | Something added a shell `entrypoint`/`command` to the tunnel service. The image is distroless — keep the plain `command: ["tunnel", ...]`. |
| Site returns Cloudflare `error 1033` | The tunnel container isn't connected: `docker logs sma_cloudflared`. |
| Frontend changes don't show | The image bakes the build: `docker compose up -d --build web`, then hard-reload. |

---

## 6. CI/CD

See [CI/CD in the README](../README.md#cicd-github-actions).

| Workflow | Triggers | Runner |
|---|---|---|
| `ci.yml` | push to `web-ui`, PRs into `web-ui`, manual | GitHub-hosted |
| `deploy.yml` | push to `main`, manual | self-hosted (`windows`, `agency-host`) |

```bash
# run what CI runs, locally
cd web && npm ci && npm run typecheck && npm run build && cd ..

pip install ruff
ruff check --select E9,F63,F7,F82,F821 src

# the dev/release split assertions CI enforces
docker compose config --services                                             # must NOT list cloudflared
docker compose -f docker-compose.yml -f docker-compose.prod.yml config --services   # must list it
```
