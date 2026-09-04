"""
Isolated campaign runner (invoked as a subprocess by the dashboard).

Running the CrewAI pipeline in its own process protects the long-lived
Streamlit server from native-library crashes (onnxruntime etc. can segfault
inside Streamlit). Reads a brief, runs the strategy phase, and writes a JSON
result + live progress to files so the dashboard can poll them.

Usage:
    python -m src.run_campaign --brief-file <path> --out-file <path> \
        --progress-file <path>
"""
import argparse
import json

from src.pipeline import run_account_manager, run_validated_strategy
from src.project_manager import slice_into_weeks


def _write(path: str, obj) -> None:
    with open(path, "w") as f:
        json.dump(obj, f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief-file", required=True)
    ap.add_argument("--out-file", required=True)
    ap.add_argument("--progress-file", required=True)
    args = ap.parse_args()

    with open(args.brief_file) as f:
        brief = f.read()

    _write(args.progress_file, {"stage": "account_manager", "message": "Structuring the brief…"})
    dossier = run_account_manager(brief)

    result = {"dossier": dossier.model_dump(mode="json"),
              "strategy": None, "validation": None, "weeks": None}

    if dossier.insufficient_context:
        _write(args.progress_file, {"stage": "halted", "message": "Insufficient context"})
        _write(args.out_file, result)
        return

    # Agents 2 + 3: strategist with adversarial validation loop.
    _write(args.progress_file, {"stage": "strategist", "message": "Researching, planning & validating…"})
    strategy, verdict = run_validated_strategy(dossier)
    result["strategy"] = strategy.model_dump(mode="json") if strategy else None
    result["validation"] = verdict.model_dump(mode="json") if verdict else None

    # Agent 4: project manager slices the month into weeks.
    if strategy:
        _write(args.progress_file, {"stage": "project_manager", "message": "Slicing weekly plan…"})
        weeks = slice_into_weeks(strategy)
        result["weeks"] = [w.model_dump(mode="json") for w in weeks]

    _write(args.progress_file, {"stage": "done", "message": "Done"})
    _write(args.out_file, result)


if __name__ == "__main__":
    main()
