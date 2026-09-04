"""
Pipeline orchestration.

Built so far: the STRATEGY PHASE (Account Manager -> Strategist).
The adversarial validation gate (Agent 3) wraps this next.

Run a quick end-to-end test:
    docker compose run --rm --no-deps app python -m src.pipeline
"""
import json
import re

from crewai import Crew, Process

from src.agents import (
    account_manager_task,
    build_account_manager,
    build_strategist,
    strategist_task,
)
from src.schemas import BrandDossier, StrategySchema, ValidationResult


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _parse_json(raw: str, model):
    """Extract the first JSON object from an LLM's raw text and validate it
    against a Pydantic model. Tolerant of markdown fences, ANSI colour codes,
    surrounding prose, and trailing commas that small models emit."""
    text = _ANSI.sub("", raw).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    # Remove trailing commas before } or ] (common small-model JSON error).
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    # Python-style literals → JSON (models sometimes emit True/False/None).
    text = re.sub(r"\bTrue\b", "true", text)
    text = re.sub(r"\bFalse\b", "false", text)
    text = re.sub(r"\bNone\b", "null", text)
    return model.model_validate(json.loads(text))


from src.config import SAMPLE_BRIEF  # noqa: E402  (re-export for CLI use)


def run_account_manager(raw_brief: str) -> BrandDossier:
    """Agent 1: turn a raw brief into a validated BrandDossier."""
    last_error = ""
    for attempt in range(2):
        try:
            am = build_account_manager()
            am_task = account_manager_task(am)
            crew = Crew(agents=[am], tasks=[am_task],
                        process=Process.sequential, verbose=True)
            crew.kickoff(inputs={"raw_brief": raw_brief})
            dossier = am_task.output.pydantic
            if dossier is None:  # fallback: parse raw text ourselves
                dossier = _parse_json(am_task.output.raw, BrandDossier)
            return dossier
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            print(f"[WARN] Account Manager attempt {attempt + 1} failed: {exc}")

    print("[ERROR] Account Manager produced no valid dossier after retries.")
    # Report WHY rather than a bare sentinel. An unreachable LLM and a genuinely
    # thin brief both land here, and the UI can't tell them apart without this.
    reason = last_error[:300] or "the model returned nothing"
    return BrandDossier(
        client_name="", industry="", target_audience="", brand_voice="",
        insufficient_context=True,
        missing_fields=[f"agent could not run — {reason}"],
    )


def run_strategist(
    dossier: BrandDossier, corrections: list[str] | None = None
) -> StrategySchema | None:
    """Agent 2: research + build the strategy from a dossier. On a re-run,
    `corrections` from the validator are fed back in (the adversarial loop)."""
    correction_block = ""
    if corrections:
        correction_block = (
            "⚠️ Your previous attempt was REJECTED. Fix these issues:\n- "
            + "\n- ".join(corrections)
            + "\n\n"
        )

    # Retry until the model returns parseable, schema-valid JSON. Catch BOTH
    # CrewAI loop errors (empty response) and parse errors so one bad attempt
    # retries instead of crashing the whole run.
    last_raw = ""
    for attempt in range(3):
        try:
            strat = build_strategist()
            st_task = strategist_task(strat)
            crew = Crew(agents=[strat], tasks=[st_task],
                        process=Process.sequential, verbose=True)
            crew.kickoff(inputs={
                "brand_dossier": dossier.model_dump_json(),
                "corrections": correction_block,
            })
            last_raw = st_task.output.raw or ""
            return _parse_json(last_raw, StrategySchema)
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Strategist attempt {attempt + 1} failed: {exc}")

    print("----- last raw strategist output -----\n", last_raw[:1500])
    return None


def run_validated_strategy(
    dossier: BrandDossier, max_attempts: int = 2
) -> tuple[StrategySchema | None, ValidationResult | None]:
    """Agent 2 + Agent 3: build a strategy, then run the adversarial validator.
    On rejection, feed corrections back and retry (up to max_attempts)."""
    from src.validator import validate_strategy

    corrections: list[str] = []
    strategy = verdict = None
    for attempt in range(1, max_attempts + 1):
        strategy = run_strategist(dossier, corrections=corrections)
        if strategy is None:
            continue
        verdict = validate_strategy(dossier, strategy)
        print(f"\n[validator] attempt {attempt}: approved={verdict.approved}")
        if verdict.approved:
            break
        corrections = verdict.correction_notes
    return strategy, verdict


def run_strategy_phase(raw_brief: str) -> tuple[BrandDossier, StrategySchema | None]:
    """Run Account Manager then Strategist. If the AM halts (insufficient
    context), the Strategist is skipped and StrategySchema is None."""
    dossier = run_account_manager(raw_brief)
    if dossier.insufficient_context:
        print("\n[HALT] insufficient context:", dossier.missing_fields)
        return dossier, None
    return dossier, run_strategist(dossier)


if __name__ == "__main__":
    dossier, strategy = run_strategy_phase(SAMPLE_BRIEF)

    print("\n" + "=" * 55)
    print(" BRAND DOSSIER")
    print("=" * 55)
    print(dossier.model_dump_json(indent=2))

    if strategy is not None:
        print("\n" + "=" * 55)
        print(" STRATEGY")
        print("=" * 55)
        print(strategy.model_dump_json(indent=2))
