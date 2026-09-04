"""
Image generation for Agent 6 (Designer).

Free stack: Pollinations.ai (flux) generates the visual, then Pillow overlays
the hook text. Per the PRD/research, we NEVER ask the AI model to render text
(diffusion garbles letters) — the visual is text-free and we add copy ourselves.

Quality levers:
  * A configurable "house style" suffix is appended to every prompt so all
    brand images look like professional editorial photography.
  * enhance=true lets Pollinations expand the prompt with an LLM pass.
  * A soft gradient (not a flat band) carries the overlaid hook text.
"""
import base64
import os
import textwrap
import time
import urllib.parse
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont

IMAGE_DIR = os.getenv("IMAGE_DIR", "/app/generated_images")

# Provider: "openai" (gpt-image-1, best quality, uses OPENAI_API_KEY),
# "cloudflare" (FLUX.2 on Workers AI — free tier, good text rendering) or
# "pollinations" (free, but their anonymous API is unreliable lately).
IMAGE_PROVIDER = os.getenv(
    "IMAGE_PROVIDER",
    "openai" if os.getenv("OPENAI_API_KEY") else "pollinations",
)
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
OPENAI_IMAGE_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "medium")

# Cloudflare Workers AI (free tier). Needs CLOUDFLARE_ACCOUNT_ID + a Workers-AI
# API token. FLUX.2 Klein renders text well enough to design the full poster.
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
CLOUDFLARE_IMAGE_MODEL = os.getenv(
    "CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-2-klein-9b")
# Portrait target; if the model rejects these dims we retry prompt-only.
CLOUDFLARE_IMAGE_WIDTH = int(os.getenv("CLOUDFLARE_IMAGE_WIDTH", "1024"))
CLOUDFLARE_IMAGE_HEIGHT = int(os.getenv("CLOUDFLARE_IMAGE_HEIGHT", "1280"))

# House style appended to every visual prompt (override via env to re-brand).
# Tuned for premium BRAND-AD imagery (think national-brand campaign, e.g.
# Baskin-Robbins / Starbucks): clean commercial polish, vivid but tasteful
# color, hero product styling, and a crisp, uncluttered composition.
STYLE_SUFFIX = os.getenv(
    "IMAGE_STYLE_SUFFIX",
    "high-end commercial advertising photography, professional brand campaign "
    "look, hero product beautifully styled and front-and-center, vibrant yet "
    "tasteful color palette, glossy premium finish, immaculate clean "
    "background with plenty of negative space, studio-grade softbox lighting "
    "with soft realistic shadows and gentle highlights, shot on a full-frame "
    "camera with an 85mm lens and shallow depth of field, crisp ultra-sharp "
    "focus, appetizing and aspirational styling, award-winning art direction, "
    "magazine-quality, 8k ultra detailed, photorealistic",
)

# Premium ad-poster template (user-specified). Placeholders are filled per post.
POSTER_TEMPLATE = """Create a premium Instagram promotional poster (portrait 4:5) with a modern, clean, high-converting advertising layout.

Hero subject / scene: {scene}

Text to render EXACTLY as written (and no other words, watermarks or invented logos):
- Large headline at the top: "{headline}"
{extra_text_lines}
Style:
- Minimalist luxury aesthetic
- Bold typography with strong visual hierarchy
- Plenty of negative space
- Professional social media advertisement
- Vibrant yet elegant color palette
- Soft lighting and realistic shadows
- High-end commercial photography look

Layout:
- Eye-catching hero subject occupying 50-60% of the canvas
- Large headline at the top
- Supporting text beneath the headline
- Strong call-to-action element near the bottom
- Clear empty space reserved in the top-left corner for a logo
- Social media handle at the bottom
- CRITICAL LAYOUT RULE: the top 12% and bottom 12% of the canvas must contain ONLY background imagery — every text element, the logo, and the CTA button must sit inside the central 76% of the frame (the image will be cropped to 4:5, so anything near the top or bottom edge is lost)

Design details:
- Layered composition, premium gradients, glassmorphism accents
- Modern geometric shapes, soft glow effects, subtle depth and shadows
- Crisp, ultra-sharp typography, realistic textures
- Marketing-focused composition that immediately grabs attention while remaining uncluttered

Quality: Ultra HD, photorealistic, award-winning advertising design, premium brand identity, perfect alignment, magazine-quality composition, professionally designed Instagram advertisement."""


# Composition hints that make multi-variant posters genuinely different.
VARIANT_HINTS = [
    "",
    " Alternative composition for this variant: dramatic close-up macro of "
    "the hero subject filling the frame.",
    " Alternative composition for this variant: elegant top-down flat-lay "
    "arrangement on a styled surface.",
]


