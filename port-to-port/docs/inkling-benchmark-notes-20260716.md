# Inkling (thinkingmachines/inkling) on Baseten — port-to-port notes

_Added 2026-07-16 (proj-2026-07-15-1700). Integrated, benchmarked, and added to the natural leaderboard._

## What it is
Thinking Machines **Inkling** — 975B-param MoE (~41B active), 1M context, native
reasoning. Served **serverless on Baseten** (pay-per-token), OpenAI Chat
Completions compatible. Model id: `thinkingmachines/inkling`.

## Integration (harness)
Runs through the `openai` provider against `https://inference.baseten.co/v1`
(key `BASETEN_API_KEY`, read as `OPENAI_API_KEY`). All Inkling behavior is gated
to the exact model set `{inkling, thinkingmachines/inkling}` in `mini-rl-env.py`;
GLM/Nemotron and every other path are untouched.

- **Reasoning control = the TOP-LEVEL native `reasoning_effort` field** (an OpenAI
  `create()` kwarg), *not* the nested `extra_body.reasoning.effort` that GLM reads.
  A controlled step-1 probe (`diagnostics/inkling_probe.py`) confirmed all three
  representations actually move `reasoning_tokens`, but native is the documented,
  future-proof one (Baseten already changed GLM's nested behavior under us once).
  The harness emits `extra["reasoning_effort"]` and strips any stale competing
  `extra_body` control so exactly one reaches the wire.
- **Effort mapping** (`_baseten_inkling_reasoning_effort`): `none→none,
  minimal→minimal, low→low, medium→medium, high→high, xhigh→max`. Full range
  supported (unlike GLM's none/high/max-only). Note the generic thinking-level
  normalizer aliases `minimal→none`, so the mapper special-cases `minimal` to
  keep it distinct.
- **`temperature=1`** (TM reference + probe fixed control), forced for Inkling
  on Baseten only.
- **`max_tokens=16384`** — 8192 confirmed to truncate large tool-call payloads at
  higher effort; 16384 completes. The sweep carries a per-config cap.
- Inkling is in `_is_baseten_retry_eligible_model` (exact set), so the 429
  backoff + empty-response gates cover it.

## How to run
```bash
CONFIG_FILTER=inkling-low,inkling-high,inkling-max ROUNDS=25 \
  bash run_baseten_sweep.sh          # strictly sequential (Baseten ~1 concurrent)
# dry-run the config plan with no key/network:
PRINT_CONFIGS=1 CONFIG_FILTER=inkling-low,inkling-high,inkling-max bash run_baseten_sweep.sh
```
Sweep configs (4-field `slug|model|thinking|max_tokens`): `inkling-low` (low),
`inkling-high` (high), `inkling-max` (**xhigh** → reasoning_effort=max), all at
mt=16384. `none` is probe/smoke-only, never canonical.

## Results (natural, 25 rounds/config, judged claude-sonnet-4-6)
| Config | Primary /100 | Task Complete | Trade /15 | Path /15 | Tools /15 | Report /15 | Turn P50 | Turn P90 | Total P50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| inkling (low) | **86** | 100% | 2.6 | 15.0 | 13.7 | 14.6 | 594 ms | 1337 ms | 57.2 s |
| inkling (high) | 86 | 100% | 3.2 | 14.8 | 13.2 | 14.5 | 606 ms | 3402 ms | 111.7 s |
| inkling (xhigh→max) | 86 | 100% | 2.8 | 15.0 | 13.2 | 14.7 | 606 ms | 3156 ms | 129.8 s |

Leaderboard best-config row: **`inkling (low)`** (same score, fastest, tightest tail).

## Findings / gotchas
- **Effort has no score effect** — low/high/max all land at Primary 86 (matches
  the integration doc's "no effort trend"). Higher effort only inflates the
  latency tail (Turn P90 1337 ms @ low → 3402 ms @ high) and total time. For a
  future rerun, sweeping just `low` would save ~⅔ the compute.
- **Reasoning is bursty**: Inkling reasons on only ~20% of turns (planning) and
  answers the rest directly (0 reasoning tokens). On reasoned turns the effort
  scales — median 88 @ low vs ~337 @ high/max, and the tail explodes with effort
  (p90 353 → 4571 → 5518; max 1735 → 12626 → 13640 tokens).
- **Weak trade quality (2.6–3.2)** caps the score. Inkling under-trades like
  Nemotron; path/tools/report are strong (15.0 / 13.x / 14.6) and it's fast and
  tool-disciplined. This is a genuine model-capability gap, not a harness limit —
  GLM trades 8.9–11 on the identical harness.
- **100% task completion, 0 infra failures** across all 75 episodes (0 empties,
  0 rate-limits, 0 timeouts) running strictly sequential.
- `none` behavior: reasoning_tokens=0 and tool calls still parse, but CoT folding
  into `content` was "not established" in the tool path (the doc's folding note is
  from a no-tools text task). `none` is excluded from canonical regardless.

See also memory `baseten-port-to-port.md`, `../aiewf-eval/docs/inkling-baseten-integration.md`,
and the effort/run/eval evidence in `proj-2026-07-15-1700/`.
