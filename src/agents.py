"""
Agent + Task definitions.

Built so far:
    Agent 1 — Account Manager   (raw brief   -> BrandDossier)
    Agent 2 — Strategist        (BrandDossier -> StrategySchema)

Prompts encode the researched best-practice rules (docs/role_knowledge.md).
Each Task uses `output_pydantic` so CrewAI forces the agent to return a
schema-valid object — the anti-hallucination "schema gating" from the PRD.
"""
from crewai import Agent, Task

from src.llm import get_llm
from src.schemas import BrandDossier, StrategySchema
from src.tools import WebSearchTool


# --------------------------------------------------------------------------- #
#  Agent 1 — Account Manager
# --------------------------------------------------------------------------- #
def build_account_manager() -> Agent:
    return Agent(
        role="Account Manager",
        goal=(
            "Convert a raw, unstructured client brief into a complete, "
            "standardized BrandDossier. Never invent facts."
        ),
        backstory=(
            "You are a meticulous agency account manager. A complete brand "
            "dossier needs visual identity, verbal identity (voice), "
            "positioning/values, and measurable KPIs. In real briefs, KPIs and "
            "success metrics are the most commonly missing piece, so you watch "
            "for them specifically. If essential fields (client_name, industry, "
            "target_audience, brand_voice, or any KPI/goal) cannot be derived "
            "from the brief, you DO NOT guess — you set insufficient_context=True "
            "and list exactly what is missing in missing_fields."
        ),
        llm=get_llm(temperature=0.2, role="account_manager"),
        verbose=True,
    )


def account_manager_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Parse this raw client brief into a BrandDossier:\n\n"
            "----- BRIEF -----\n{raw_brief}\n-----------------\n\n"
            "Extract every field you can. Do not fabricate.\n"
            "Rules for the guardrail:\n"
            "- 'goals' and 'kpis' overlap — a measurable goal like 'grow IG "
            "followers 20%' can go in EITHER list. As long as goals OR kpis has "
            "at least one entry, that requirement is satisfied.\n"
            "- Only set insufficient_context=true if one of client_name, "
            "industry, target_audience, or brand_voice cannot be determined, OR "
            "if BOTH goals and kpis are empty.\n"
            "- Put platform names in lowercase (instagram, linkedin, ...).\n"
            "List any genuinely missing required fields in missing_fields."
        ),
        expected_output="A BrandDossier object matching the schema.",
        agent=agent,
        output_pydantic=BrandDossier,
    )


# --------------------------------------------------------------------------- #
#  Agent 2 — Strategist
# --------------------------------------------------------------------------- #
def build_strategist() -> Agent:
    return Agent(
        role="Social Media Strategist",
        goal=(
            "Research competitors, discover trends, and produce a StrategySchema "
            "with 3-5 evidence-backed content pillars and a one-month calendar."
        ),
        backstory=(
            "You are a senior social strategist. You follow a strict method:\n"
            "1) Competitor analysis in 4 steps: identify 3-5 competitors, review "
            "their activity, run a SWOT, and note what to exploit.\n"
            "2) Define 3-5 content pillars — never fewer than 3, never more than "
            "5. Each pillar MUST cite real evidence URLs from your web searches "
            "(no citation = not allowed).\n"
            "3) Apply the 70/20/10 content mix (planned / reactive / experimental).\n"
            "4) Build a one-month calendar skeleton spread across the brand's "
            "platforms using realistic cadence (IG 3-5/wk, LinkedIn 2-3/wk, etc.).\n"
            "Every claim traces back to a URL you actually retrieved."
        ),
        tools=[WebSearchTool()],
        llm=get_llm(temperature=0.4, role="strategist"),
        max_iter=6,  # cap ReAct loops so a slow local model can't spiral
        verbose=True,
    )


def strategist_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Build the monthly social strategy for this brand dossier:\n\n"
            "----- BRAND DOSSIER (JSON) -----\n{brand_dossier}\n"
            "--------------------------------\n\n"
            "{corrections}"
            "Be concise — keep total output compact.\n\n"
            "Steps:\n"
            "1. Run AT MOST 2 web_search queries total: one for competitors, one "
            "for market trends. Record real competitor URLs in "
            "competitor_urls_scanned and trends in market_trends_discovered.\n"
            "2. Define EXACTLY 3-4 content_pillars. Each needs a short "
            "justification and at least one real evidence_url from your searches "
            "(if search was rate-limited and returned no URLs, leave evidence_urls "
            "empty — never invent URLs).\n"
            "3. Produce a LIGHT one_month_calendar_skeleton of only 8 posts "
            "(about 2 per week), spread across the brand's platforms. Keep each "
            "angle_and_objective to one short sentence.\n\n"
            "Do not invent URLs.\n\n"
            "OUTPUT FORMAT: return ONLY a single valid JSON object (no prose, no "
            "markdown fences) with exactly these keys:\n"
            "  client_name (str),\n"
            "  competitor_urls_scanned (list of url strings),\n"
            "  market_trends_discovered (list of strings),\n"
            "  content_pillars (list of {{pillar_name, justification, "
            "evidence_urls:[url strings]}}),\n"
            "  one_month_calendar_skeleton (list of {{date:'YYYY-MM-DD', "
            "platform:[strings], pillar, angle_and_objective}}).\n"
            "Platforms must be lowercase from: instagram, linkedin, twitter, "
            "facebook, tiktok."
        ),
        expected_output="A single JSON object with the strategy keys, nothing else.",
        agent=agent,
        # NOTE: no output_pydantic — we parse + validate in Python to avoid an
        # extra (token-expensive) CrewAI conversion call.
    )
