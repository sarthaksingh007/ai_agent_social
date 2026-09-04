"""Database connection + helpers (SQLAlchemy engine over PostgreSQL)."""
from sqlalchemy import create_engine, text

from src.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

_schema_ready = False


def _ensure_schema() -> None:
    """Lazy migration for columns/tables added after the initial init.sql."""
    global _schema_ready
    if _schema_ready:
        return
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS cta_text TEXT DEFAULT ''"))
        conn.execute(text(
            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS platform_variants JSONB "
            "DEFAULT '[]'"))
        conn.execute(text(
            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS image_variants TEXT[] "
            "DEFAULT '{}'"))
        # Post format (post/carousel/reel) + their format-specific payloads.
        conn.execute(text(
            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS content_format TEXT "
            "DEFAULT 'post'"))
        conn.execute(text(
            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS carousel_slides JSONB "
            "DEFAULT '[]'"))
        conn.execute(text(
            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS reel_script JSONB "
            "DEFAULT NULL"))
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS brand_kits ("
            "client_name TEXT PRIMARY KEY, colors TEXT[] DEFAULT '{}', "
            "font_style TEXT DEFAULT '', logo_description TEXT DEFAULT '', "
            "handle TEXT DEFAULT '', website TEXT DEFAULT '', "
            "style_notes TEXT DEFAULT '', "
            "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"))
        # One project per brand — holds the wizard state as JSON.
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS projects ("
            "id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, "
            "state JSONB NOT NULL DEFAULT '{}', "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
            "updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"))
        # Background job queue processed by the worker service.
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS job_queue ("
            "id SERIAL PRIMARY KEY, project_id INT REFERENCES projects(id) "
            "ON DELETE CASCADE, project_name TEXT, job_type TEXT NOT NULL, "
            "label TEXT DEFAULT '', agent TEXT DEFAULT '', "
            "payload JSONB NOT NULL DEFAULT '{}', "
            "status TEXT NOT NULL DEFAULT 'queued', "
            "result JSONB, error TEXT, "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
            "started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ)"))
        conn.execute(text(
            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS project_id INT"))
    _schema_ready = True


# --------------------------------------------------------------------------- #
#  Projects (one per brand)
# --------------------------------------------------------------------------- #
def create_project(name: str) -> dict:
    _ensure_schema()
    with engine.begin() as conn:
        row = conn.execute(
            text("INSERT INTO projects (name) VALUES (:n) "
                 "ON CONFLICT (name) DO UPDATE SET updated_at = now() "
                 "RETURNING *"),
            {"n": name},
        ).mappings().first()
    return dict(row)


def list_projects() -> list[dict]:
    _ensure_schema()
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM projects ORDER BY updated_at DESC")
        ).mappings().all()
    return [dict(r) for r in rows]


def get_project(project_id: int) -> dict | None:
    _ensure_schema()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM projects WHERE id = :id"), {"id": project_id}
        ).mappings().first()
    return dict(row) if row else None


def save_project_state(project_id: int, state: dict) -> None:
    import json as _json
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE projects SET state = :s, updated_at = now() "
                 "WHERE id = :id"),
            {"s": _json.dumps(state), "id": project_id},
        )


def delete_project(project_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM projects WHERE id = :id"),
                     {"id": project_id})


# --------------------------------------------------------------------------- #
#  Job queue (worker processes one at a time)
# --------------------------------------------------------------------------- #
def enqueue_job(project_id: int, project_name: str, job_type: str,
                payload: dict, label: str = "") -> int:
    import json as _json
    _ensure_schema()
    with engine.begin() as conn:
        row = conn.execute(
            text("INSERT INTO job_queue (project_id, project_name, job_type, "
                 "label, payload) VALUES (:pid, :pn, :jt, :lb, :pl) "
                 "RETURNING id"),
            {"pid": project_id, "pn": project_name, "jt": job_type,
             "lb": label, "pl": _json.dumps(payload)},
        ).first()
    return row[0]


def claim_next_job() -> dict | None:
    """Atomically grab the oldest queued job and mark it running."""
    _ensure_schema()
    with engine.begin() as conn:
        row = conn.execute(text(
            "UPDATE job_queue SET status='running', started_at=now() "
            "WHERE id = (SELECT id FROM job_queue WHERE status='queued' "
            "ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *"
        )).mappings().first()
    return dict(row) if row else None


def set_job_agent(job_id: int, agent: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE job_queue SET agent=:a WHERE id=:id"),
                     {"a": agent, "id": job_id})


def finish_job(job_id: int, result: dict) -> None:
    import json as _json
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE job_queue SET status='done', result=:r, agent='', "
            "finished_at=now() WHERE id=:id"),
            {"r": _json.dumps(result), "id": job_id})


def fail_job(job_id: int, error: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE job_queue SET status='failed', error=:e, agent='', "
            "finished_at=now() WHERE id=:id"),
            {"e": error[:2000], "id": job_id})


def get_running_job() -> dict | None:
    # /api/status is the first call the UI makes, so on a brand-new database
    # this can run before anything else has created job_queue.
    _ensure_schema()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT * FROM job_queue WHERE status='running' "
            "ORDER BY started_at LIMIT 1")).mappings().first()
    return dict(row) if row else None


def list_jobs(project_id: int, limit: int = 15) -> list[dict]:
    _ensure_schema()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT * FROM job_queue WHERE project_id=:pid "
            "ORDER BY created_at DESC LIMIT :lim"),
            {"pid": project_id, "lim": limit}).mappings().all()
    return [dict(r) for r in rows]


