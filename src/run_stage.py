"""
Isolated single-stage runner (invoked as a subprocess by the dashboard).

The dashboard is a human-gated wizard: each agent runs alone, the human reviews
its output, and only then is the next stage allowed. This runner executes ONE
stage per invocation so the UI can stop between agents.

Stages:
  dossier  — Account Manager: {"brief": str} -> {"dossier": {...}}
  strategy — Strategist + Validator verdict:
             {"dossier": {...}, "feedback": [str]} ->
             {"strategy": {...}|null, "validation": {...}|null}

(The Project Manager stage is pure Python and runs inline in the dashboard;
post generation has its own runner, src/generate_posts.py.)

Usage:
    python -m src.run_stage --stage dossier --in-file in.json --out-file out.json
"""
import argparse
import json


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["dossier", "strategy"])
    ap.add_argument("--in-file", required=True)
    ap.add_argument("--out-file", required=True)
    args = ap.parse_args()

    with open(args.in_file) as f:
        data = json.load(f)

    if args.stage == "dossier":
        from src.pipeline import run_account_manager

        dossier = run_account_manager(data["brief"])
        out = {"dossier": dossier.model_dump(mode="json")}

    else:  # strategy
        from src.pipeline import run_strategist
        from src.schemas import BrandDossier
        from src.validator import validate_strategy

        dossier = BrandDossier.model_validate(data["dossier"])
        feedback = data.get("feedback") or []
        # Human is the retry loop now: one strategist attempt + one verdict,
        # then the reviewer decides to approve or re-run with feedback.
        strategy = run_strategist(dossier, corrections=feedback)
        out = {
            "strategy": strategy.model_dump(mode="json") if strategy else None,
            "validation": (
                validate_strategy(dossier, strategy).model_dump(mode="json")
                if strategy else None
            ),
        }

    with open(args.out_file, "w") as f:
        json.dump(out, f)


if __name__ == "__main__":
    main()
