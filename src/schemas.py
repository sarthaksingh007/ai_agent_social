"""
Schema Contracts (Pydantic Gating)  —  PRD §4.

The core of the anti-hallucination design: agents never hand off raw text.
Every handoff between agents MUST be one of these validated objects. If an
agent's output doesn't fit the schema, it's rejected before the next agent
ever sees it.

Handoff chain:
    Account Manager  -> BrandDossier
    Strategist       -> StrategySchema      (validated by the Adversarial Gate)
    Project Manager  -> WeeklyPlan[]
    Copywriter       -> CopyAndDesignSchema
    Designer         -> CopyAndDesignSchema  (image_path filled in)

Design refinements from role research (docs/role_knowledge.md):
  * BrandDossier tracks `kpis` explicitly — the most-omitted brief field.
  * StrategySchema enforces the 3-5 content-pillar rule in code (deterministic).
  * ValidationResult is a hybrid gate: deterministic per-dimension booleans
    (LLM-as-judge pattern) + actionable correction notes.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


# --------------------------------------------------------------------------- #
#  Shared enums
# --------------------------------------------------------------------------- #
class Platform(str, Enum):
    """Supported publishing targets."""
    instagram = "instagram"
    linkedin = "linkedin"
    twitter = "twitter"
    facebook = "facebook"
    tiktok = "tiktok"

    @classmethod
    def _missing_(cls, value):
        # LLMs often return 'Instagram', 'X', 'IG' etc. — normalize gracefully.
        if isinstance(value, str):
            v = value.strip().lower()
            aliases = {"x": "twitter", "ig": "instagram", "insta": "instagram",
                       "fb": "facebook"}
            v = aliases.get(v, v)
            for member in cls:
                if member.value == v:
                    return member
        return None


class PostStatus(str, Enum):
    """Mirrors the `status` column on the Postgres `posts` table (HITL gate)."""
    pending = "Pending Human Review"
    approved = "Approved"
    rejected = "Rejected"
    published = "Published"


class ContentFormat(str, Enum):
    """How a post is delivered. Drives what the Copywriter writes and how many
    images the Designer generates."""
    post = "post"          # single image + caption (the original behavior)
    carousel = "carousel"  # 3 sequential slides, one image each
    reel = "reel"          # a shot-by-shot video script + one cover image

    @classmethod
    def _missing_(cls, value):
        # LLMs / older payloads may send 'single', 'story', 'video', etc.
        if isinstance(value, str):
            v = value.strip().lower()
            aliases = {"single": "post", "image": "post", "static": "post",
                       "video": "reel", "reels": "reel", "short": "reel",
                       "slides": "carousel", "swipe": "carousel"}
            v = aliases.get(v, v)
            for member in cls:
                if member.value == v:
                    return member
        return None


# --------------------------------------------------------------------------- #
#  Agent 1 — Account Manager  ->  BrandDossier
# --------------------------------------------------------------------------- #
class BrandDossier(BaseModel):
    """Standardized brand brief. If required fields can't be filled from the
    raw input, the Account Manager sets `insufficient_context=True` and halts
    instead of guessing (PRD §3, Agent 1 guardrail)."""
    client_name: str = Field(description="Official brand / client name")
    industry: str = Field(description="Industry or niche the brand operates in")
    target_audience: str = Field(description="Primary audience the brand wants to reach")
    brand_voice: str = Field(description="Tone and personality, e.g. 'playful and bold'")
    target_platforms: List[Platform] = Field(
        default_factory=list, description="Platforms the brand wants to post on"
    )
    goals: List[str] = Field(
        default_factory=list, description="Marketing goals, e.g. 'grow followers'"
    )
    # Research: KPIs/success metrics are the single most-omitted brief field.
    kpis: List[str] = Field(
        default_factory=list,
        description="Measurable success metrics, e.g. '+20% IG followers in 90 days'",
    )
    key_products: List[str] = Field(
        default_factory=list, description="Main products/services to feature"
    )
    known_competitors: List[str] = Field(
        default_factory=list, description="Competitor names or URLs, if provided"
    )

    # Guardrail flags
    insufficient_context: bool = Field(
        default=False,
        description="True when essential brand info is missing; halts the pipeline",
    )
    missing_fields: List[str] = Field(
        default_factory=list,
        description="Names of the required fields that were missing from the brief",
    )


# --------------------------------------------------------------------------- #
#  Agent 2 — Strategist  ->  StrategySchema
# --------------------------------------------------------------------------- #
class ContentPillar(BaseModel):
    """A core content theme, each tied back to evidence (PRD §4)."""
    pillar_name: str = Field(description="Name of the core brand content category")
    justification: str = Field(
        description="Direct logical connection to the verified client data profile"
    )
    evidence_urls: List[HttpUrl] = Field(
        default_factory=list,
        description="Source URLs supporting this pillar (evidence tracking, PRD §1)",
    )


class PostStructure(BaseModel):
    """One slot in the month's calendar skeleton (PRD §4)."""
    date: str = Field(description="Target date, ISO format YYYY-MM-DD")
    platform: List[Platform]
    pillar: str = Field(description="Which content pillar this post belongs to")
    angle_and_objective: str = Field(
        description="The specific angle and what this post should achieve"
    )


