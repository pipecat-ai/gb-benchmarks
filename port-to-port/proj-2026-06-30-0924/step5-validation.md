# Step 5 — Validation summary

Final authoritative run: `runs/baseten-sweep-20260703-142414/` — 5 configs × 25 rounds = 125 episodes, **strictly sequential** (one episode per process, under the ~1-concurrent Baseten limit), `mt=8192`, on the fully-fixed harness (steps 2/3/6/7). Judged with `claude-sonnet-4-6`.

## Results (25 rounds/config)

| Config | Primary /100 | Task Complete | Trade /15 | Tools /15 | Turn P50 (ms) | Total Time (s) |
|---|---:|---:|---:|---:|---:|---:|
| glm-5.2 xhigh (→ effort=max) | **97** | 100% | 11.0 | 14.3 | 1191 | 213 |
| glm-5.2 high | 94 | 100% | 10.2 | 15.0 | 809 | 117 |
| glm-5.2 none | 92 | 100% | 8.9 | 14.8 | 785 | 80 |
| nemotron-3-ultra-550b high | 88 | 100% | 4.6 | 14.9 | 989 | 81 |
| nemotron-3-ultra-550b none | 83 | 100% | 2.9 | 11.7 | 754 | 62 |

**All configs reach 100% task completion.** Every rate-limit that occurred (21 across 125 episodes) was recovered by step-6 backoff-retry (0 empties, 0 mislabeled failures).

## vs the original 4096 / parallel / pre-fix baseline

| Config | Primary | Tools /15 | Task Complete |
|---|---|---|---|
| glm-5.2 high | 82 → **94** | 4.3 → **15.0** | 80% → **100%** |
| glm-5.2 none | 77 → **92** | 3.9 → **14.8** | 88% → **100%** |
| nemotron high | 83 → **88** | 8.8 → **14.9** | 100% |
| nemotron none | 76 → **83** | 4.4 → **11.7** | 100% |
| glm-5.2 xhigh(max) | — | — → **14.3** | new best config (97) |

Tools-discipline (tanked by the no-tool/empty/rate-limit turns) recovered from ~4/15 to ~15/15. glm-5.2 xhigh(max) at 97 now ties the leaderboard leader.

## What produced the improvement (attribution)
- **Step 2 (mt 4096→8192):** removed Mechanism A (reasoning truncation before the tool call).
- **Sequential running:** the original "Mechanism B empties" were root-caused as **Baseten HTTP 429 rate-limiting** (concurrency ~1; 6-way → 98.7% 429, sequential → ~0), swallowed by pipecat into empty responses. Running one-at-a-time avoids the rate limit.
- **Step 6 (429 backoff-retry):** recovers the occasional 429 even sequentially; surfaces exhausted/non-429 errors distinctly instead of as empties.
- **Step 7 (GLM effort restriction):** Baseten now accepts GLM-5.2 `reasoning.effort` only in {none, high, max}; harness maps `xhigh→max` and rejects low/medium (which had started 400-failing mid-project).
- **Step 3 (empty-retry) / Step 4 (reasoning preservation):** step 3 is a net for genuine empties (rarely needed once B was understood as rate-limiting); step 4 was **dropped** — the completion failures were A + B, not reasoning-stripping, and GLM scores 92–97 without it.

## Measured finding — Nemotron trade quality (no code change)
Nemotron-3-Ultra completes 100% but trades weakest of the set (Trade 2.9 none / 4.6 high vs GLM 8.9–11.0). With reasoning off it under-trades and is prone to invalid buy/sell direction; with reasoning on it improves but still trails GLM. This is a model-capability gap, reported per plan, not addressed by a harness change.

## Leaderboard
`leaderboards/leaderboard-natural.md` + `-filtered.md` regenerated: stale `mt=4096` Baseten rows (incl. now-invalid GLM low/medium) replaced with the `mt=8192` rows above; README best-config rows updated to `glm-5.2 (max) 97` and `nemotron-3-ultra-550b (thinking) 88`.
