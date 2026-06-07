#!/usr/bin/env python3
"""
Reference target agent for personalized daily activity reconstruction.

This prototype:
1. Loads one or more public day JSON files from --dataset_dir
2. Builds 15-minute slot evidence from Chrome, location, calls, and todos
3. Prompts moonshotai/Kimi-K2.6 via Nebius to reconstruct the day
4. Saves submission.json and a richer timestamped result JSON
5. Logs a single execution trajectory to agent_execution.json
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

MODEL_NAME = "moonshotai/Kimi-K2.6"
NEBIUS_BASE_URL = "https://api.tokenfactory.us-central1.nebius.com/v1/"
MAX_TOKENS = 2500


def setup_client() -> OpenAI:
    api_key = os.getenv("NEBIUS_API_KEY")
    if not api_key:
        raise SystemExit("Set NEBIUS_API_KEY environment variable.")
    return OpenAI(api_key=api_key, base_url=NEBIUS_BASE_URL)


def load_day_files(dataset_dir: Path) -> list[dict[str, Any]]:
    day_files = sorted(dataset_dir.glob("day_*_public.json"))
    if not day_files:
        raise SystemExit(f"No day_*_public.json files found in {dataset_dir}")
    return [json.loads(path.read_text(encoding="utf-8")) for path in day_files]


def hhmm_to_minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def minutes_to_hhmm(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def overlaps(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    return start_a < end_b and start_b < end_a


def clip_text(text: str, limit: int = 120) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def summarize_event(event: dict[str, Any], preferred_keys: list[str]) -> str:
    parts = []
    for key in preferred_keys:
        value = event.get(key)
        if value:
            parts.append(str(value))
    return clip_text(" | ".join(parts), 140)


def build_slot_index(day: dict[str, Any]) -> list[dict[str, Any]]:
    work_started_at = day.get("user_context", {}).get("work_started_at", "09:00")
    start_minute = hhmm_to_minutes(work_started_at)
    end_minute = 24 * 60

    slots = []
    for slot_start in range(start_minute, end_minute, 15):
        slot_end = min(slot_start + 15, end_minute)
        slots.append(
            {
                "start": minutes_to_hhmm(slot_start),
                "end": minutes_to_hhmm(slot_end),
                "call_evidence": [],
                "location_evidence": [],
                "chrome_session_evidence": [],
                "chrome_raw_event_count": 0,
            }
        )

    def attach_time_bounded(
        events: list[dict[str, Any]], target_key: str, preferred_keys: list[str]
    ) -> None:
        for event in events:
            try:
                event_start = hhmm_to_minutes(event["start"])
                event_end = hhmm_to_minutes(event["end"])
            except Exception:
                continue
            summarized = summarize_event(event, preferred_keys)
            for slot in slots:
                slot_start = hhmm_to_minutes(slot["start"])
                slot_end = hhmm_to_minutes(slot["end"])
                if overlaps(slot_start, slot_end, event_start, event_end):
                    slot[target_key].append(summarized)

    attach_time_bounded(
        day.get("call_activity", {}).get("events_rounded_15m", []),
        "call_evidence",
        ["description", "contact"],
    )
    attach_time_bounded(
        day.get("location_activity", {}).get("events_rounded_15m", []),
        "location_evidence",
        ["description", "type"],
    )
    attach_time_bounded(
        day.get("chrome_activity", {}).get("merged_sessions", []),
        "chrome_session_evidence",
        ["session_label_hint", "primary_domain", "titles_preview"],
    )

    for event in day.get("chrome_activity", {}).get("raw_events_normalized", []):
        try:
            event_start = hhmm_to_minutes(event["start"])
            event_end = hhmm_to_minutes(event["end"])
        except Exception:
            continue
        effective_end = max(event_start + 1, event_end)
        for slot in slots:
            slot_start = hhmm_to_minutes(slot["start"])
            slot_end = hhmm_to_minutes(slot["end"])
            if overlaps(slot_start, slot_end, event_start, effective_end):
                slot["chrome_raw_event_count"] += 1

    return slots


def build_prompt_for_day(day: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    slots = build_slot_index(day)
    heuristics = day.get("user_context", {}).get("heuristics", [])
    todos = [item["text"] for item in day.get("user_context", {}).get("todo_items", [])]
    chrome_summary = day.get("chrome_activity", {}).get("summary", {})

    compact_slots = []
    for slot in slots:
        compact_slot = {
            "start": slot["start"],
            "end": slot["end"],
            "chrome_raw_event_count": slot["chrome_raw_event_count"],
        }
        if slot["call_evidence"]:
            compact_slot["call_evidence"] = slot["call_evidence"][:2]
        if slot["location_evidence"]:
            compact_slot["location_evidence"] = slot["location_evidence"][:2]
        if slot["chrome_session_evidence"]:
            compact_slot["chrome_session_evidence"] = slot["chrome_session_evidence"][:2]
        compact_slots.append(compact_slot)

    prompt = {
        "task": (
            "Reconstruct the user's day as detailed 15-minute activity labels. "
            "Preserve specific activity meaning. Avoid broad generic categories when more detail is justified."
        ),
        "date": day.get("date"),
        "day_label": day.get("day_label"),
        "work_started_at": day.get("user_context", {}).get("work_started_at"),
        "todo_items": todos,
        "heuristics": heuristics,
        "chrome_summary": {
            "raw_event_count": chrome_summary.get("raw_event_count"),
            "merged_session_count": chrome_summary.get("merged_session_count"),
            "top_domains": chrome_summary.get("top_domains", [])[:8],
        },
        "slot_evidence": compact_slots,
        "required_output_schema": {
            "date": "YYYY-MM-DD",
            "slots_15m": [{"start": "HH:MM", "end": "HH:MM", "label": "detailed freeform description"}],
            "segments": [{"start": "HH:MM", "end": "HH:MM", "label": "detailed freeform description"}],
        },
        "instructions": [
            "Use cross-signal evidence across browsing, location, calls, todos, and heuristics.",
            "Heuristics are weak hints, not labels to copy blindly.",
            "Work from the compact slot evidence and day summary. Do not expand every raw browsing event unless absolutely necessary.",
            "If evidence is ambiguous, still make your best specific guess rather than using broad labels.",
            "Return JSON only.",
        ],
    }
    return json.dumps(prompt, indent=2, ensure_ascii=False), slots


def normalize_slots(slots: list[dict[str, Any]]) -> list[dict[str, str]]:
    normalized = []
    for slot in slots:
        start = str(slot.get("start", "")).strip()
        end = str(slot.get("end", "")).strip()
        label = str(slot.get("label", "")).strip()
        if start and end and label:
            normalized.append({"start": start, "end": end, "label": label})
    return normalized


def build_segments_from_slots(slots: list[dict[str, str]]) -> list[dict[str, str]]:
    if not slots:
        return []
    segments = [slots[0].copy()]
    for slot in slots[1:]:
        last = segments[-1]
        if slot["label"] == last["label"] and slot["start"] == last["end"]:
            last["end"] = slot["end"]
        else:
            segments.append(slot.copy())
    return segments


def parse_response_json(raw_text: str) -> dict[str, Any]:
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


def save_execution_log(path: Path, payload: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def run_one_day(client: OpenAI, day: dict[str, Any], working_dir: Path) -> dict[str, Any]:
    user_prompt, slot_evidence = build_prompt_for_day(day)
    system_prompt = (
        "You reconstruct a user's day from noisy personal telemetry. "
        "You must output detailed, specific activity labels in valid JSON."
    )

    trajectory: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=MAX_TOKENS,
        response_format={"type": "json_object"},
    )

    raw_text = (response.choices[0].message.content or "").strip()
    trajectory.append(
        {
            "role": "assistant",
            "content": raw_text,
            "_meta": {
                "date": day.get("date"),
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
                "completion_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
            },
        }
    )

    parsed = parse_response_json(raw_text)
    predicted_slots = normalize_slots(parsed.get("slots_15m", []))
    if not predicted_slots:
        raise ValueError("Model response did not contain valid slots_15m output.")

    predicted_segments = normalize_slots(parsed.get("segments", []))
    if not predicted_segments:
        predicted_segments = build_segments_from_slots(predicted_slots)

    result = {
        "date": day.get("date"),
        "slots_15m": predicted_slots,
        "segments": predicted_segments,
        "slot_count": len(predicted_slots),
        "source_summary": {
            "slot_evidence_count": len(slot_evidence),
            "todo_count": len(day.get("user_context", {}).get("todo_items", [])),
        },
        "total_input_tokens": getattr(response.usage, "prompt_tokens", 0) if response.usage else 0,
        "total_output_tokens": getattr(response.usage, "completion_tokens", 0) if response.usage else 0,
        "total_reasoning_tokens": 0,
        "total_cost_usd": 0.0,
        "timestamp": datetime.now().isoformat(),
    }

    save_execution_log(working_dir / "agent_execution.json", trajectory)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Personalized productivity breakdown reference agent")
    parser.add_argument("--dataset_dir", type=Path, required=True, help="Path to the READ-ONLY dataset directory")
    parser.add_argument("--working_dir", type=Path, required=True, help="Path to the READ-WRITE working directory")
    args = parser.parse_args()

    dataset_dir = args.dataset_dir
    working_dir = args.working_dir
    working_dir.mkdir(parents=True, exist_ok=True)
    results_dir = working_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    day_files = load_day_files(dataset_dir)
    client = setup_client()

    if len(day_files) != 1:
        raise SystemExit("This reference agent currently expects exactly one day_*_public.json file.")

    result = run_one_day(client, day_files[0], working_dir)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_dir / f"submission_{result['date']}_{timestamp}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    with open(results_dir / "submission.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(
        f"saved {output_file} | "
        f"prompt_tokens={result['total_input_tokens']} | "
        f"completion_tokens={result['total_output_tokens']}"
    )


if __name__ == "__main__":
    main()
