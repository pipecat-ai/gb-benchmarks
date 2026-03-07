# AGENTS.md

## Port-to-Port Benchmark Ops

### Core rules
- Keep runs sequential per provider endpoint. Parallelize only across different providers or different OpenAI-compatible base URLs.
- Do not use fail-fast wrappers such as `set -e` for multi-run workers. One failed run must not block later runs.
- Always pass `--log-json runs/<run-stem>.json` for any run that may be judged or compared later.
- Always capture console output to `runs/<run-stem>.log` or a worker log with `tee`.
- A failed run is still benchmark data if the raw JSON exists. Judge it instead of discarding it.
- Default benchmark settings are `--max-turns 50` and `--function-call-timeout-secs 20`.

### Environment keys
- Do not `source` the repo `.env` wholesale. Extract only the needed key.
- Anthropic:
```bash
ANTHROPIC_API_KEY="$(rg --no-line-number '^ANTHROPIC_API_KEY=' /home/khkramer/src/gb-benchmarks/.env | cut -d= -f2-)"
```
- OpenAI / OpenAI-compatible:
```bash
OPENAI_API_KEY="$(rg --no-line-number '^OPENAI_API_KEY=' /home/khkramer/src/gb-benchmarks/.env | cut -d= -f2-)"
```
- Google:
```bash
GOOGLE_API_KEY="$(rg --no-line-number '^GOOGLE_API_KEY=' /home/khkramer/src/gb-benchmarks/.env | cut -d= -f2-)"
```

### Shared command pattern
- Work from `port-to-port`:
```bash
cd /home/khkramer/src/gb-benchmarks/port-to-port
```
- Natural prompt:
```bash
--task-variant natural
```
- Literal prompt:
```bash
--task-variant literal
```
- Common flags:
```bash
--max-turns 50 --function-call-timeout-secs 20 --log-json runs/<run-stem>.json
```

### Exact run commands

#### Anthropic
- Claude Sonnet 4.6 none:
```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider anthropic --model claude-sonnet-4-6 \
  --task-variant natural --thinking none \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/claude-sonnet-4-6-natural-none-<ts>.json \
  > runs/claude-sonnet-4-6-natural-none-<ts>.log 2>&1
```
- Claude Sonnet 4.6 low:
```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider anthropic --model claude-sonnet-4-6 \
  --task-variant natural --thinking low \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/claude-sonnet-4-6-natural-low-<ts>.json \
  > runs/claude-sonnet-4-6-natural-low-<ts>.log 2>&1
```
- Claude Sonnet 4.6 medium:
```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider anthropic --model claude-sonnet-4-6 \
  --task-variant natural --thinking medium \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/claude-sonnet-4-6-natural-medium-<ts>.json \
  > runs/claude-sonnet-4-6-natural-medium-<ts>.log 2>&1
```
- Claude Haiku 4.5 low:
```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider anthropic --model claude-haiku-4-5-20251001 \
  --task-variant natural --thinking low \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/claude-haiku-4-5-natural-low-<ts>.json \
  > runs/claude-haiku-4-5-natural-low-<ts>.log 2>&1
```
- Claude Haiku 4.5 medium:
```bash
ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider anthropic --model claude-haiku-4-5-20251001 \
  --task-variant natural --thinking medium \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/claude-haiku-4-5-natural-medium-<ts>.json \
  > runs/claude-haiku-4-5-natural-medium-<ts>.log 2>&1
```

#### Hosted OpenAI
- GPT 5.2 medium:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model gpt-5.2 \
  --task-variant natural --thinking medium \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/gpt-5.2-natural-medium-<ts>.json \
  > runs/gpt-5.2-natural-medium-<ts>.log 2>&1
```
- GPT 5.1 low:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model gpt-5.1 \
  --task-variant natural --thinking low \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/gpt-5.1-natural-low-<ts>.json \
  > runs/gpt-5.1-natural-low-<ts>.log 2>&1
```
- GPT 5.1 medium:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model gpt-5.1 \
  --task-variant natural --thinking medium \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/gpt-5.1-natural-medium-<ts>.json \
  > runs/gpt-5.1-natural-medium-<ts>.log 2>&1
```
- GPT 4.1:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model gpt-4.1 \
  --task-variant natural --thinking none \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/gpt-4.1-natural-<ts>.json \
  > runs/gpt-4.1-natural-<ts>.log 2>&1
```

#### Google
- Gemini 3.1 Flash Lite Preview minimal:
```bash
GOOGLE_API_KEY="$GOOGLE_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider google --model gemini-3.1-flash-lite-preview \
  --task-variant natural --thinking minimal \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/gemini-3.1-flash-lite-preview-natural-minimal-<ts>.json \
  > runs/gemini-3.1-flash-lite-preview-natural-minimal-<ts>.log 2>&1
```
- Gemini 3.1 Flash Lite Preview medium:
```bash
GOOGLE_API_KEY="$GOOGLE_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider google --model gemini-3.1-flash-lite-preview \
  --task-variant natural --thinking medium \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/gemini-3.1-flash-lite-preview-natural-medium-<ts>.json \
  > runs/gemini-3.1-flash-lite-preview-natural-medium-<ts>.log 2>&1
```
- Gemini 3.1 Flash Lite Preview high:
```bash
GOOGLE_API_KEY="$GOOGLE_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider google --model gemini-3.1-flash-lite-preview \
  --task-variant natural --thinking high \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/gemini-3.1-flash-lite-preview-natural-high-<ts>.json \
  > runs/gemini-3.1-flash-lite-preview-natural-high-<ts>.log 2>&1
```
- Gemini 3.1 Pro Preview medium:
```bash
GOOGLE_API_KEY="$GOOGLE_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider google --model gemini-3.1-pro-preview \
  --task-variant natural --thinking medium \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/gemini-3.1-pro-preview-natural-medium-<ts>.json \
  > runs/gemini-3.1-pro-preview-natural-medium-<ts>.log 2>&1
```
- Gemini 2.5 Flash exact budget 2048:
```bash
GOOGLE_API_KEY="$GOOGLE_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider google --model gemini-2.5-flash \
  --task-variant natural --thinking-budget 2048 \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/gemini-2.5-flash-natural-budget2048-<ts>.json \
  > runs/gemini-2.5-flash-natural-budget2048-<ts>.log 2>&1
```
- Google caveats:
  - Gemini 3 / Supernova models use benchmark `--thinking`, which maps to `thinking_level`.
  - Gemini 2.5 Flash supports exact `--thinking-budget`.
  - Do not pass `--max-tokens` on `--provider google`.

