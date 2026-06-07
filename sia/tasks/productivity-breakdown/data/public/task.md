# Task: Personalized Daily Activity Reconstruction

Your goal is to reconstruct a **highly detailed, personalized daily time breakdown** from raw behavioral traces.

You are given day-level evidence such as:

- Chrome browsing history
- Google Maps / location activity
- call activity
- to-do items for the day

The desired output is a **detailed 15-minute reconstruction** of what the user was most likely doing throughout the day.

This is **not** a generic productivity categorization task. Do **not** collapse activities into broad classes like `work`, `personal`, `break`, `meeting`, etc. unless the evidence is extremely weak and no more specific description is justified.

Instead, your output should preserve rich descriptions such as:

- `went out to get matcha`
- `attended a community networking event`
- `company interview, followed by a short note about what was discussed`

## Core Challenge

The main challenge is not just reading the raw data. It is inferring the **user-specific interpretation rules** that connect raw signals to actual activity labels.

Examples:

- some websites may signal job search for this specific user
- some LLM chats may signal hackathon preparation
- some map activity may reflect actual movement, while other map usage may reflect trip planning
- repeated browser activity may need deduplication or session merging before it becomes useful

These user-specific heuristics should be **discovered by the evolving agent/harness**, not hardcoded as fixed ground truth labels from the task input.

## Input

You will receive one or more day-level public JSON files, for example:

- `day_2026-06-05_public.json`

The public dataset directory may also include supporting source artifacts under:

- `supporting_raw/`

These supporting files are agent-visible and may contain the lower-level raw or cleaned inputs used to assemble the day-level JSON, such as browser-history exports, call notes, location traces, and todo snapshots.
They are intended as optional fallback evidence, not the default primary input for every model call.

Each file may contain:

- `user_context`
- `call_activity`
- `location_activity`
- `chrome_activity`

The `user_context` may also contain **heuristics-like hints**. These are not ground truth labels and should not be copied mechanically into the answer. Instead, they are weak personalized clues about how this specific user's signals may need to be interpreted.

Examples of such heuristics:

- map usage may sometimes reflect trip planning rather than actual movement
- names of LLM chats may hint at the real intent behind activity

Treat these heuristics as part of the evidence available to the solver. The evolving harness may also discover additional user-specific heuristics from repeated patterns in the raw signals.

The Chrome history may include:

- raw normalized events
- merged browsing sessions
- noisy or duplicative entries
- redirect-like entries

Use the evidence jointly. Do not rely on a single modality if others provide clarification.
For efficiency, start from `day_*_public.json` and only inspect `supporting_raw/` selectively when the compact day-level evidence is insufficient for a specific ambiguity.

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
      "label": "called sister"
    },
    {
      "start": "12:30",
      "end": "12:45",
      "label": "called sister"
    },
    {
      "start": "12:45",
      "end": "13:00",
      "label": "played video games"
    }
  ],
  "segments": [
    {
      "start": "12:15",
      "end": "12:45",
      "label": "called sister"
    },
    {
      "start": "12:45",
      "end": "13:15",
      "label": "played video games"
    }
  ]
}
```

## Output Expectations

### 1. `slots_15m`

This is the **main required output**.

- cover the day using 15-minute intervals
- each slot should contain one detailed freeform label
- labels should be specific and personalized when supported by evidence

### 2. `segments`

This is a convenience view.

- merge adjacent 15-minute slots when the label is effectively the same
- segments should remain consistent with `slots_15m`

## Level of Detail

Aim for the level of detail shown in the ground-truth examples:

- preserve intent when possible
- preserve task identity when possible
- preserve transitions when possible

Prefer:

- `reading available docs and researched relevant GitHub repos for a budgeting app`

over:

- `worked on budgeting app`

and strongly prefer that over:

- `work`

## Important Constraints

1. Do not standardize labels into a fixed taxonomy unless the task explicitly requires it.
2. Do not output overly generic labels when a more specific label is justified by evidence.
3. Do not rely blindly on raw Chrome rows; deduplication and session-level reasoning may be needed.
4. Use user-specific patterns inferred from the data rather than generic assumptions.
5. When evidence is ambiguous, still provide your best slot-level reconstruction rather than falling back to broad generic labels.
6. Heuristics present in `user_context` are advisory clues, not labels. Use them to guide interpretation, not to replace reasoning from the raw evidence.
7. Keep the solving loop efficient: avoid copying entire raw support files into prompts when a compact summary or a few targeted details would suffice.

## Evaluation

Evaluation is based on comparison with a hidden gold breakdown.

Because the labels are detailed freeform descriptions rather than a fixed controlled vocabulary, evaluation may rely on:

- 15-minute slot alignment
- semantic similarity between predicted and gold labels
- an LLM judge that checks whether the predicted activity meaningfully matches the hidden ground truth at the same time ranges

Therefore:

- semantic faithfulness matters more than exact wording
- preserving the right activity meaning at the right time is the main objective

## Practical Goal

The system should gradually discover better ways to:

- clean noisy browsing data
- merge low-level events into meaningful sessions
- use cross-signal evidence across modalities
- infer personalized activity semantics
- produce a daily breakdown that is close to the hidden labeled reconstruction
