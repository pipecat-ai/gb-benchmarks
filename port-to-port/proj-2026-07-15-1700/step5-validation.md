# Step 5 — Eval + leaderboard validation

## Pipeline (non-destructive)
1. **Derivatives:** copied all 75 canonical raw runs to `runs/leaderboard-derivatives-inkling-20260716/` (`baseten-inkling-{low,high,max}-r{01..25}.json`), rewriting ONLY `config.model`/`summary.model` `thinkingmachines/inkling`→`inkling`. Raw runs untouched (verified: still `thinkingmachines/inkling`, mtimes predate the copies).
2. **Judge:** `evaluate_runs.py … --report-accuracy-judge llm --judge-model claude-sonnet-4-6` over the 75 derivatives → `runs/eval-inkling-20260716/enriched_runs.jsonl` (75 rows, absolute derivative paths).
3. **Combine:** `runs/leaderboard-natural-v1-refresh-20260716.jsonl` = master `…-20260715.jsonl` (1550 rows, byte-identical prefix) + the 75 Inkling rows = 1625; all `file` keys unique, master rows untouched.
4. **Symlink:** 75 `baseten-inkling-*.json` symlinks into `runs/leaderboard-natural-v1-input/` (→ 1475 inputs); each resolves to its enriched `file` (0 missing joins across all 1475).
5. **Rebuild → scratch → diff:** `build_primary_leaderboard.py` to a scratch path; diff vs committed `leaderboard-natural.md` = **only** the `Enriched scores:` header line (20260715→20260716) + 3 added Inkling rows; every existing row byte-identical.
6. **Apply (post-approval):** copied scratch → `leaderboards/leaderboard-natural.md` and `-filtered.md` (byte-identical); added the `inkling (low)` best-config row to `../README.md` at the 86 tier.

## Results (25 rounds/config, judged claude-sonnet-4-6)

| Config | Primary /100 | Task Complete | Trade /15 | Path /15 | Tools /15 | Report /15 | Turn P50 | Turn P90 | Total P50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| inkling (low) | **86** | 100% | 2.6 | 15.0 | 13.7 | 14.6 | 594 ms | 1337 ms | 57.2 s |
| inkling (high) | 86 | 100% | 3.2 | 14.8 | 13.2 | 14.5 | 606 ms | 3402 ms | 111.7 s |
| inkling (xhigh→max) | 86 | 100% | 2.8 | 15.0 | 13.2 | 14.7 | 606 ms | 3156 ms | 129.8 s |

## Findings
- **Effort has no score effect** — low/high/max all land at Primary 86 (matches the integration doc's "no effort trend"). Higher effort only inflates the latency tail (Turn P90 1337 ms @ low → 3402 ms @ high) and total time.
- **`inkling (low)` is the best config**: same Primary/completion as the others, fastest total (57 s), tightest tail, and the doc's recommended single pick. Turn P50 594 ms ≪ the 4 s README cutoff → included in the README main table.
- **Score profile:** 100% task completion with strong path (15.0) / report (14.6) but **weak trade quality (2.6–3.2)** — Inkling under-trades (Nemotron-like), which caps the primary at 86. Fast and disciplined, weak at the profit-optimization dimension.

## Rigor
- Non-destructive: raw runs untouched; only Inkling rows + the enriched-header line changed in the committed leaderboards; existing rows byte-identical; `-filtered.md` received the same approved bytes.
- Paired review (my direct + Codex): **Clean** — Codex independently reconstructed the committed leaderboard byte-for-byte after removing the 3 Inkling rows + header, recomputed every aggregate, and confirmed the derivatives/enriched/join/best-config.
- **User-approved** the leaderboard + README commit before it was applied (plan's approval gate).
