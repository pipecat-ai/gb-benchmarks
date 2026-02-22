# gb-benchmarks

Standalone benchmark repo for Gradient Bang experiments.

Current benchmark package:
- `port-to-port/` (ported from `benchmarks/mini-rl-harness`)

## Prerequisites

- `uv` installed
- Python 3.12+
- API key(s) for the provider/model you run:
  - Anthropic: `ANTHROPIC_API_KEY`
  - OpenAI-compatible: `OPENAI_API_KEY`
  - Google: `GOOGLE_API_KEY`

## Run From Repo Root

Run a single benchmark with Claude Sonnet 4.6 from `~/src/gb-benchmarks`:

```bash
cd ~/src/gb-benchmarks
mkdir -p port-to-port/runs

TS="$(date -u +%Y%m%dT%H%M%SZ)"
uv run --project port-to-port python port-to-port/mini-rl-env.py \
  --provider anthropic \
  --model claude-sonnet-4-6 \
  --thinking-budget 1024 \
  --max-turns 40 \
  --log-json "port-to-port/runs/claude-sonnet-4-6-${TS}.json" \
  > "port-to-port/runs/claude-sonnet-4-6-${TS}.log" 2>&1
```

Notes:
- Exit code `0` = strict benchmark success.
- Exit code `1` = run completed but did not meet success criteria.
- Run artifacts are written to `port-to-port/runs/`.

## Quick Result Check

```bash
rg -n "^(SUCCESS|BAD_ACTIONS_COUNT|FINAL_SECTOR|COHERENT_REPORT|TURNS|ELAPSED_MS)=" \
  port-to-port/runs/claude-sonnet-4-6-*.log
```

## Additional Tools

- `port-to-port/evaluate_runs.py`: post-process run JSON files.
- `port-to-port/build_primary_leaderboard.py`: build markdown leaderboard.
- `port-to-port/run_model_matrix.sh`: single-round model matrix helper.
- `port-to-port/run_big_sweeps.sh`: parallel large sweep helper.