def build_poster_prompt(scene: str, headline: str, subtext: str | None = None,
                        cta: str | None = None, handle: str | None = None,
                        brand: dict | None = None,
                        variant_hint: str = "") -> str:
    """Fill the poster template with this post's real text elements, plus the
    client's Brand Kit (colors, typography, logo, handle, website)."""
    brand = brand or {}
    lines = []
    if subtext:
        lines.append(f'- Supporting text beneath the headline: "{subtext}"')
    if cta:
        lines.append(f'- Call-to-action button near the bottom: "{cta}"')

    handle = brand.get("handle") or handle
    footer = " ".join(x for x in [handle, brand.get("website", "")] if x)
    if footer:
        lines.append(f'- Social media handle / website at the bottom: "{footer}"')

    # Brand kit injection
    if brand.get("colors"):
        lines.append(
            "- Use the brand color palette throughout the design: "
            + ", ".join(brand["colors"]))
    if brand.get("font_style"):
        lines.append(f"- Typography style: {brand['font_style']}")
    if brand.get("logo_description"):
        lines.append(
            f"- Render a small brand logo in the top-left corner: "
            f"{brand['logo_description']}")
    if brand.get("style_notes"):
        lines.append(f"- Brand style notes: {brand['style_notes']}")

    extra = ("\n".join(lines) + "\n") if lines else ""
    return POSTER_TEMPLATE.format(scene=scene + variant_hint, headline=headline,
                                  extra_text_lines=extra)

# Set IMAGE_TEXT_OVERLAY=false for clean images with no text band.
TEXT_OVERLAY = os.getenv("IMAGE_TEXT_OVERLAY", "true").lower() != "false"

# Bold fonts, most-preferred first. Covers Linux (Docker), macOS and Windows —
# so headline sizing works locally AND in the container. Bold before regular.
# Override with IMAGE_FONT_PATH to use a specific brand font.
_FONT_CANDIDATES = [
    os.getenv("IMAGE_FONT_PATH", ""),
    # Linux (Docker image)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    # Windows
    "C:\\Windows\\Fonts\\arialbd.ttf",
    # Regular-weight fallbacks
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in _FONT_CANDIDATES:
        if p and os.path.exists(p):
            return ImageFont.truetype(p, size)
    # load_default(size) honors size on Pillow >= 10.1 (older ignores it).
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def _fit_wrap(draw: ImageDraw.ImageDraw, text: str,
              font: ImageFont.FreeTypeFont, max_w: int) -> str:
    """Wrap text so the longest line fits within max_w pixels (measured, not
    guessed from character counts)."""
    for width in range(40, 10, -2):
        wrapped = textwrap.fill(text, width=width)
        longest = max(draw.textlength(line, font=font)
                      for line in wrapped.split("\n"))
        if longest <= max_w:
            return wrapped
    return textwrap.fill(text, width=12)


def _overlay_hook(img: Image.Image, text: str) -> Image.Image:
    """Draw the hook large over a strong bottom gradient so it pops on any
    background. Font size / gradient darkness are tunable via env."""
    img = img.convert("RGB")
    W, H = img.size

    # Bigger, bolder default than before. Override with IMAGE_HOOK_FONT_SCALE.
    font_size = int(H * float(os.getenv("IMAGE_HOOK_FONT_SCALE", "0.062")))
    font = _font(font_size)
    line_spacing = int(font_size * 0.28)
    line_h = font_size + line_spacing

    measure = ImageDraw.Draw(img)
    wrapped = _fit_wrap(measure, text, font, int(W * 0.88))
    n_lines = wrapped.count("\n") + 1
    text_block = line_h * n_lines
    grad_h = text_block + int(H * 0.22)

    # Vertical gradient: transparent -> near-black, blended onto the photo.
    # Darker peak (235) + a longer ramp make white text legible over bright
    # backgrounds (e.g. a sunlit table) where the old gradient washed out.
    max_alpha = int(os.getenv("IMAGE_HOOK_GRADIENT_ALPHA", "235"))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for y in range(grad_h):
        alpha = int(max_alpha * (y / grad_h) ** 1.4)
        odraw.line([(0, H - grad_h + y), (W, H - grad_h + y)],
                   fill=(8, 8, 8, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    x, y0 = int(W * 0.06), H - text_block - int(H * 0.06)
    # A black outline (stroke) around the white text guarantees legibility
    # even where the gradient is faint — cleaner than a plain drop shadow.
    stroke = max(2, font_size // 14)
    draw.multiline_text((x, y0), wrapped, font=font, fill=(255, 255, 255),
                        spacing=line_spacing, stroke_width=stroke,
                        stroke_fill=(0, 0, 0))
    return img


def _openai_generate(prompt: str) -> Image.Image | None:
    """Generate via OpenAI gpt-image-1 (portrait 1024x1536). Returns None on
    failure so the caller can fall back."""
    try:
        resp = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}"},
            json={
                "model": OPENAI_IMAGE_MODEL,
                "prompt": prompt,
                "size": "1024x1536",
                "quality": OPENAI_IMAGE_QUALITY,
            },
            timeout=300,
        )
        if resp.status_code != 200:
            print(f"[images] openai {resp.status_code}: {resp.text[:200]}")
            return None
        b64 = resp.json()["data"][0]["b64_json"]
        return Image.open(BytesIO(base64.b64decode(b64)))
    except Exception as exc:  # noqa: BLE001
        print(f"[images] openai failed: {exc}")
        return None


def _cloudflare_generate(prompt: str) -> Image.Image | None:
    """Generate via Cloudflare Workers AI (FLUX.2 Klein). Free tier. Returns
    None on failure so the caller can fall back.

    The Workers-AI text-to-image endpoint returns either JSON with a base64
    `result.image`, or raw PNG bytes, depending on the model — handle both.
    """
    if not (CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN):
        print("[images] cloudflare: CLOUDFLARE_ACCOUNT_ID / _API_TOKEN not set")
        return None

    url = (f"https://api.cloudflare.com/client/v4/accounts/"
           f"{CLOUDFLARE_ACCOUNT_ID}/ai/run/{CLOUDFLARE_IMAGE_MODEL}")
    headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"}

    # FLUX.2 on Workers AI takes multipart/form-data (NOT JSON) and returns
    # base64 JPEG in result.image. Fields must be strings.
    files = {
        "prompt": (None, prompt),
        "width": (None, str(CLOUDFLARE_IMAGE_WIDTH)),
        "height": (None, str(CLOUDFLARE_IMAGE_HEIGHT)),
    }
    for attempt in range(3):
        try:
            resp = requests.post(url, headers=headers, files=files, timeout=180)
            if resp.status_code == 429:  # rate limited — back off and retry
                time.sleep(15)
                continue
            if resp.status_code != 200:
                print(f"[images] cloudflare {resp.status_code}: {resp.text[:200]}")
                return None
            ctype = resp.headers.get("content-type", "")
            if "application/json" in ctype:
                data = resp.json()
                b64 = (data.get("result") or {}).get("image")
                if not b64:
                    print(f"[images] cloudflare: no image in {str(data)[:200]}")
                    return None
                return Image.open(BytesIO(base64.b64decode(b64)))
            # Some models return raw image bytes instead.
            return Image.open(BytesIO(resp.content))
        except Exception as exc:  # noqa: BLE001
            print(f"[images] cloudflare attempt {attempt + 1} failed: {exc}")
            time.sleep(5)
    return None


def _pollinations_generate(prompt: str, width: int, height: int):
    """Free fallback. Their anonymous API is unreliable (429/500) lately."""
    url = (
        f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
        f"?width={width}&height={height}&model=flux&nologo=true"
    )
    for attempt in range(4):
        try:
            resp = requests.get(url, timeout=180)
            if resp.status_code == 429:
                time.sleep(20)
                continue
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content))
        except Exception as exc:  # noqa: BLE001
            print(f"[images] pollinations attempt {attempt + 1} failed: {exc}")
            time.sleep(8)
    return None


