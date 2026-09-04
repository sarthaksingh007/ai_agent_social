# Role Knowledge Base

Researched best practices (2024–2026) for each agent role. Guides Pydantic
schemas and agent prompts. Sources at bottom.

---

## Agent 1 — Account Manager (brief intake → BrandDossier)

**Real-agency fields a brand dossier should capture:**
- Business core: name, industry, mission, USP, products/services
- Goals & KPIs: primary objective (awareness / leads / sales / community)
- Audience: demographics, psychographics, pain points
- Competitors: 3–5 named
- Brand voice/tone + visual identity (colors/hex, fonts, logo, do's/don'ts)
- Platforms & handles; content assets; approval owner

**Rules:**
1. Prefer structured/closed questions over blank text → gap-free data.
2. Flag missing fields explicitly — **KPIs/success metrics are the most-omitted**.
3. A complete dossier = visual identity + verbal identity + positioning + usage rules + governance.

→ *Schema already models this; keep the `missing_fields` + `insufficient_context` gate.*

---

## Agent 2 — Strategist (BrandDossier → StrategySchema)

**Outputs:** 3–5 content pillars, competitor SWOT, monthly themed calendar, per-platform cadence.

**Rules:**
1. **3–5 pillars** — <3 limits variety, >5 dilutes. Start 3–4.
2. **70/20/10 mix** — 70% planned, 20% reactive/trending, 10% experimental.
3. **Competitor analysis = 4 steps:** identify 3–5 → review activity → **SWOT** → monitor.
4. Plan ≥2 weeks ahead; every pillar needs evidence (URLs).

---

## Agent 3 — Strategy Validator (adversarial gate → ValidationResult)

**Pattern: LLM-as-a-Judge + reflection/actor-critic loop.**

**Outputs:** boolean pass/fail **per rubric dimension**, chain-of-thought reasoning, list of actionable `issues` (field + severity + concrete fix), gate decision APPROVE / REVISE / REJECT.

**Rules:**
1. Boolean pass/fail per dimension > 1–10 scores (less judge variance).
2. Split checks: **deterministic** for factual/format (pillar count 3–5, citations present), **LLM judgment** for nuance (on-brand, audience fit).
3. Generation ≠ critique — keep the critic a *separate* agent, adversarial framing.
4. Emit citations, not vague notes. Cap iterations; early-exit when zero issues.

→ *`ValidationResult` covers approved + correction_notes + missing_citations. We'll add deterministic pre-checks in code before the LLM judge runs.*

---

## Agent 4 — Project Manager (StrategySchema → WeeklyPlan[])

**Outputs:** two-tier calendar (monthly themes → weekly tactical). Weekly plan = week theme + per-post rows (type, hook/topic, platform, date/time, owner, status).

**Rules:**
1. Slice month into weeks by theme/campaign; batch-plan 1–2 weeks to avoid repetition.
2. **Cadence norms:** IG 3–5/wk (+2 Stories/day), TikTok 3–5/wk, LinkedIn 2–3/wk (B2B), Facebook 3–5/wk, X 2–3/day.

---

## Agent 5 — Copywriter (post slot → CopyAndDesignSchema)

**Outputs:** platform-tailored caption = **Hook (first line, 5–10 words) → Body (3–5 sentences, line-broken) → CTA**, ~150–200 words, + hashtag set.

**Rules:**
1. Front-load hook before the "…more" cutoff. Line breaks every 1–2 lines.
2. One clear low-friction CTA (posts w/ CTAs get ~70% more comments).
3. **Hashtags per platform:** IG 3–5, LinkedIn 1–3, X 1–2. Mix niche + branded + topic.
4. Persuasion frameworks: **AIDA, PAS, BAB, 4Ps**. Hook types: curiosity gap, pain-point, question, contrarian.

---

## Agent 6 — Designer (visual prompt → image_path)

**Outputs:** literal **text-free** image prompt → generate → overlay text programmatically (Pillow) → final graphic in platform aspect ratio.

**Rules:**
1. **Never bake text into the AI prompt** — diffusion garbles letters. Overlay copy with Pillow after.
2. Prompt structure: **Subject + Setting + Composition + Style + Lighting + Technical flags**. Descriptive sentences, not keyword lists (FLUX).
3. Brand consistency via fixed colors/fonts/logo; keep on-image text minimal + high-contrast.
4. Pollinations.ai = free, no-signup, FLUX-based. Guidance 7–10 creative / 15–20 strict.

---

## Cross-cutting CrewAI design pattern
- Role-based agents map to real social teams; **chain structured outputs** (each agent's Pydantic output = next agent's input).
- Official examples: `crewAIInc/crewAI-examples` (marketing strategy + Instagram post).

## Sources
Account/Strategist: ContentStudio, AgencyAnalytics, Designity, StoryChief, Hootsuite, Sprout Social, Buffer, HeyOrca, Later.
Validator/PM: deepeval, galtea.ai, langfuse, AutoGen-vs-CrewAI, emergentmind (critique-agent), Planable, CoSchedule.
Copywriter/Designer: Zeely, SocialPilot, Planable (hashtags), SaaSFunnelLab (AIDA/PAS), LetsEnhance, Imagine.art, RenderForm, Pollinations GitHub, Canva.
