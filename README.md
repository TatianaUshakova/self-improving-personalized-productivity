# Self-Improving Personalized Productivity System

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

This repo is a self-improving personalized productivity system.

Its purpose is to turn messy personal activity traces into a useful, structured understanding of how time was actually spent, what the user was trying to do, and how that behavior can be interpreted more accurately over time.

The system works across multiple weak signals, including:

- browser history
- maps and movement traces
- call activity
- todo items
- lightweight user-specific heuristics

The important idea is not just timeline reconstruction. It is **personalized interpretation**.

The same website, map session, or communication event can mean very different things depending on the user, the surrounding context, and what happened before or after it. This system is designed to improve that interpretation loop over time by learning better ways to:

- clean noisy telemetry
- merge low-level events into meaningful sessions
- infer intent from cross-signal context
- preserve useful detail without collapsing everything into broad labels
- produce a more accurate picture of the user's real work and life patterns

This repo was adapted from the SIA framework and now centers on the bundled `productivity-breakdown` task under [sia/tasks/productivity-breakdown](/Users/tatianaushakova/sia/sia/tasks/productivity-breakdown).

## What This Repo Does

At a high level, the system runs three roles in a loop:

1. A meta agent reads the task and writes the initial target agent.
2. The target agent reconstructs the day from public evidence.
3. A feedback agent inspects the outputs and rewrites the target agent for the next generation.

Artifacts for each run land under `runs/run_{id}/gen_{n}/`, including:

- `target_agent.py`
- `agent_execution.json`
- `improvement.md`
- `results.json` when evaluation is available

## What Makes It Useful

This system is useful when ordinary productivity tracking breaks down.

Most productivity tools rely on manual logging or shallow categories. They can tell you that time was spent in a browser or on a map, but not whether that meant focused work, planning, job search, project research, errands, communication, or context switching.

This project tries to recover that missing layer of meaning. The goal is to build a system that can:

- explain what the user was likely doing
- preserve important task identity and transitions
- improve its own interpretation rules over repeated runs
- support reflection, planning, and behavioral analysis from real activity data

## Productivity Task

The key task is [task.md](/Users/tatianaushakova/sia/sia/tasks/productivity-breakdown/data/public/task.md).

It asks the agent to reconstruct a detailed daily activity timeline from:

- `day_*_public.json`
- optional support files under `data/public/supporting_raw/`

The bundled task includes:

- public evidence in [data/public](/Users/tatianaushakova/sia/sia/tasks/productivity-breakdown/data/public)
- hidden labels in [data/private](/Users/tatianaushakova/sia/sia/tasks/productivity-breakdown/data/private)
- a bundled reference agent in [reference/reference_target_agent.py](/Users/tatianaushakova/sia/sia/tasks/productivity-breakdown/reference/reference_target_agent.py)
- example task descriptions in [reference/SAMPLE_TASK_DESCRIPTIONS.md](/Users/tatianaushakova/sia/sia/tasks/productivity-breakdown/reference/SAMPLE_TASK_DESCRIPTIONS.md)

The public release version of the dataset is sanitized for hackathon/demo use.

## Run It

### Install

Pick the agent implementation you want to use.

Claude-only:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install 'sia-agent[claude]'
export ANTHROPIC_API_KEY="..."
```

Multi-provider / OpenHands:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install 'sia-agent[openhands]'

export ANTHROPIC_API_KEY="..."
export GEMINI_API_KEY="..."
export OPENAI_API_KEY="..."
```

PydanticAI:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install 'sia-agent[pydantic-ai]'
```

For Nebius-backed profiles:

```bash
export NEBIUS_API_KEY="..."
```

See [docs/configuration.md](docs/configuration.md) for provider and profile details.

### Run The Productivity System

```bash
sia run --task productivity-breakdown --max_gen 3 --run_id 1
```

Useful flags:

| Flag | Default | Description |
|---|---|---|
| `--task` | — | Bundled task name |
| `--task_dir` | — | External task directory |
| `--max_gen` | `3` | Number of generations |
| `--run_id` | `1` | Unique run id |
| `--meta-agent-profile` | `default-meta` | Meta / feedback profile |
| `--target-agent-profile` | `default-target` | Target agent profile |
| `--no-web` | off | Disable live dashboard |
| `--web-port` | `8000` | Dashboard port |

## Visualize Runs

The repo includes a small web UI for inspecting runs, generations, prompts, code, trajectories, and logs.

```bash
sia web --runs-dir ./runs --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

Do not open `sia/web/static/index.html` directly over `file://`; the UI expects the FastAPI backend.

## Repo Structure

```text
sia/
├── sia/
│   ├── orchestrator.py
│   ├── context_manager.py
│   ├── run_setup.py
│   ├── web/
│   └── tasks/
│       ├── _shared/
│       └── productivity-breakdown/
│           ├── data/
│           │   ├── public/
│           │   └── private/
│           └── reference/
├── runs/
├── tests/
└── docs/
```

## Other Bundled Tasks

The repo still contains the original benchmark-oriented bundled tasks:

- `gpqa`
- `lawbench`
- `longcot-chess`
- `spaceship-titanic`

But the current README and bundled demo focus on `productivity-breakdown`.

## Evaluation

The productivity task includes hidden labels and an evaluator so the loop can optimize against a concrete score.

In general, SIA-style tasks evaluate by:

1. running the target agent
2. writing a submission artifact in the generation directory
3. scoring that output against hidden data
4. feeding the result into the next-generation feedback prompt

For custom task authoring, see:

- [EVALUATION_GUIDE.md](EVALUATION_GUIDE.md)
- [docs/walkthrough.md](docs/walkthrough.md)

## Notes

- The codebase still contains generic SIA framework components and references.
- This repo was repurposed for a personalized productivity reconstruction system and hackathon submission.
- Public task artifacts were intentionally sanitized before publication.

## Further Reading

- [docs/architecture.md](docs/architecture.md)
- [docs/configuration.md](docs/configuration.md)
- [docs/troubleshooting.md](docs/troubleshooting.md)
- [EVALUATION_GUIDE.md](EVALUATION_GUIDE.md)
