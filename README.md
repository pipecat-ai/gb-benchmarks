# gb-benchmarks

Benchmark repository for sub-agent tasks and orchestration things.

The goal is to build tooling to better analyze things we do in realtime AI systems that are hard for today's models.

Task definitions, world data and structured input events, and (very long) system instructions are pulled from the <a href="https://github.com/pipecat-ai/gradient-bang">gradient-bang</a> project.

## port-to-port

The first public benchmark in this repo is `../port-to-port`, which tests the following task instruction:

```
  Go round-trip from our current location to the nearest mega-port. At the mega-port, recharge to full warp power.
  While traveling there and back, make as much money as possible by trading optimally at profitable ports on your
  route without going off-course. When you're back where you started, give me a quick summary with the mega-port you
  used, how much warp you recharged and what it cost, how many distinct ports you traded at, and total profit or
  loss from the whole trip.
```

This is a reasonably well-defined task that requires interpolation of the user's intent, some multi-step planning, excellent tool calling discipline, and good state tracking. SOTA models in reasoning mode are reasonably good at performing this task (though not perfect). Claude Sonnet 4.6 is the only model that does well on this task with reasoning disabled.

Here are scores for all of the models we've tested that have a per-turn P50 time of less than 4 seconds. We show only the best configuration for each model on this table. The highest thinking level is not always the best-performing configuration, interestingly. All configurations and models tested are in [port-to-port/leaderboards/leaderboard-natural.md](port-to-port/leaderboards/leaderboard-natural.md).

| Model                                | Score | Task Complete | Trade /15 | Path /15 | Tools /15 | Report /15 | Turn P50 | Turn P90 | Total Time | Est. Cost / Complete |
| ------------------------------------ | ----: | ------------: | --------: | -------: | --------: | ---------: | -------: | -------: | ---------: | -------------------: |
| gemini-3.5-flash (high)              |    97 |        100.0% |      12.0 |     15.0 |      15.0 |       15.0 |   1862.2 |   5388.5 |     140.97 |               $0.535 |
| glm-5.2 (max)                        |    97 |        100.0% |      11.0 |     14.8 |      14.3 |       14.8 |   1190.8 |  14458.6 |     212.72 |               $0.228 |
| claude-sonnet-5 (xhigh)              |    93 |        100.0% |       9.6 |     15.0 |      14.1 |       15.0 |   2527.3 |  13172.9 |     246.87 |               $0.384 |
| kimi-2.6 Cerebras (thinking)         |    92 |        100.0% |       7.0 |     15.0 |      15.0 |       15.0 |    497.8 |   2352.2 |      67.06 |               $0.137 |
| glm-5 (thinking)                     |    92 |        100.0% |       5.9 |     14.8 |      15.0 |       14.9 |   1420.1 |   4623.0 |     107.98 |                $1.05 |
| claude-sonnet-4-6 (none)             |    92 |        100.0% |       8.2 |     15.0 |      14.5 |       13.6 |   1998.1 |   4948.2 |     125.53 |               $0.281 |
| gpt-5.4 (low)                        |    92 |        100.0% |       7.6 |     15.0 |      15.0 |       14.9 |   2433.8 |  10455.4 |     136.22 |               $0.256 |
| gpt-5.6-terra (xhigh)                |    92 |        100.0% |       7.4 |     15.0 |      14.7 |       15.0 |   2253.3 |   6374.1 |     136.56 |               $0.222 |
| gpt-5.2 (medium)                     |    91 |        100.0% |       6.5 |     14.8 |      14.1 |       14.6 |   1047.9 |  10482.2 |     149.98 |               $0.171 |
| gemma-4-31b (thinking)               |    89 |        100.0% |       4.0 |     15.0 |      15.0 |       15.0 |    850.6 |   1065.5 |      60.43 |        $0.042–$0.066 |
| claude-haiku-4-5-20251001 (low)      |    89 |        100.0% |       4.3 |     14.1 |      14.4 |       14.8 |   2157.9 |   6863.1 |     125.41 |               $0.116 |
| nemotron-3-ultra-550b (thinking)     |    88 |        100.0% |       4.6 |     13.2 |      14.9 |       14.0 |    989.3 |   2817.5 |      81.03 |               $0.299 |
| gpt-5.1 (low)                        |    88 |        100.0% |       4.2 |     15.0 |      14.8 |       14.4 |   1798.2 |  12660.8 |     162.69 |               $0.173 |
| gpt-5.6-luna (xhigh)                 |    88 |         96.0% |       6.8 |     12.9 |      14.1 |       14.0 |   1490.2 |   5967.5 |     125.40 |               $0.111 |
| gemini-3.1-flash-lite-preview (high) |    87 |        100.0% |       2.4 |     14.8 |      14.6 |       14.3 |    802.8 |   2814.8 |      67.01 |               $0.049 |
| inkling (low)                        |    86 |        100.0% |       2.6 |     15.0 |      13.7 |       14.6 |    594.0 |   1337.1 |      57.16 |               $0.074 |
| gpt-4.1                              |    86 |        100.0% |       2.4 |     14.3 |      14.4 |       13.7 |    805.9 |   1395.4 |      61.33 |               $0.210 |
| gemini-2.5-flash (2048)              |    84 |        100.0% |       2.3 |     15.0 |      12.8 |       14.3 |   2352.2 |   3831.5 |     126.25 |               $0.059 |
| nemotron-3-super-120b (tb=512)       |    82 |        100.0% |       1.4 |     13.0 |      13.1 |       14.1 |   2854.6 |   7666.1 |     109.38 |               $0.548 |
| gpt-4o                               |    82 |         92.0% |       1.1 |     15.0 |      10.2 |       13.9 |    822.7 |   1951.9 |      70.70 |               $0.466 |
| gemini-3.1-pro-preview (medium)      |    81 |        100.0% |       1.7 |     15.0 |      10.9 |       15.0 |   3062.6 |   5958.4 |     155.53 |               $0.287 |
| qwen3.5-9b (thinking)                |    64 |         56.0% |       0.6 |      7.8 |       5.8 |       10.8 |   3237.6 |   9443.8 |     270.02 |               $0.649 |
| qwen3.5-27b (none)                   |    39 |          8.0% |       2.5 |     14.5 |       0.0 |        1.8 |   1932.7 |   4479.8 |     282.62 |                $2.83 |
| nemotron-3-super-120b (none)         |    37 |         16.0% |       1.6 |     14.2 |       0.2 |        2.3 |    826.3 |   2994.8 |     156.01 |                $2.06 |
| qwen3.5-4b                           |    37 |         12.0% |       0.8 |     13.5 |       0.1 |        2.8 |   1178.9 |   3033.4 |     241.03 |                $1.39 |
| glm-4.7-flash                        |    29 |         12.0% |       1.1 |      6.6 |       6.9 |        3.4 |   1875.3 |   3692.8 |     168.69 |                $1.82 |