def _crop_to_4x5(img: Image.Image) -> Image.Image:
    """Center-crop to Instagram's 4:5 portrait ratio (e.g. 1024x1280)."""
    W, H = img.size
    target_h = int(W * 1.25)
    if H <= target_h:
        return img
    # Symmetric crop; the poster prompt reserves the top/bottom 12% of the
    # canvas as background-only so nothing important is lost.
    top = (H - target_h) // 2
    return img.crop((0, top, W, top + target_h))


def generate_image(prompt: str, post_id: str, hook_text: str | None = None,
                   subtext: str | None = None, cta: str | None = None,
                   handle: str | None = None, brand: dict | None = None,
                   variant_hint: str = "",
                   width: int = 1080, height: int = 1350) -> str:
    """Generate a 4:5 portrait poster (Instagram-native) and return its path."""
    os.makedirs(IMAGE_DIR, exist_ok=True)
    path = os.path.join(IMAGE_DIR, f"{post_id}.png")

    img = None
    ai_rendered_text = False

    if IMAGE_PROVIDER == "openai":
        if hook_text:
            # gpt-image-1 renders text well — have it DESIGN the full ad
            # poster (headline, subtext, CTA, brand kit) using the template.
            img = _openai_generate(
                build_poster_prompt(f"{prompt}, {STYLE_SUFFIX}", hook_text,
                                    subtext=subtext, cta=cta, handle=handle,
                                    brand=brand, variant_hint=variant_hint))
            ai_rendered_text = img is not None
        else:
            img = _openai_generate(f"{prompt}, {STYLE_SUFFIX}")

    elif IMAGE_PROVIDER == "cloudflare":
        # FLUX.2 makes gorgeous visuals but GARBLES rendered text — so we
        # generate a clean, text-free image and let the Pillow overlay add the
        # (guaranteed-legible) hook. variant_hint keeps multi-variant posters
        # visually distinct.
        img = _cloudflare_generate(f"{prompt}{variant_hint}, {STYLE_SUFFIX}")
        # ai_rendered_text stays False -> _overlay_hook runs below.

    if img is None:  # pollinations path, or the chosen provider failed
        img = _pollinations_generate(f"{prompt}, {STYLE_SUFFIX}", width, height)
    if img is None:  # last resort: branded placeholder
        img = Image.new("RGB", (width, height), (34, 40, 49))

    # Pillow overlay only when the AI didn't already design the text in.
    if hook_text and TEXT_OVERLAY and not ai_rendered_text:
        img = _overlay_hook(img, hook_text)

    img = _crop_to_4x5(img)
    img.save(path)
    return path