def queue_depth() -> int:
    _ensure_schema()  # same fresh-database path as get_running_job()
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT count(*) FROM job_queue WHERE status='queued'")).scalar()


def get_brand_kit(client_name: str) -> dict | None:
    """Fetch the stored brand kit for a client (case-insensitive), if any."""
    _ensure_schema()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM brand_kits WHERE lower(client_name) = "
                 "lower(:cn)"),
            {"cn": client_name},
        ).mappings().first()
    return dict(row) if row else None


def save_brand_kit(kit: dict) -> None:
    """Insert or update a client's brand kit."""
    _ensure_schema()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO brand_kits (client_name, colors, font_style, "
                "logo_description, handle, website, style_notes) VALUES "
                "(:cn, :co, :fs, :ld, :ha, :we, :sn) "
                "ON CONFLICT (client_name) DO UPDATE SET colors = :co, "
                "font_style = :fs, logo_description = :ld, handle = :ha, "
                "website = :we, style_notes = :sn, updated_at = now()"
            ),
            {
                "cn": kit.get("client_name", ""),
                "co": kit.get("colors") or [],
                "fs": kit.get("font_style", ""),
                "ld": kit.get("logo_description", ""),
                "ha": kit.get("handle", ""),
                "we": kit.get("website", ""),
                "sn": kit.get("style_notes", ""),
            },
        )


def ping() -> bool:
    """Return True if the database is reachable and the posts table exists."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        conn.execute(text("SELECT 1 FROM posts LIMIT 1"))
    return True


def fetch_posts(status: str | None = None,
                project_id: int | None = None) -> list[dict]:
    """Return posts, optionally filtered by status and/or project, newest first."""
    _ensure_schema()
    q = "SELECT * FROM posts"
    params, where = {}, []
    if status:
        where.append("status = :status")
        params["status"] = status
    if project_id is not None:
        where.append("project_id = :pid")
        params["pid"] = project_id
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY created_at DESC"
    with engine.connect() as conn:
        rows = conn.execute(text(q), params).mappings().all()
    return [dict(r) for r in rows]


def update_status(post_id: str, status: str) -> None:
    """Flip a post's approval status (the HITL gate)."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE posts SET status = :s WHERE post_id = :pid"),
            {"s": status, "pid": post_id},
        )


def update_caption(post_id: str, hook: str, caption: str) -> None:
    """Let a human edit copy before approving."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE posts SET hook_text = :h, body_caption = :c "
                "WHERE post_id = :pid"
            ),
            {"h": hook, "c": caption, "pid": post_id},
        )


def insert_post(post, project_id: int | None = None) -> str:
    """Persist a CopyAndDesignSchema as a row in the posts table (the content
    conveyor belt). Returns the post_id."""
    import json as _json

    _ensure_schema()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO posts (post_id, client_name, scheduled_date, "
                "target_platforms, pillar, hook_text, body_caption, hashtags, "
                "cta_text, visual_prompt, image_path, image_variants, "
                "platform_variants, content_format, carousel_slides, "
                "reel_script, status, project_id) VALUES (:pid, :cn, :sd, "
                ":tp, :pl, :hk, :bc, :ht, :cta, :vp, :img, :iv, :pv, :cf, :cs, "
                ":rs, :st, :prj) "
                "ON CONFLICT (post_id) DO NOTHING"
            ),
            {
                "prj": project_id,
                "pid": post.post_id,
                "cn": post.client_name,
                "sd": post.scheduled_date,
                "tp": [p.value for p in post.target_platforms],
                "pl": post.pillar,
                "hk": post.hook_text,
                "bc": post.body_caption,
                "ht": post.hashtags,
                "cta": post.cta_text,
                "vp": post.visual_generation_prompt,
                "img": post.image_path,
                "iv": post.image_variants,
                "pv": _json.dumps(
                    [v.model_dump(mode="json") for v in post.platform_variants]),
                "cf": post.content_format.value,
                "cs": _json.dumps(
                    [s.model_dump(mode="json") for s in post.carousel_slides]),
                "rs": (_json.dumps(post.reel_script.model_dump(mode="json"))
                       if post.reel_script else None),
                "st": post.status.value,
            },
        )
    return post.post_id


def update_image(post_id: str, image_path: str) -> None:
    """Point a post at a freshly regenerated image."""
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE posts SET image_path = :img WHERE post_id = :pid"),
            {"img": image_path, "pid": post_id},
        )


def insert_sample_post() -> str:
    """Insert a demo post so the approval flow can be exercised before the
    copy/design agents exist. Returns the new post_id."""
    import uuid

    pid = f"demo-{uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO posts (post_id, client_name, scheduled_date, "
                "target_platforms, pillar, hook_text, body_caption, hashtags, "
                "visual_prompt, status) VALUES (:pid, :cn, :sd, :tp, :pl, :hk, "
                ":bc, :ht, :vp, :st)"
            ),
            {
                "pid": pid,
                "cn": "Bean There",
                "sd": "2026-08-03",
                "tp": ["instagram", "linkedin"],
                "pl": "Sustainability Stories",
                "hk": "Your morning cup is quietly saving the planet ☕",
                "bc": "Every bean we roast is sourced from farms that pay fair "
                "wages and regenerate their soil.\n\nSwing by this weekday and "
                "taste the difference sustainability makes.\n\n👉 Show this post "
                "for 10% off before noon.",
                "ht": ["#vegancoffee", "#sustainablecafe", "#mumbaicafe",
                       "#specialtycoffee"],
                "vp": "A warm overhead shot of a latte on a reclaimed-wood table, "
                "morning light, green plants in soft focus background",
                "st": "Pending Human Review",
            },
        )
    return pid
