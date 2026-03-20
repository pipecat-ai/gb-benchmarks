# gb-benchmarks

Benchmark repository for sub-agent tasks and orchestration things.

The goal is to build tooling to better analyze things we do in realtime AI systems that are hard for today's models.

Task definitions, world data and structured input events, and (very long) system instructions are pulled from from the <a href="https://github.com/pipecat-ai/gradient-bang">gradient-bang</a> project.

## port-to-port

The first public benchmark in this repo is `port-to-port/`, which tests LLM agents on 8 task variants in the Gradient Bang space-trading game. Agents are scored on a 100-point rubric covering mission completion, trade quality, path efficiency, tool discipline, and report quality.

### Model Leaderboard (natural task)

The `natural` task instruction is:

```
  Go round-trip from our current location to the nearest mega-port. At the mega-port, recharge to full warp power.
  While traveling there and back, make as much money as possible by trading optimally at profitable ports on your
  route without going off-course. When you're back where you started, give me a quick summary with the mega-port you
  used, how much warp you recharged and what it cost, how many distinct ports you traded at, and total profit or
  loss from the whole trip.
```

This is a reasonably well-defined task that requires interpolation of the user's intent, some multi-step planning, excellent tool calling discipline, and good state tracking. SOTA models in reasoning mode are reasonably good at performing this task (though not perfect). Claude Sonnet 4.6 is the only model that does well on this task with reasoning disabled.

Here are scores for all of the models we've tested that have a per-turn P50 time of less than 4 seconds. We show only the best configuration for each model on this table. The highest thinking level is not always the best-performing configuration, interestingly. All configurations and models tested are in [port-to-port/leaderboards/leaderboard-natural.md](port-to-port/leaderboards/leaderboard-natural.md).


| Model | Score | Task Complete | Trade /15 | Path /15 | Tools /15 | Report /15 | Turn P50 | Turn P90 | Total Time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| glm-5 (thinking) | 92 | 100.0% | 5.9 | 14.8 | 15.0 | 14.9 | 1420.1 | 4623.0 | 107.98 |
| claude-sonnet-4-6 (none) | 92 | 100.0% | 8.2 | 15.0 | 14.5 | 13.6 | 1998.1 | 4948.2 | 125.53 |
| gpt-5.4 (low) | 92 | 100.0% | 7.6 | 15.0 | 15.0 | 14.9 | 2433.8 | 10455.4 | 136.22 |
| gpt-5.2 (medium) | 91 | 100.0% | 6.5 | 14.8 | 14.1 | 14.6 | 1047.9 | 10482.2 | 149.98 |
| claude-haiku-4-5-20251001 (low) | 89 | 100.0% | 4.3 | 14.1 | 14.4 | 14.8 | 2157.9 | 6863.1 | 125.41 |
| gpt-5.1 (low) | 88 | 100.0% | 4.2 | 15.0 | 14.8 | 14.4 | 1798.2 | 12660.8 | 162.69 |
| gemini-3.1-flash-lite-preview (high) | 87 | 100.0% | 2.4 | 14.8 | 14.6 | 14.3 | 802.8 | 2814.8 | 67.01 |
| gpt-4.1 | 86 | 100.0% | 2.4 | 14.3 | 14.4 | 13.7 | 805.9 | 1395.4 | 61.33 |
| gemini-2.5-flash (2048) | 84 | 100.0% | 2.3 | 15.0 | 12.8 | 14.3 | 2352.2 | 3831.5 | 126.25 |
| nemotron-3-super-120b (tb=512) | 82 | 100.0% | 1.4 | 13.0 | 13.1 | 14.1 | 2854.6 | 7666.1 | 109.38 |
| gpt-4o | 82 | 92.0% | 1.1 | 15.0 | 10.2 | 13.9 | 822.7 | 1951.9 | 70.70 |
| gemini-3.1-pro-preview (medium) | 81 | 100.0% | 1.7 | 15.0 | 10.9 | 15.0 | 3062.6 | 5958.4 | 155.53 |
| qwen3.5-9b (thinking) | 64 | 56.0% | 0.6 | 7.8 | 5.8 | 10.8 | 3237.6 | 9443.8 | 270.02 |
| qwen3.5-27b (none) | 39 | 8.0% | 2.5 | 14.5 | 0.0 | 1.8 | 1932.7 | 4479.8 | 282.62 |
| nemotron-3-super-120b (none) | 37 | 16.0% | 1.6 | 14.2 | 0.2 | 2.3 | 826.3 | 2994.8 | 156.01 |
| qwen3.5-4b | 37 | 12.0% | 0.8 | 13.5 | 0.1 | 2.8 | 1178.9 | 3033.4 | 241.03 |
| glm-4.7-flash | 29 | 12.0% | 1.1 | 6.6 | 6.9 | 3.4 | 1875.3 | 3692.8 | 168.69 |

