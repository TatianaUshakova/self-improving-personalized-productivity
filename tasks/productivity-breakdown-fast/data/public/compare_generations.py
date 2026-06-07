#!/usr/bin/env python3
"""
Generate per-generation label comparison reports for productivity-breakdown runs.

Usage:
    python compare_generations.py --run-dir runs/run_8
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluate import (
    TRUTH_PATH,
    evaluate_submission,
    find_submission_file,
    load_json,
)


def load_or_compute_results(gen_dir: Path) -> dict[str, Any]:
    results_path = gen_dir / "results.json"
    if results_path.is_file():
        return load_json(results_path)

    submission_path = find_submission_file(gen_dir)
    if not submission_path:
        raise FileNotFoundError(f"No submission found for {gen_dir}")

    truth = load_json(TRUTH_PATH)
    submission = load_json(submission_path)
    results = evaluate_submission(submission, truth)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    return results


def render_generation_report(gen_name: str, results: dict[str, Any]) -> str:
    lines = [
        f"# {gen_name}",
        "",
        f"- Judge mode: `{results['judge_mode']}`",
        f"- Overall score: `{results['overall_score']:.4f}`",
        f"- Average slot score: `{results['average_slot_score']:.4f}`",
        f"- Coverage: `{results['coverage']:.4f}`",
        f"- Missing slots: `{results['missing_slots']}`",
        "",
        "| Start | End | Score | Gold | Predicted | Reason |",
        "|---|---:|---:|---|---|---|",
    ]

    for detail in results.get("details", []):
        reason = str(detail.get("reason", "")).replace("\n", " ").replace("|", "/")
        gold = str(detail.get("gold_label", "")).replace("\n", " ").replace("|", "/")
        predicted = str(detail.get("predicted_label", "")).replace("\n", " ").replace("|", "/")
        lines.append(
            f"| {detail.get('start', '')} | {detail.get('end', '')} | "
            f"{detail.get('score', 0.0):.4f} | {gold} | {predicted} | {reason} |"
        )

    return "\n".join(lines) + "\n"


def render_run_summary(run_name: str, generation_summaries: list[dict[str, Any]]) -> str:
    lines = [
        f"# {run_name} Comparison Summary",
        "",
        "| Generation | Overall | Avg slot | Coverage | Missing slots | Judge mode |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in generation_summaries:
        lines.append(
            f"| {item['generation']} | {item['overall_score']:.4f} | {item['average_slot_score']:.4f} | "
            f"{item['coverage']:.4f} | {item['missing_slots']} | {item['judge_mode']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True, help="Path to runs/run_X")
    args = parser.parse_args()

    run_dir = args.run_dir
    if not run_dir.is_dir():
        raise SystemExit(f"Run directory not found: {run_dir}")

    compare_dir = run_dir / "comparisons"
    compare_dir.mkdir(parents=True, exist_ok=True)

    generation_summaries = []
    gen_dirs = sorted(run_dir.glob("gen_*"))
    if not gen_dirs:
        raise SystemExit(f"No gen_* directories found in {run_dir}")

    for gen_dir in gen_dirs:
        try:
            results = load_or_compute_results(gen_dir)
        except FileNotFoundError:
            continue

        report_path = compare_dir / f"{gen_dir.name}_label_comparison.md"
        report_path.write_text(
            render_generation_report(gen_dir.name, results),
            encoding="utf-8",
        )

        generation_summaries.append(
            {
                "generation": gen_dir.name,
                "overall_score": float(results.get("overall_score", 0.0)),
                "average_slot_score": float(results.get("average_slot_score", 0.0)),
                "coverage": float(results.get("coverage", 0.0)),
                "missing_slots": int(results.get("missing_slots", 0)),
                "judge_mode": str(results.get("judge_mode", "")),
            }
        )

    summary_path = compare_dir / "summary.md"
    summary_path.write_text(
        render_run_summary(run_dir.name, generation_summaries),
        encoding="utf-8",
    )

    print(f"Saved comparison reports to {compare_dir}")


if __name__ == "__main__":
    main()
