"""
Isolated content runners (invoked as subprocesses by the dashboard).

The Copywriter and Designer are SEPARATE human-gated stages:

  --mode copy    {"dossier": {...}, "posts": [PostStructure...], "limit": N}
                 -> {"posts": [CopyAndDesignSchema...]}          (NO images, no DB)
                 The human reviews/edits the copy before any image is made.

  --mode design  {"posts": [CopyAndDesignSchema...], "update": bool}
                 -> {"created": [ids], "count": N}
                 Generates the ad poster for each (post text may have been
                 edited by the human) and persists to Postgres. With
                 update=true it refreshes existing rows (copy edits + new
                 image) instead of inserting — used for per-post regeneration.

Usage:
    python -m src.generate_posts --mode copy --in-file in.json \
        --out-file out.json --progress-file prog.json
"""
import argparse
import json

from src.schemas import BrandDossier, CopyAndDesignSchema, PostStructure


def _write(path: str, obj) -> None:
    with open(path, "w") as f:
        json.dump(obj, f)


def _run_copy(data: dict, progress_file: str) -> dict:
    from src.content import run_copywriter
    from src.db import get_brand_kit

    dossier = BrandDossier.model_validate(data["dossier"])
    slots = [PostStructure.model_validate(p) for p in data["posts"]]
    slots = slots[: int(data.get("limit", 4))]
    kit = get_brand_kit(dossier.client_name)

    drafts, total = [], len(slots)
    for i, slot in enumerate(slots, start=1):
        _write(progress_file, {"done": i - 1, "total": total,
                               "message": f"Writing copy {i}/{total}…"})
        try:
            drafts.append(
                run_copywriter(dossier, slot, brand_kit=kit)
                .model_dump(mode="json"))
        except Exception as exc:  # noqa: BLE001 — skip a bad slot, keep going
            print(f"[WARN] copy for slot {i} failed: {exc}")
    _write(progress_file, {"done": total, "total": total, "message": "Done"})
    return {"posts": drafts}


def _run_design(data: dict, progress_file: str) -> dict:
    from src.content import run_designer
    from src.db import get_brand_kit, insert_post, update_caption, update_image

    posts = [CopyAndDesignSchema.model_validate(p) for p in data["posts"]]
    update = bool(data.get("update"))
    variants = int(data.get("variants", 1))

    created, total = [], len(posts)
    for i, post in enumerate(posts, start=1):
        _write(progress_file, {"done": i - 1, "total": total,
                               "message": f"Designing image {i}/{total}…"})
        try:
            kit = get_brand_kit(post.client_name)
            post = run_designer(post, brand_kit=kit, variants=variants)
            if update:
                update_caption(post.post_id, post.hook_text, post.body_caption)
                update_image(post.post_id, post.image_path)
            else:
                insert_post(post)
            created.append(post.post_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] design for post {i} failed: {exc}")
    _write(progress_file, {"done": total, "total": total, "message": "Done"})
    return {"created": created, "count": len(created)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=["copy", "design"])
    ap.add_argument("--in-file", required=True)
    ap.add_argument("--out-file", required=True)
    ap.add_argument("--progress-file", required=True)
    args = ap.parse_args()

    with open(args.in_file) as f:
        data = json.load(f)

    if args.mode == "copy":
        out = _run_copy(data, args.progress_file)
    else:
        out = _run_design(data, args.progress_file)

    _write(args.out_file, out)


if __name__ == "__main__":
    main()
