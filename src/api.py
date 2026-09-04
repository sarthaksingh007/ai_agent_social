"""
REST API behind the React control panel (replaces the Streamlit dashboard).

Deliberately thin: every endpoint is a direct wrapper over `src.db`, so the
React app is the only place that holds UI state. Heavy agent work still happens
in the separate `worker` container — this process only enqueues jobs, so a
CrewAI crash can never take the UI down.

The one rule: never import the agent stack (crewai/litellm/Pillow) at module
level. Those native libs are slow to load and have historically destabilised
long-lived server processes; `publish` is imported lazily inside its handler.
"""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src import config, db
from src.jobs import AGENTS

IMAGE_DIR = Path(os.getenv("IMAGE_DIR", "/app/generated_images"))

app = FastAPI(title="Social Media Agency API", version="1.0")

# The SPA is served same-origin through nginx in production; CORS is only here
# so `npm run dev` on :5173 can talk to this API directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
#  Request bodies
# --------------------------------------------------------------------------- #
class ProjectIn(BaseModel):
    name: str


class StateIn(BaseModel):
    state: dict


class JobIn(BaseModel):
    job_type: str
    payload: dict = {}
    label: str = ""


class PostPatch(BaseModel):
    status: str | None = None
    hook_text: str | None = None
    body_caption: str | None = None
    image_path: str | None = None


class BrandKitIn(BaseModel):
    client_name: str
    colors: list[str] = []
    font_style: str = ""
    logo_description: str = ""
    handle: str = ""
    website: str = ""
    style_notes: str = ""


# --------------------------------------------------------------------------- #
#  Meta
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict:
    try:
        db.ping()
        return {"ok": True, "database": "up"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"Database not reachable: {exc}") from exc


@app.get("/api/config")
def get_config() -> dict:
    """Everything the UI needs to render itself: agent roster, models, the demo
    brief, and any setup problems worth surfacing as a banner."""
    return {
        "agents": AGENTS,
        "models": config.AGENT_MODELS,
        "sample_brief": config.SAMPLE_BRIEF,
        "problems": config.check(),
    }


@app.get("/api/status")
def status() -> dict:
    """Live worker state — the React app polls this to drive the agent panel."""
    running = db.get_running_job()
    return {
        "running": running,
        "active_agent": running["agent"] if running else None,
        "queue_depth": db.queue_depth(),
    }


# --------------------------------------------------------------------------- #
#  Projects
# --------------------------------------------------------------------------- #
@app.get("/api/projects")
def list_projects() -> list[dict]:
    return db.list_projects()


@app.post("/api/projects", status_code=201)
def create_project(body: ProjectIn) -> dict:
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Project name cannot be empty")
    return db.create_project(name)


@app.get("/api/projects/{project_id}")
def get_project(project_id: int) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@app.put("/api/projects/{project_id}/state")
def save_state(project_id: int, body: StateIn) -> dict:
    if not db.get_project(project_id):
        raise HTTPException(404, "Project not found")
    db.save_project_state(project_id, body.state)
    return {"ok": True}


@app.delete("/api/projects/{project_id}", status_code=204)
def delete_project(project_id: int) -> None:
    db.delete_project(project_id)


# --------------------------------------------------------------------------- #
#  Job queue
# --------------------------------------------------------------------------- #
@app.get("/api/projects/{project_id}/jobs")
def list_jobs(project_id: int, limit: int = 25) -> list[dict]:
    return db.list_jobs(project_id, limit=limit)


@app.post("/api/projects/{project_id}/jobs", status_code=201)
def enqueue_job(project_id: int, body: JobIn) -> dict:
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    job_id = db.enqueue_job(project_id, project["name"], body.job_type,
                            body.payload, body.label)
    return {"id": job_id, "status": "queued"}


# --------------------------------------------------------------------------- #
#  Posts (the approval desk)
# --------------------------------------------------------------------------- #
@app.get("/api/projects/{project_id}/posts")
def list_posts(project_id: int) -> list[dict]:
    return [_with_image_urls(p) for p in db.fetch_posts(project_id=project_id)]


@app.patch("/api/posts/{post_id}")
def patch_post(post_id: str, body: PostPatch) -> dict:
    """Save copy edits, flip the approval status, or select an image variant.
    Any combination in one call — the UI's Save button sends both fields."""
    if body.hook_text is not None or body.body_caption is not None:
        db.update_caption(post_id, body.hook_text or "", body.body_caption or "")
    if body.image_path is not None:
        db.update_image(post_id, body.image_path)
    if body.status is not None:
        db.update_status(post_id, body.status)
    return {"ok": True}


@app.post("/api/posts/{post_id}/publish")
def publish(post_id: str) -> dict:
    posts = [p for p in db.fetch_posts() if p["post_id"] == post_id]
    if not posts:
        raise HTTPException(404, "Post not found")
    from src.publish import publish_post  # heavy-ish import, keep it lazy
    return {"sent_via": publish_post(posts[0])}


# --------------------------------------------------------------------------- #
#  Brand kits
# --------------------------------------------------------------------------- #
@app.get("/api/brand-kits/{client_name}")
def get_brand_kit(client_name: str) -> dict:
    return db.get_brand_kit(client_name) or {}


@app.put("/api/brand-kits")
def save_brand_kit(body: BrandKitIn) -> dict:
    if not body.client_name.strip():
        raise HTTPException(400, "client_name is required")
    db.save_brand_kit(body.model_dump())
    return {"ok": True}


# --------------------------------------------------------------------------- #
#  Generated images
# --------------------------------------------------------------------------- #
@app.get("/api/images/{filename}")
def get_image(filename: str):
    """Serve one generated poster. Only the basename is accepted, so a crafted
    path can't escape IMAGE_DIR."""
    safe = Path(filename).name
    path = IMAGE_DIR / safe
    if not path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(path)


def _image_url(path: str | None) -> str | None:
    """Map a stored absolute container path to a URL the browser can fetch.
    Returns None when the file is gone, so the UI can show a 'regenerate' hint."""
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    return f"/api/images/{p.name}"


def _with_image_urls(post: dict) -> dict:
    post = dict(post)
    post["image_url"] = _image_url(post.get("image_path"))
    post["image_variant_urls"] = [
        {"path": v, "url": _image_url(v)}
        for v in (post.get("image_variants") or [])
        if _image_url(v)
    ]
    return post