class StrategySchema(BaseModel):
    """Strategist output — the whole month's plan. This is the object the
    Adversarial Gate (Agent 3) cross-examines against the BrandDossier."""
    client_name: str
    competitor_urls_scanned: List[HttpUrl] = Field(
        default_factory=list, description="Competitor URLs actually crawled"
    )
    market_trends_discovered: List[str] = Field(
        default_factory=list, description="Trends found during research"
    )
    content_pillars: List[ContentPillar] = Field(
        description="Exactly 3-5 pillars (deterministically enforced)"
    )
    one_month_calendar_skeleton: List[PostStructure] = Field(
        description="Macro monthly distribution of posts"
    )

    @field_validator("content_pillars")
    @classmethod
    def _enforce_pillar_count(cls, v: List[ContentPillar]) -> List[ContentPillar]:
        # Research rule: <3 limits variety, >5 dilutes messaging.
        if not 3 <= len(v) <= 5:
            raise ValueError(
                f"content_pillars must have 3-5 items, got {len(v)}"
            )
        return v


# --------------------------------------------------------------------------- #
#  Agent 3 — Strategy Validator (Adversarial Gate)  ->  ValidationResult
# --------------------------------------------------------------------------- #
class DimensionCheck(BaseModel):
    """One rubric dimension the validator judges (LLM-as-judge pattern).
    Boolean pass/fail is more reliable than 1-10 scores.

    `hard` checks block approval and trigger a retry; `soft` checks are advisory
    (recorded + shown, but don't fail the whole strategy). Evidence citations and
    the LLM's on-brand judgment are soft because free web search is unreliable
    and a small local judge is noisy."""
    dimension: str = Field(description="e.g. 'pillar_count', 'evidence', 'on_brand'")
    passed: bool
    reason: str = Field(description="Concrete justification for the verdict")
    hard: bool = Field(default=True, description="If True, a fail blocks approval")


class ValidationResult(BaseModel):
    """Verdict from the adversarial validator. On failure the pipeline routes
    the context backward with `correction_notes` (PRD §3, Agent 3).

    `checks` holds the per-dimension results (deterministic + LLM). `approved`
    is only true when every check passes."""
    approved: bool = Field(description="True only if the strategy passes all checks")
    checks: List[DimensionCheck] = Field(
        default_factory=list, description="Per-dimension pass/fail results"
    )
    correction_notes: List[str] = Field(
        default_factory=list,
        description="Specific, actionable fixes the Strategist must apply on reject",
    )
    missing_citations: List[str] = Field(
        default_factory=list,
        description="Claims/pillars that lacked required evidence URLs",
    )

    @model_validator(mode="after")
    def _sync_approved(self) -> "ValidationResult":
        # approved can't be true if any HARD check failed (soft checks advisory).
        if self.checks and any(not c.passed for c in self.checks if c.hard):
            self.approved = False
        return self


# --------------------------------------------------------------------------- #
#  Agent 4 — Project Manager  ->  WeeklyPlan
# --------------------------------------------------------------------------- #
class WeeklyPlan(BaseModel):
    """A single week sliced out of the monthly skeleton (PRD §3, Agent 4)."""
    week_number: int = Field(ge=1, description="1-based week index within the month")
    theme: str = Field(description="Focus/theme for this week")
    posts: List[PostStructure] = Field(description="Posts scheduled for this week")


