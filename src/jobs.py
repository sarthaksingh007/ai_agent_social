"""
Job dispatch — maps a queued job to the agent work that fulfils it.

Each job records which agent is active (db.set_job_agent) so the dashboard's
status panel can show it live. Results are merged into the project's saved
state so switching brands restores everything.

Job types:
  dossier   payload {brief}                     -> Account Manager
  strategy  payload {dossier, feedback}         -> Strategist + Validator
  weekly    payload {strategy}                  -> Project Manager (instant)
  copy      payload {dossier, posts, limit}     -> Copywriter
  design    payload {posts, variants}           -> Designer (persists posts)
  regen     payload {post}                       -> Designer (updates one post)
"""
from src import db

# Canonical agent list — the status panel renders these in order.
AGENTS = ["Account Manager", "Strategist", "Validator", "Project Manager",
          "Copywriter", "Designer"]


def dispatch(job: dict) -> dict:
    """Run one job. Returns a dict merged into the project state by the worker
    (keys: patch = state updates, message = human summary)."""
    jt = job["job_type"]
    payload = job["payload"] or {}
    jid = job["id"]

    if jt == "dossier":
        db.set_job_agent(jid, "Account Manager")
        from src.pipeline import run_account_manager
        dossier = run_account_manager(payload["brief"])
        return {"patch": {"dossier": dossier.model_dump(mode="json"),
                          "stage": "dossier"},
                "message": f"Dossier ready for {dossier.client_name or '—'}"}

    if jt == "strategy":
        from src.pipeline import run_strategist
        from src.schemas import BrandDossier
        from src.validator import validate_strategy
        dossier = BrandDossier.model_validate(payload["dossier"])
        db.set_job_agent(jid, "Strategist")
        strategy = run_strategist(dossier, corrections=payload.get("feedback") or [])
        validation = None
        if strategy:
            db.set_job_agent(jid, "Validator")
            validation = validate_strategy(dossier, strategy)
        return {"patch": {
            "strategy": strategy.model_dump(mode="json") if strategy else None,
            "validation": validation.model_dump(mode="json") if validation else None,
            "stage": "strategy"},
            "message": "Strategy + validation ready"}

    if jt == "weekly":
        db.set_job_agent(jid, "Project Manager")
        from src.project_manager import slice_into_weeks
        from src.schemas import StrategySchema
        weeks = slice_into_weeks(StrategySchema.model_validate(payload["strategy"]))
        return {"patch": {"weeks": [w.model_dump(mode="json") for w in weeks],
                          "stage": "weekly"},
                "message": f"{len(weeks)} weekly plans ready"}

    if jt == "copy":
        db.set_job_agent(jid, "Copywriter")
        from src.content import run_copywriter
        from src.schemas import BrandDossier, ContentFormat, PostStructure
        dossier = BrandDossier.model_validate(payload["dossier"])
        kit = db.get_brand_kit(dossier.client_name)
        fmt = ContentFormat(payload.get("content_format", "post"))
        slots = [PostStructure.model_validate(p) for p in payload["posts"]]
        slots = slots[: int(payload.get("limit", 4))]
        drafts = []
        for slot in slots:
            try:
                drafts.append(run_copywriter(dossier, slot, brand_kit=kit,
                                             content_format=fmt)
                              .model_dump(mode="json"))
            except Exception as exc:  # noqa: BLE001
                print(f"[jobs] copy slot failed: {exc}")
        return {"patch": {"drafts": drafts, "stage": "copy"},
                "message": f"Copy ({fmt.value}) written for {len(drafts)} posts"}

    if jt in ("design", "regen"):
        db.set_job_agent(jid, "Designer")
        from src.content import run_designer
        from src.schemas import CopyAndDesignSchema
        update = jt == "regen"
        variants = int(payload.get("variants", 1))
        posts = [CopyAndDesignSchema.model_validate(p) for p in payload["posts"]]
        created = []
        for post in posts:
            try:
                kit = db.get_brand_kit(post.client_name)
                post = run_designer(post, brand_kit=kit, variants=variants)
                if update:
                    db.update_caption(post.post_id, post.hook_text,
                                      post.body_caption)
                    db.update_image(post.post_id, post.image_path)
                else:
                    db.insert_post(post, project_id=job.get("project_id"))
                created.append(post.post_id)
            except Exception as exc:  # noqa: BLE001
                print(f"[jobs] design failed: {exc}")
        return {"patch": {"drafts": None} if not update else {},
                "message": f"{len(created)} poster(s) designed"}

    raise ValueError(f"unknown job_type: {jt}")