Cost estimates use current list prices and the judged completion rate, not the raw run-success flag. Token-priced APIs use all 25 canonical usage traces; GPT-5.6 uses one cache-write-aware representative trace; Modal estimates use GPU-only active-request time across all 25 canonical traces. See the [full cost table and methodology](port-to-port/leaderboards/leaderboard-natural-costs.md). Kimi uses a public same-model price proxy, and Gemma's range covers its configured A100-to-H100 fallback.

Thank you to [Modal](https://modal.com) for providing compute resources for this benchmark. And to [Charles Frye](https://x.com/charles_irl/) for advice about models and inference tuning.

One note: qwen3.5-27b in thinking mode scores very well, but comes in just above the 4s turn cut-off. Advice on a faster inference stack for that model would be welcome!

## Prerequisites

- `uv` installed
- Python 3.12+
- You'll need API keys for the providers/models you run, and an ANTHROPIC_API_KEY to judge the quality of the natural language finish message.

## Example run command

```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider anthropic --model claude-sonnet-4-6 \
  --task-variant natural --thinking none \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/claude-sonnet-4-6-natural-none-<ts>.json \
  > runs/claude-sonnet-4-6-natural-none-<ts>.log 2>&1
```

## Judging

- Judge runs with `evaluate_runs.py` after the raw JSON lands.
- Single run:

```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" .venv/bin/python evaluate_runs.py \
  "runs/<run-stem>.json" \
  --out-dir "runs/eval-<run-stem>" \
  --report-accuracy-judge llm \
  --judge-model claude-sonnet-4-6
```

- Batch:

```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" .venv/bin/python evaluate_runs.py \
  "runs/<glob>.json" \
  --out-dir "runs/eval-<batch-stem>" \
  --report-accuracy-judge llm \
  --judge-model claude-sonnet-4-6
```

- A non-zero run exit is still judgeable if the raw JSON exists.
- If no raw JSON exists, rerun with `--log-json` instead of trying to reconstruct the run.
