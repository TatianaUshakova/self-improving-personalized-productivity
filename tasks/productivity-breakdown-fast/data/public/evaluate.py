#!/usr/bin/env python3
"""
Evaluate productivity-breakdown submissions against hidden slot-level labels.

The primary unit of evaluation is the 15-minute slot. When an API key is
available, the evaluator uses an LLM judge to score semantic similarity between
the predicted and gold labels for each aligned slot. If no judge is configured,
the evaluator falls back to lexical similarity so the task remains runnable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - handled at runtime
    OpenAI = None

TASK_DIR = Path(__file__).parent.parent.parent
TRUTH_PATH = TASK_DIR / "data/private/2026-06-05_labels.json"
NEBIUS_BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/"
DEFAULT_NEBIUS_MODEL = "moonshotai/Kimi-K2.6"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_submission_file(gen_dir: Path) -> Path | None:
    candidates = [
        gen_dir / "results" / "submission.json",
        gen_dir / "submission.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    results_dir = gen_dir / "results"
    if results_dir.is_dir():
        json_files = sorted(results_dir.glob("submission_*.json"))
        if json_files:
            return max(json_files, key=lambda p: p.stat().st_mtime)
    return None


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def lexical_similarity(a: str, b: str) -> float:
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if not a_norm and not b_norm:
        return 1.0
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def build_slot_map(slots: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    slot_map: dict[tuple[str, str], str] = {}
    for slot in slots:
        start = str(slot.get("start", "")).strip()
        end = str(slot.get("end", "")).strip()
        label = str(slot.get("label", "")).strip()
        if start and end:
            slot_map[(start, end)] = label
    return slot_map


def make_judge_client() -> tuple[Any | None, str | None, str]:
    if OpenAI is None:
        return None, None, "lexical_fallback"

    if os.getenv("NEBIUS_API_KEY"):
        client = OpenAI(api_key=os.getenv("NEBIUS_API_KEY"), base_url=NEBIUS_BASE_URL)
        model = os.getenv("PRODUCTIVITY_EVAL_MODEL", DEFAULT_NEBIUS_MODEL)
        return client, model, "llm_nebius"

    if os.getenv("OPENAI_API_KEY"):
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("PRODUCTIVITY_EVAL_MODEL", DEFAULT_OPENAI_MODEL)
        return client, model, "llm_openai"

    return None, None, "lexical_fallback"


def parse_json_object(raw_text: str) -> dict[str, Any]:
    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.startswith("json"):
            raw_text = raw_text[4:].strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and start < end:
            return json.loads(raw_text[start : end + 1])
        raise


def judge_batch(
    client: Any,
    model: str,
    slot_pairs: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    if not slot_pairs:
        return {}

    prompt = {
        "task": "Score semantic agreement between predicted and gold activity labels for aligned 15-minute slots.",
        "rubric": {
            "1.0": "Same underlying activity with comparable specificity.",
            "0.7": "Mostly the same activity but predicted label is less specific or misses a minor detail.",
            "0.4": "Partially related, but meaningfully incomplete or somewhat incorrect.",
            "0.0": "Different activity or no meaningful semantic match.",
        },
        "instructions": [
            "Judge the meaning of the activity, not exact wording.",
            "Do not reward labels that are much more generic than the gold label unless they still capture the main activity.",
            "Return JSON only.",
        ],
        "pairs": slot_pairs,
        "required_output_schema": {
            "judgments": [
                {
                    "start": "HH:MM",
                    "end": "HH:MM",
                    "score": 0.0,
                    "reason": "short explanation",
                }
            ]
        },
    }

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a careful evaluator of semantic similarity between activity labels. Return valid JSON only.",
            },
            {
                "role": "user",
                "content": json.dumps(prompt, ensure_ascii=False, indent=2),
            },
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw_text = (response.choices[0].message.content or "").strip()
    parsed = parse_json_object(raw_text)
    judgments = parsed.get("judgments", [])

    result: dict[tuple[str, str], dict[str, Any]] = {}
    for judgment in judgments:
        start = str(judgment.get("start", "")).strip()
        end = str(judgment.get("end", "")).strip()
        if not start or not end:
            continue
        try:
            score = float(judgment.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        result[(start, end)] = {
            "llm_score": max(0.0, min(1.0, score)),
            "llm_reason": str(judgment.get("reason", "")).strip(),
        }
    return result


def evaluate_submission(submission: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    truth_slots = truth.get("slots_15m", [])
    pred_slots = submission.get("slots_15m", [])

    truth_map = build_slot_map(truth_slots)
    pred_map = build_slot_map(pred_slots)
    all_keys = sorted(truth_map.keys())

    client, model, judge_mode = make_judge_client()
    slot_pairs = []
    for start, end in all_keys:
        slot_pairs.append(
            {
                "start": start,
                "end": end,
                "gold_label": truth_map[(start, end)],
                "predicted_label": pred_map.get((start, end), ""),
            }
        )

    llm_scores: dict[tuple[str, str], dict[str, Any]] = {}
    if client is not None and model is not None:
        try:
            batch_size = 20
            for i in range(0, len(slot_pairs), batch_size):
                llm_scores.update(judge_batch(client, model, slot_pairs[i : i + batch_size]))
        except Exception:
            judge_mode = "lexical_fallback"
            llm_scores = {}

    details = []
    final_scores = []
    lexical_scores = []
    missing_slots = 0

    for start, end in all_keys:
        gold_label = truth_map[(start, end)]
        predicted_label = pred_map.get((start, end), "")
        lexical = lexical_similarity(gold_label, predicted_label)
        lexical_scores.append(lexical)

        llm_meta = llm_scores.get((start, end), {})
        if judge_mode.startswith("llm") and llm_meta:
            score = llm_meta.get("llm_score", lexical)
        else:
            score = lexical

        if not predicted_label:
            missing_slots += 1
            score = 0.0

        final_scores.append(score)
        details.append(
            {
                "start": start,
                "end": end,
                "gold_label": gold_label,
                "predicted_label": predicted_label,
                "lexical_score": round(lexical, 4),
                "score": round(score, 4),
                "reason": llm_meta.get("llm_reason", ""),
                "missing_prediction": not bool(predicted_label),
            }
        )

    total_slots = len(all_keys)
    coverage = 0.0 if total_slots == 0 else (total_slots - missing_slots) / total_slots
    average_score = 0.0 if not final_scores else sum(final_scores) / len(final_scores)
    average_lexical = 0.0 if not lexical_scores else sum(lexical_scores) / len(lexical_scores)
    overall_score = average_score * coverage

    return {
        "date": truth.get("date_text", submission.get("date", "")),
        "timestamp": datetime.now().isoformat(),
        "judge_mode": judge_mode,
        "judge_model": model,
        "num_gold_slots": total_slots,
        "num_predicted_slots": len(pred_map),
        "missing_slots": missing_slots,
        "coverage": round(coverage, 4),
        "average_slot_score": round(average_score, 4),
        "average_lexical_score": round(average_lexical, 4),
        "overall_score": round(overall_score, 4),
        "details": details,
    }


def save_results(results: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def print_summary(results: dict[str, Any]) -> None:
    print("\n" + "=" * 70)
    print("Productivity Breakdown Evaluation Results")
    print("=" * 70)
    print(f"Judge mode:          {results['judge_mode']}")
    if results.get("judge_model"):
        print(f"Judge model:         {results['judge_model']}")
    print(f"Gold slots:          {results['num_gold_slots']}")
    print(f"Predicted slots:     {results['num_predicted_slots']}")
    print(f"Missing slots:       {results['missing_slots']}")
    print(f"Coverage:            {100 * results['coverage']:.1f}%")
    print(f"Average slot score:  {results['average_slot_score']:.4f}")
    print(f"Average lexical:     {results['average_lexical_score']:.4f}")
    print(f"Overall score:       {results['overall_score']:.4f}")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission", type=Path, help="Path to submission JSON")
    parser.add_argument("--gen-dir", type=Path, help="Generation directory containing results/submission.json")
    args = parser.parse_args()

    if args.submission:
        submission_path = args.submission
    elif args.gen_dir:
        submission_path = find_submission_file(args.gen_dir)
        if not submission_path:
            raise SystemExit(f"No submission JSON found in {args.gen_dir}")
    else:
        parser.print_help()
        raise SystemExit(1)

    truth = load_json(TRUTH_PATH)
    submission = load_json(submission_path)
    results = evaluate_submission(submission, truth)

    if args.gen_dir:
        save_results(results, args.gen_dir / "results.json")
    print_summary(results)


if __name__ == "__main__":
    main()
