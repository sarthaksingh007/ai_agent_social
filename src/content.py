"""
Agent 5 (Copywriter) + Agent 6 (Designer).

Copywriter turns one calendar slot into a full CopyAndDesignSchema (hook, body,
hashtags, literal image prompt). Designer generates the image. Both operate per
post. We use a direct LLM call (not a CrewAI ReAct loop) for speed on the local
model — one prompt in, one JSON out.

Copy rules baked in from the research (docs/role_knowledge.md):
  hook first (5-10 words) → body → one CTA; hashtags IG 3-5 / LinkedIn 1-3 / X 1-2;
  the visual prompt must be literal and TEXT-FREE.
"""
import json
import uuid

from src.images import VARIANT_HINTS, generate_image
from src.llm import get_llm
from src.schemas import (
    BrandDossier,
    CarouselSlide,
    ContentFormat,
    CopyAndDesignSchema,
    PlatformVariant,
    PostStructure,
    ReelScene,
    ReelScript,
)


def _new_post_id(client_name: str) -> str:
    slug = "".join(c for c in client_name.lower() if c.isalnum())[:6] or "post"
    return f"{slug}-{uuid.uuid4().hex[:6]}"


# Format-specific instructions appended to the base copy prompt. Each asks the
# model for one extra JSON key that we parse into the format's payload.
_CAROUSEL_INSTRUCTIONS = (
    '  "carousel_slides": an array of EXACTLY 3 objects forming a swipe '
    "sequence — slide 1 hooks attention, slide 2 delivers the value/detail, "
    "slide 3 lands the CTA. Each object: "
    '{"slide_no": 1-3, "headline": short on-slide text of 3-6 words, '
    '"caption": one supporting sentence, "visual_generation_prompt": a LITERAL, '
    "TEXT-FREE 40-60 word photo brief specific to THIS slide (subject, props, "
    "setting, composition, lighting). Do NOT request words/letters/logos},\n"
)
_REEL_INSTRUCTIONS = (
    '  "reel_script": an object {"hook": the first-3-seconds scroll-stopping '
    'opener, "scenes": an array of 3-5 objects {"shot": what is filmed, '
    '"on_screen_text": short caption on the clip, "voiceover": one narration '
    'line}, "cta": closing call-to-action, "audio_suggestion": a trending '
    'audio / music vibe, "duration_seconds": 15-45, "cover_prompt": a LITERAL, '
    "TEXT-FREE 40-60 word photo brief for the cover/thumbnail frame (no words "
    "or logos)},\n"
)


def run_copywriter(dossier: BrandDossier, post: PostStructure,
                   brand_kit: dict | None = None,
                   content_format: ContentFormat = ContentFormat.post,
                   ) -> CopyAndDesignSchema:
    """Agent 5: write copy + a literal image prompt for one post. Produces a
    per-platform caption variant for every target platform.

    When `content_format` is carousel or reel, the copywriter also produces the
    format's extra payload (3 slides, or a shot-by-shot script)."""
    content_format = ContentFormat(content_format)
    platforms = [p.value for p in post.platform]
    kit_line = ""
    if brand_kit:
        bits = [b for b in [brand_kit.get("handle"), brand_kit.get("website"),
                            brand_kit.get("style_notes")] if b]
        if bits:
            kit_line = f"Brand kit: {' · '.join(bits)}\n"

    format_line = {
        ContentFormat.carousel: "Format: a 3-slide Instagram CAROUSEL.\n",
        ContentFormat.reel: "Format: a short-form REEL (vertical video).\n",
    }.get(content_format, "Format: a single-image POST.\n")

    extra_key = {
        ContentFormat.carousel: _CAROUSEL_INSTRUCTIONS,
        ContentFormat.reel: _REEL_INSTRUCTIONS,
    }.get(content_format, "")

    prompt = (
        "You are a senior social media copywriter. Write ONE post.\n\n"
        f"Brand: {dossier.client_name} — {dossier.industry}\n"
        f"Voice: {dossier.brand_voice}\n"
        f"{kit_line}"
        f"Audience: {dossier.target_audience}\n"
        f"Pillar: {post.pillar}\n"
        f"Angle/objective: {post.angle_and_objective}\n"
        f"Platforms: {', '.join(platforms)}\n"
        f"{format_line}\n"
        "Return ONLY JSON with these keys:\n"
        '  "hook_text": a 5-10 word scroll-stopping first line,\n'
        '  "body_caption": 3-5 short lines, structure Hook -> Body -> one CTA, '
        "use line breaks,\n"
        '  "hashtags": list of tags (Instagram 3-5, LinkedIn 1-3, mix niche + '
        "branded),\n"
        '  "cta_text": a short 2-4 word call-to-action button label that fits '
        "the post objective (e.g. \"Order Today\", \"Visit Us\", "
        "\"Try The Blend\"),\n"
        '  "platform_variants": one entry PER target platform, each '
        '{"platform", "body_caption", "hashtags"} adapted to that platform: '
        "instagram = casual, emoji-friendly, save-worthy, 3-5 hashtags; "
        "linkedin = professional, insight-led, no emojis, 1-3 hashtags; "
        "twitter = punchy under 280 chars, 1-2 hashtags,\n"
        '  "visual_generation_prompt": a RICH, LITERAL, TEXT-FREE professional '
        "photography prompt of 50-80 words. Describe concretely: the main "
        "subject in vivid detail (colors, textures, materials), supporting "
        "props and styling, the setting/background, composition and camera "
        "angle (e.g. overhead flat lay / 45-degree / close macro), lighting "
        "(e.g. golden-hour window light, dramatic side light), and mood/color "
        "palette that fits the brand. Make it feel like an art director's "
        "shot brief. Do NOT request any words, letters, or logos in the image.\n"
        f"{extra_key}"
        "No prose outside the JSON."
    )
    raw = get_llm(temperature=0.6, max_tokens=1600, role="copywriter").call(
        [{"role": "user", "content": prompt}]
    )
    data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])

    hashtags = data.get("hashtags", [])
    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.split() if h.strip()]

    variants = []
    for v in data.get("platform_variants") or []:
        try:
            variants.append(PlatformVariant.model_validate(v))
        except Exception:  # noqa: BLE001 — a bad variant shouldn't kill the post
            pass

    carousel_slides = _parse_carousel(data) if content_format == ContentFormat.carousel else []
    reel_script = _parse_reel(data) if content_format == ContentFormat.reel else None

    return CopyAndDesignSchema(
        post_id=_new_post_id(dossier.client_name),
        client_name=dossier.client_name,
        scheduled_date=post.date,
        target_platforms=post.platform,
        pillar=post.pillar,
        content_format=content_format,
        hook_text=data["hook_text"],
        body_caption=data["body_caption"],
        hashtags=hashtags,
        cta_text=str(data.get("cta_text", "") or ""),
        platform_variants=variants,
        visual_generation_prompt=data["visual_generation_prompt"],
        carousel_slides=carousel_slides,
        reel_script=reel_script,
    )