#### OpenAI-compatible Nemotron
- Shared Nano base URL:
```bash
NEMO_NANO_URL="https://daily--nemotron-nano-b200-sglang-serve.modal.run"
```
- Shared Super base URL:
```bash
NEMO_SUPER_URL="https://daily--nemotron-super-b200-sglang-serve.modal.run"
```
- Nemotron Nano none:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model nemotron-3-nano-30b \
  --openai-base-url "$NEMO_NANO_URL" \
  --task-variant natural --thinking none --max-tokens 4096 \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/nemotron-3-nano-30b-natural-none-<ts>.json \
  > runs/nemotron-3-nano-30b-natural-none-<ts>.log 2>&1
```
- Nemotron Nano low:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model nemotron-3-nano-30b \
  --openai-base-url "$NEMO_NANO_URL" \
  --task-variant natural --thinking low --max-tokens 4096 \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/nemotron-3-nano-30b-natural-low-<ts>.json \
  > runs/nemotron-3-nano-30b-natural-low-<ts>.log 2>&1
```
- Nemotron Nano medium:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model nemotron-3-nano-30b \
  --openai-base-url "$NEMO_NANO_URL" \
  --task-variant natural --thinking medium --max-tokens 4096 \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/nemotron-3-nano-30b-natural-medium-<ts>.json \
  > runs/nemotron-3-nano-30b-natural-medium-<ts>.log 2>&1
```
- Nemotron Nano high:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model nemotron-3-nano-30b \
  --openai-base-url "$NEMO_NANO_URL" \
  --task-variant natural --thinking high --max-tokens 4096 \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/nemotron-3-nano-30b-natural-high-<ts>.json \
  > runs/nemotron-3-nano-30b-natural-high-<ts>.log 2>&1
```
- Nemotron Super none:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model nemotron-3-super-120b \
  --openai-base-url "$NEMO_SUPER_URL" \
  --task-variant natural --thinking none --max-tokens 4096 \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/nemotron-3-super-120b-natural-none-<ts>.json \
  > runs/nemotron-3-super-120b-natural-none-<ts>.log 2>&1
```
- Nemotron Super low:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model nemotron-3-super-120b \
  --openai-base-url "$NEMO_SUPER_URL" \
  --task-variant natural --thinking low --max-tokens 4096 \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/nemotron-3-super-120b-natural-low-<ts>.json \
  > runs/nemotron-3-super-120b-natural-low-<ts>.log 2>&1
```
- Nemotron Super medium:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model nemotron-3-super-120b \
  --openai-base-url "$NEMO_SUPER_URL" \
  --task-variant natural --thinking medium --max-tokens 4096 \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/nemotron-3-super-120b-natural-medium-<ts>.json \
  > runs/nemotron-3-super-120b-natural-medium-<ts>.log 2>&1
```
- Nemotron Super high:
```bash
OPENAI_API_KEY="$OPENAI_API_KEY" .venv/bin/python mini-rl-env.py \
  --provider openai --model nemotron-3-super-120b \
  --openai-base-url "$NEMO_SUPER_URL" \
  --task-variant natural --thinking high --max-tokens 4096 \
  --max-turns 50 --function-call-timeout-secs 20 \
  --log-json runs/nemotron-3-super-120b-natural-high-<ts>.json \
  > runs/nemotron-3-super-120b-natural-high-<ts>.log 2>&1
```
- Nemotron caveats:
  - On these SGLang endpoints, benchmark `--thinking` maps to exact `thinking_budget` values: `none=0`, `low=128`, `medium=512`, `high=2048`.
  - Keep one run at a time per endpoint.
  - Always pass `--max-tokens 4096` for the benchmark runs we are comparing here.

### Monitoring
- Prefer a live PTY session for long workers.
- Log `RUN_START` and `RUN_EXIT` around each run when using a sequential worker.
- Watch for:
  - `HARNESS_CONFIG` to confirm provider/model/thinking settings
  - `LLM_RUN` and `TURN_COMPLETE` for live progress
  - `WROTE ...json` to confirm the raw artifact exists
  - `SUCCESS=`, `TERMINAL_REASON=`, and `RUN_EXIT rc=...` at the end

### Judging
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

### Prompt and leaderboard discipline
- Bump the built-in prompt version string before collecting new prompt-iteration data.
- Do not mix prompt revisions inside one leaderboard.
- Canonical leaderboards are prompt-specific:
  - `port-to-port/leaderboards/leaderboard-natural.md`
  - `port-to-port/leaderboards/leaderboard-literal.md`
- When rebuilding a leaderboard, feed `build_primary_leaderboard.py` only runs from a single prompt scope.
