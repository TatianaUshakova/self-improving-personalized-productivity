# Task: Personalized Daily Activity Reconstruction (Fast Slice)

Your goal is to reconstruct a **highly detailed, personalized daily time breakdown** from raw behavioral traces.

This fast-turn variant is intentionally limited to a short early slice of the day so the self-improvement loop can run many generations cheaply.

## Time Window

Reconstruct only this window:

- `12:15` to `15:15`

The expected output is a detailed 15-minute reconstruction for that window only.

## Input

You will receive one public JSON file:

- `day_2026-06-05_public.json`

It includes:

- Chrome browsing history summaries and filtered raw events
- Google Maps / location activity
- call activity
- to-do items for the day
- lightweight heuristics that may help interpret this user's signals

The heuristics are weak clues, not labels to copy.

## Required Output

Write a JSON file named:

- `submission.json`

inside your working directory or a `results/` subdirectory.

The output JSON must have this structure:

```json
{
  "date": "2026-06-05",
  "slots_15m": [
    {
      "start": "12:15",
      "end": "12:30",
      "label": "called a family member"
    }
  ],
  "segments": [
    {
      "start": "12:15",
      "end": "12:45",
      "label": "called a family member"
    }
  ]
}
```

## Important Constraints

1. Reconstruct only the specified time window.
2. Do not collapse labels into broad categories like `work` or `personal` when more specific labels are justified.
3. Use cross-signal evidence across calls, browsing, location, todos, and heuristics.
4. Keep the solving loop efficient: work from the provided compact evidence rather than trying to expand every raw trace into the prompt.
5. If evidence is ambiguous, still make your best specific guess.

## Practical Goal

This task is designed for fast self-improvement iterations. The evolving harness should learn how to:

- clean noisy browsing traces
- fuse signals across modalities
- infer user-specific activity meaning
- produce a compact but semantically accurate slot-level reconstruction