# --------------------------------------------------------------------------- #
#  Brand Kit — stored once per client, auto-injected into every generation
# --------------------------------------------------------------------------- #
class BrandKit(BaseModel):
    """Brand identity injected into every poster + caption (the research's
    #1 'feels professional' SaaS feature)."""
    client_name: str
    colors: List[str] = Field(
        default_factory=list, description="Brand hex colors, e.g. ['#E63946']")
    font_style: str = Field(
        default="", description="Typography style, e.g. 'elegant modern serif'")
    logo_description: str = Field(
        default="",
        description="Literal logo description the designer can render, e.g. "
        "'minimal golden mortar-and-pestle icon'")
    handle: str = Field(default="", description="Social handle, e.g. @umamispices")
    website: str = Field(default="", description="Website shown on posters")
    style_notes: str = Field(
        default="", description="Extra do's/don'ts for visuals and voice")


class PlatformVariant(BaseModel):
    """A caption adapted to one platform's tone and hashtag norms."""
    platform: Platform
    body_caption: str
    hashtags: List[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
#  Format-specific payloads (carousel slides / reel script)
# --------------------------------------------------------------------------- #
class CarouselSlide(BaseModel):
    """One frame in a 3-slide carousel. Slides form a sequence:
    slide 1 hooks, slide 2 delivers value, slide 3 drives the CTA."""
    slide_no: int = Field(ge=1, description="1-based slide position")
    headline: str = Field(description="Short on-slide text (3-6 words), overlaid")
    caption: str = Field(default="", description="Optional supporting line")
    visual_generation_prompt: str = Field(
        description="Literal, TEXT-FREE photo brief for this slide's image")
    image_path: Optional[str] = Field(
        default=None, description="Generated image path (filled by Designer)")


class ReelScene(BaseModel):
    """One shot in a reel's shot-list."""
    shot: str = Field(description="What's filmed / on screen for this beat")
    on_screen_text: str = Field(default="", description="Text caption on the clip")
    voiceover: str = Field(default="", description="One line of narration/dialogue")


class ReelScript(BaseModel):
    """A ready-to-shoot short-form video script + its cover-frame brief."""
    hook: str = Field(description="First 3 seconds — the scroll-stopping opener")
    scenes: List[ReelScene] = Field(
        default_factory=list, description="3-5 sequential shots")
    cta: str = Field(default="", description="Closing call-to-action")
    audio_suggestion: str = Field(
        default="", description="Trending audio / music vibe to use")
    duration_seconds: int = Field(default=30, description="Target length, 15-45s")
    cover_prompt: str = Field(
        default="", description="Literal, TEXT-FREE photo brief for the cover frame")


# --------------------------------------------------------------------------- #
#  Agents 5 & 6 — Copywriter + Designer  ->  CopyAndDesignSchema
# --------------------------------------------------------------------------- #
class CopyAndDesignSchema(BaseModel):
    """Final per-post payload written to Postgres (PRD §4). The Copywriter fills
    everything except `image_path`; the Designer fills `image_path`."""
    post_id: str = Field(description="Unique id for this post")
    client_name: str
    scheduled_date: str = Field(description="ISO date YYYY-MM-DD")
    target_platforms: List[Platform]
    pillar: str = Field(description="Content pillar this post belongs to")
    content_format: ContentFormat = Field(
        default=ContentFormat.post,
        description="Delivery format: single post, carousel, or reel")
    hook_text: str = Field(description="Scroll-stopping opening line, 5-10 words")
    body_caption: str = Field(description="Main caption body: Hook -> Body -> CTA")
    hashtags: List[str] = Field(
        default_factory=list,
        description="Per-platform counts: IG 3-5, LinkedIn 1-3, X 1-2",
    )
    cta_text: str = Field(
        default="",
        description="Short call-to-action button text, e.g. 'Order Today'",
    )
    visual_generation_prompt: str = Field(
        description=(
            "Literal, text-free description for the image engine "
            "(Subject + Setting + Composition + Style + Lighting). "
            "Abstract text/metaphors are illegal; on-image text is added later."
        )
    )
    platform_variants: List[PlatformVariant] = Field(
        default_factory=list,
        description="Per-platform caption adaptations (IG casual, LinkedIn pro)")
    image_path: Optional[str] = Field(
        default=None, description="Path/URL of the chosen image (filled by Designer)"
    )
    image_variants: List[str] = Field(
        default_factory=list,
        description="Paths of all generated poster variants (pick one in UI)")
    # --- Format-specific payloads (only one is populated, per content_format) ---
    carousel_slides: List[CarouselSlide] = Field(
        default_factory=list,
        description="Slides when content_format == carousel (3 slides)")
    reel_script: Optional[ReelScript] = Field(
        default=None,
        description="Script when content_format == reel")
    status: PostStatus = Field(
        default=PostStatus.pending,
        description="Human-in-the-loop gate state (starts as Pending Human Review)",
    )
