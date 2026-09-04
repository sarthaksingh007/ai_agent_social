"""
Background queue worker.

Runs as its own container (see docker-compose `worker` service). Polls the
job_queue, processes ONE job at a time (so agents never overlap), merges the
result into the owning project's state, and marks the job done/failed.

This is what lets the dashboard stay responsive, show a live "which agent is
working" panel, and accept extra work into a queue while an agent is busy.
"""
import time
import traceback

from src import db
from src.jobs import dispatch


def _apply_patch(project_id: int, patch: dict) -> None:
    """Merge a job's state patch into the project's saved state."""
    if not patch:
        return
    project = db.get_project(project_id)
    if not project:
        return
    state = dict(project.get("state") or {})
    for k, v in patch.items():
        if v is None:
            state.pop(k, None)
        else:
            state[k] = v
    db.save_project_state(project_id, state)


def process_one() -> bool:
    """Claim and run one job. Returns True if a job was processed."""
    job = db.claim_next_job()
    if not job:
        return False

    jid = job["id"]
    print(f"[worker] job {jid} ({job['job_type']}) for "
          f"project '{job.get('project_name')}' — start")
    try:
        result = dispatch(job)
        if job.get("project_id"):
            _apply_patch(job["project_id"], result.get("patch") or {})
        db.finish_job(jid, {"message": result.get("message", "done")})
        print(f"[worker] job {jid} — done: {result.get('message')}")
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        db.fail_job(jid, f"{type(exc).__name__}: {exc}")
        print(f"[worker] job {jid} — FAILED: {exc}")
    return True


def main() -> None:
    print("[worker] started — polling job_queue…")
    while True:
        try:
            if not process_one():
                time.sleep(2)
        except Exception as exc:  # noqa: BLE001 — never let the worker die
            print(f"[worker] loop error: {exc}")
            time.sleep(3)


if __name__ == "__main__":
    main()
