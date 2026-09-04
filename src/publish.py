"""
Publishing trigger (replaces Make.com).  PRD §5.

When a human flips a post to Approved, this fires. Real platform APIs
(Instagram/TikTok) are gated, so the free-friendly default is:
  * write the ready-to-post payload to an OUTBOX folder (JSON the user can hand
    to any scheduler), and
  * optionally POST it to a webhook (n8n / Make.com / Discord / Telegram) if
    PUBLISH_WEBHOOK_URL is set.
Then it marks the post Published.
"""
import json
import os

import requests

from src.db import update_status

OUTBOX_DIR = os.getenv("OUTBOX_DIR", "/app/generated_images/outbox")
WEBHOOK_URL = os.getenv("PUBLISH_WEBHOOK_URL", "")


def publish_post(post: dict) -> str:
    """Publish one approved post. Returns a short status string."""
    os.makedirs(OUTBOX_DIR, exist_ok=True)
    payload = {k: v for k, v in post.items() if k not in ("created_at", "updated_at")}

    # 1. Always drop a ready-to-post record into the outbox.
    with open(os.path.join(OUTBOX_DIR, f"{post['post_id']}.json"), "w") as f:
        json.dump(payload, f, default=str, indent=2)
    sent_via = "outbox"

    # 2. Optionally fire a webhook (the actual "auto-publish" trigger).
    if WEBHOOK_URL:
        try:
            requests.post(WEBHOOK_URL, json=payload, timeout=15).raise_for_status()
            sent_via = "webhook"
        except Exception as exc:  # noqa: BLE001
            sent_via = f"webhook_failed ({exc})"

    update_status(post["post_id"], "Published")
    return sent_via
