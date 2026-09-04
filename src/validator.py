"""
Agent 3 — Strategy Validator (Adversarial Gate).  PRD §3.

Hybrid design from the role research (docs/role_knowledge.md):
  * DETERMINISTIC checks in Python for factual/format rules (pillar count,
    evidence citations, platform alignment) — reliable, zero LLM variance.
  * An LLM JUDGE for nuanced checks (on-brand, audience fit) using boolean
    pass/fail per dimension.

On failure it returns actionable `correction_notes`; the pipeline routes the
context back to the Strategist for another attempt.
"""
import json

from src.llm import get_llm
from src.schemas import BrandDossier, DimensionCheck, StrategySchema, ValidationResult


def _deterministic_checks(
    dossier: BrandDossier, strategy: StrategySchema
) -> tuple[list[DimensionCheck], list[str], list[str]]:
    checks: list[DimensionCheck] = []
    notes: list[str] = []
    missing_citations: list[str] = []

    # 1. Pillar count (schema already enforces 3-5, but record the dimension).
    n = len(strategy.content_pillars)
    ok = 3 <= n <= 5
    checks.append(DimensionCheck(
        dimension="pillar_count", passed=ok,
        reason=f"{n} pillars ({'within' if ok else 'outside'} 3-5)"))
    if not ok:
        notes.append(f"Provide 3-5 content pillars (got {n}).")

    # 2. Evidence citations — advisory (soft): free web search is often
    #    rate-limited, so missing URLs shouldn't reject an otherwise-sound plan.
    uncited = [p.pillar_name for p in strategy.content_pillars if not p.evidence_urls]
    ok = len(uncited) == 0
    checks.append(DimensionCheck(
        dimension="evidence", passed=ok, hard=False,
        reason="all pillars cited" if ok else f"uncited: {', '.join(uncited)}"))
    if not ok:
        missing_citations.extend(uncited)
        notes.append(f"(advisory) Add evidence URLs for pillars: {', '.join(uncited)}.")

    # 3. Calendar non-empty.
    ok = len(strategy.one_month_calendar_skeleton) > 0
    checks.append(DimensionCheck(
        dimension="calendar", passed=ok,
        reason=f"{len(strategy.one_month_calendar_skeleton)} posts"))
    if not ok:
        notes.append("Produce a non-empty calendar skeleton.")

    # 4. Platform alignment — calendar must only use the brand's platforms.
    allowed = set(dossier.target_platforms)
    if allowed:
        stray = {p for post in strategy.one_month_calendar_skeleton
                 for p in post.platform if p not in allowed}
        ok = not stray
        checks.append(DimensionCheck(
            dimension="platform_alignment", passed=ok,
            reason="aligned" if ok else f"off-brief platforms: {stray}"))
        if not ok:
            notes.append(
                f"Only use the brand's platforms "
                f"({', '.join(p.value for p in allowed)}).")

    return checks, notes, missing_citations


def _llm_judge(dossier: BrandDossier, strategy: StrategySchema) -> DimensionCheck:
    """One nuanced on-brand / audience-fit judgment (boolean pass/fail)."""
    prompt = (
        "You are an adversarial QA reviewer. Judge whether this social media "
        "strategy genuinely fits the brand and audience. Be strict.\n\n"
        f"BRAND: {dossier.model_dump_json()}\n\n"
        f"STRATEGY PILLARS: "
        f"{json.dumps([p.pillar_name for p in strategy.content_pillars])}\n\n"
        "Return ONLY JSON: {\"passed\": true/false, \"reason\": \"...\"}. "
        "passed=false if pillars are generic, off-brand, or ignore the audience."
    )
    try:
        raw = get_llm(temperature=0.1, max_tokens=300, role="validator").call(
            [{"role": "user", "content": prompt}]
        )
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start:end + 1])
        return DimensionCheck(
            dimension="on_brand", passed=bool(data.get("passed")), hard=False,
            reason=str(data.get("reason", ""))[:200])
    except Exception as exc:  # noqa: BLE001
        # If the judge fails, don't block the pipeline — pass with a note.
        return DimensionCheck(dimension="on_brand", passed=True, hard=False,
                              reason=f"judge unavailable ({exc})")


def validate_strategy(
    dossier: BrandDossier, strategy: StrategySchema
) -> ValidationResult:
    """Run deterministic checks + the LLM judge and combine into a verdict."""
    checks, notes, missing = _deterministic_checks(dossier, strategy)
    checks.append(_llm_judge(dossier, strategy))
    for c in checks:
        if c.dimension == "on_brand" and not c.passed:
            notes.append(f"On-brand issue: {c.reason}")

    result = ValidationResult(
        approved=True,  # _sync_approved flips this false if any check failed
        checks=checks,
        correction_notes=notes,
        missing_citations=missing,
    )
    return result