Thank you to [Modal](https://modal.com) for providing compute resources for this benchmark. And to [Charles Frye](https://x.com/charles_irl/) for advice about models and inference tuning.

One note: qwen3.5-27b in thinking mode scores very well, but comes in just above the 4s turn cut-off. Advice on a faster inference stack for that model would be welcome!

### System Prompt Sweep

In addition to comparing models, the benchmark can compare **system prompts** on a fixed model across all 8 task variants. The `run_system_prompt_sweep.sh` script runs every `.txt` file in the prompts directory against all tasks for N rounds, then evaluates the results.

#### Quick Start

```bash
cd port-to-port
uv sync

# GPT-4.1, 10 rounds (default)
OPENAI_API_KEY=... ANTHROPIC_API_KEY=... \
  ROUNDS=10 ./run_system_prompt_sweep.sh

# Gemini 2.5 Flash, 20 rounds
GOOGLE_API_KEY=... ANTHROPIC_API_KEY=... \
  PROVIDER=google MODEL=gemini-2.5-flash THINKING=high \
  ROUNDS=20 ./run_system_prompt_sweep.sh

# Run only specific tasks
TASK_VARIANTS="natural,trade-arbitrage" ./run_system_prompt_sweep.sh

# Run only specific prompts (use a separate directory)
PROMPTS_DIR=my_prompts ./run_system_prompt_sweep.sh
```

#### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PROVIDER` | `openai` | LLM provider: `openai`, `google`, or `anthropic` |
| `MODEL` | `gpt-4.1` | Model name |
| `THINKING` | `none` | Thinking level: `none`, `minimal`, `low`, `medium`, `high` |
| `ROUNDS` | `10` | Number of rounds per (prompt, task) combination |
| `PARALLEL` | `7` | Max concurrent benchmark runs |
| `PROMPTS_DIR` | `system_prompts` | Directory containing prompt `.txt` files |
| `TASK_VARIANTS` | all 8 tasks | Comma-separated list of tasks to run |
| `EVAL_JUDGE_MODEL` | `claude-sonnet-4-6` | Model used for report accuracy judging |

#### API Keys

The sweep script validates the required API key for the selected provider:
- `openai` → `OPENAI_API_KEY`
- `google` → `GOOGLE_API_KEY`
- `anthropic` → `ANTHROPIC_API_KEY`

The evaluator also requires `ANTHROPIC_API_KEY` for the LLM judge (default: Claude Sonnet).

#### Output

Results are written to `port-to-port/runs/prompt-sweep-<timestamp>/`:

| File | Description |
|---|---|
| `*.json` | Per-run detailed JSON logs |
| `*.log` | Per-run stdout/stderr |
| `results.tsv` | Summary TSV with one row per run |
| `progress.log` | Live progress log |
| `eval/table.md` | Markdown evaluation summary with per-task and overall tables |
| `eval/table.csv` | CSV version of the evaluation |
| `eval/aggregate.json` | Full aggregate statistics |
| `eval/enriched_runs.jsonl` | Per-run enriched data with scores |
| `DONE` | Written on completion with run metadata |

The overall table includes 95% bootstrap confidence intervals (e.g., `92.6 ± 1.6`).

#### Adding Prompts

Add a `.txt` file to the prompts directory. The filename (without `.txt`) becomes the prompt label.

Prompts ending in `_inlined` are treated specially: the `load_game_info` tool is excluded (the game info is assumed to be baked into the prompt itself).

### Task Variants

| Task | Turn Budget | Description |
|---|---:|---|
| `natural` | 50 | Full port-to-port: visit mega-port, recharge, trade, return home |
| `trade-arbitrage` | 100 | Complete a multi-port trading circuit and return |
| `explore-fuel` | 150 | Explore 5+ new sectors and return home |
| `info-retrieval` | 50 | Answer questions using game info tools |
| `scavenger-hunt` | 50 | Buy specific items at specific sectors |
| `megaport-gauntlet` | 50 | Navigate to mega-port, dump cargo, recharge, return |
| `cargo-logistics` | 50 | Buy and deliver cargo to a target sector |
| `error-recovery` | 50 | Handle intentionally broken tool calls gracefully |

### Scoring Rubric (100 points)

| Category | Points | What it measures |
|---|---:|---|
| Mission Completion | 40 | Did the agent complete the task objectives? |
| Trade Quality | 15 | Profit earned, trade coverage |
| Path Efficiency | 15 | Ratio of productive actions to total turns |
| Tool Discipline | 15 | Avoiding bad actions, unnecessary tool calls |
| Report Quality | 15 | Accuracy and completeness of the finished() message |

## Prerequisites

- `uv` installed
- Python 3.12+
- API keys for the providers/models you run, and an `ANTHROPIC_API_KEY` to judge the quality of the natural language finish message.

## Single Run

```bash
cd port-to-port

uv run python mini-rl-env.py \
  --provider openai --model gpt-4.1 \
  --task-variant natural --thinking none \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/gpt-4.1-natural-<ts>.json \
  > runs/gpt-4.1-natural-<ts>.log 2>&1
```

## Evaluation

The evaluator can be run independently on existing JSON logs:

```bash
cd port-to-port

# Single run
ANTHROPIC_API_KEY=... uv run python evaluate_runs.py \
  "runs/<run-stem>.json" \
  --out-dir "runs/eval-<run-stem>" \
  --report-accuracy-judge llm \
  --judge-model claude-sonnet-4-6

# Batch (glob)
ANTHROPIC_API_KEY=... uv run python evaluate_runs.py \
  "runs/<glob>.json" \
  --out-dir "runs/eval-<batch-stem>" \
  --report-accuracy-judge llm \
  --judge-model claude-sonnet-4-6
```

A non-zero run exit is still judgeable if the raw JSON exists. If no raw JSON exists, rerun with `--log-json` instead of trying to reconstruct the run.