def _parse_carousel(data: dict) -> list[CarouselSlide]:
    """Coerce the model's carousel_slides into validated slides (best-effort;
    a malformed slide is skipped rather than killing the whole post)."""
    slides = []
    for i, s in enumerate(data.get("carousel_slides") or [], start=1):
        try:
            s.setdefault("slide_no", i)
            slides.append(CarouselSlide.model_validate(s))
        except Exception:  # noqa: BLE001
            pass
    return slides


def _parse_reel(data: dict) -> ReelScript | None:
    rs = data.get("reel_script")
    if not isinstance(rs, dict):
        return None
    scenes = []
    for sc in rs.get("scenes") or []:
        try:
            scenes.append(ReelScene.model_validate(sc))
        except Exception:  # noqa: BLE001
            pass
    try:
        return ReelScript(
            hook=str(rs.get("hook", "") or ""),
            scenes=scenes,
            cta=str(rs.get("cta", "") or ""),
            audio_suggestion=str(rs.get("audio_suggestion", "") or ""),
            duration_seconds=int(rs.get("duration_seconds", 30) or 30),
            cover_prompt=str(rs.get("cover_prompt", "") or ""),
        )
    except Exception:  # noqa: BLE001
        return None


def _handle_for(client_name: str) -> str:
    return "@" + "".join(c for c in client_name.lower() if c.isalnum())


def _first_supporting_line(post: CopyAndDesignSchema) -> str | None:
    """First caption line that isn't just the hook repeated — used as subtext."""
    for line in (post.body_caption or "").strip().splitlines():
        line = line.strip()
        if line and line.lower()[:40] != post.hook_text.lower()[:40]:
            return line[:70]
    return None


def run_designer(post: CopyAndDesignSchema, brand_kit: dict | None = None,
                 variants: int = 1) -> CopyAndDesignSchema:
    """Agent 6: generate the visuals for a post, carousel, or reel.

    * post     — the ad poster(s); variants>1 gives differently-composed options.
    * carousel — one image per slide (3), each with its own headline overlaid.
    * reel     — a single cover/thumbnail frame with the hook overlaid.

    The Brand Kit (colors, logo, typography, handle) is injected into each."""
    fmt = ContentFormat(post.content_format)
    handle = _handle_for(post.client_name)

    if fmt == ContentFormat.carousel and post.carousel_slides:
        paths = []
        for slide in post.carousel_slides:
            path = generate_image(
                slide.visual_generation_prompt or post.visual_generation_prompt,
                f"{post.post_id}-s{slide.slide_no}",
                hook_text=slide.headline,
                subtext=slide.caption or None,
                # Only the final slide carries the CTA button.
                cta=post.cta_text if slide.slide_no == len(post.carousel_slides) else None,
                handle=handle,
                brand=brand_kit,
            )
            slide.image_path = path
            paths.append(path)
        post.image_variants = paths
        post.image_path = paths[0] if paths else None
        return post

    if fmt == ContentFormat.reel:
        cover_prompt = (post.reel_script.cover_prompt if post.reel_script
                        and post.reel_script.cover_prompt
                        else post.visual_generation_prompt)
        hook = (post.reel_script.hook if post.reel_script and post.reel_script.hook
                else post.hook_text)
        path = generate_image(
            cover_prompt,
            f"{post.post_id}-cover",
            hook_text=hook,
            cta=post.cta_text or None,
            handle=handle,
            brand=brand_kit,
        )
        post.image_variants = [path]
        post.image_path = path
        return post

    # Default: single post (optionally multiple poster variants).
    first_line = _first_supporting_line(post)
    variants = max(1, min(variants, len(VARIANT_HINTS)))
    paths = []
    for i in range(variants):
        suffix = f"-v{i + 1}" if variants > 1 else ""
        paths.append(generate_image(
            post.visual_generation_prompt,
            f"{post.post_id}{suffix}",
            hook_text=post.hook_text,
            subtext=first_line,
            cta=post.cta_text or None,
            handle=handle,
            brand=brand_kit,
            variant_hint=VARIANT_HINTS[i],
        ))

    post.image_variants = paths
    post.image_path = paths[0]
    return post
