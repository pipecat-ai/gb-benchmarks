# Step 5 VALIDATION review — Codex

## Verdict: Clean

No blocking, should-fix, or nice-to-have findings. The staged Step 5 artifacts are internally consistent and ready for the approval gate. This was a read-only validation: no Baseten calls and no re-judging were performed.

## Blocking

None.

## Should-fix

None.

## Nice-to-have

None.

## Clean checks

- **Raw and derivatives:** Found exactly 75 raw JSONs and 75 derivatives with the exact expected `3 × 25` filenames. A recursive comparison of every corresponding pair found exactly two changed paths: `config.model` and `summary.model`, both `thinkingmachines/inkling` → `inkling`. All turns, scores, finished messages, and every other field are identical. All 75 raw files still have `thinkingmachines/inkling` in both model fields; their mtimes also predate every derivative copy.
- **Grouping:** Exact groups are `(inkling, low, 16384, https://inference.baseten.co/v1)=25`, `(inkling, high, 16384, https://inference.baseten.co/v1)=25`, and `(inkling, xhigh, 16384, https://inference.baseten.co/v1)=25`.
- **Evaluation:** `enriched_runs.jsonl` has 75 rows and 75 unique, absolute, existing derivative paths. Every required score is finite numeric, and the derivative/enriched sets match exactly. `aggregate.json` records `judge_model=claude-sonnet-4-6` and `report_accuracy_judge=llm`.
- **Combined integrity:** The 1,625-row combined JSONL is byte-for-byte the complete 1,550-row master file followed by the exact 75-row Inkling enriched file. All raw and resolved file keys are unique, so every existing master row is untouched.
- **Symlinks and join:** Found exactly 75 `baseten-inkling-*.json` symlinks among 1,475 leaderboard inputs. Their resolved targets exactly equal the 75 enriched derivative paths. Independently checking all 1,475 resolved inputs against the combined enriched file found zero missing joins.
- **Scratch diff:** Removing the three Inkling table lines and changing only the enriched header `20260716` → `20260715` reconstructs the committed leaderboard byte-for-byte. Thus the sole existing-line change is that header, and all existing table rows retain identical bytes and order.
- **Independent aggregation:** The scratch rows exactly match recomputation from the 25 runs/config using Primary median, task-complete rate, dimension means, linear turn percentiles over raw turns, and elapsed-time median:

  | Thinking | Primary | Complete | Trade | Path | Tools | Report | Turn P50 | Turn P90 | Total P50 |
  |---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
  | low | 86 | 100.0% | 2.6 | 15.0 | 13.7 | 14.6 | 594.0 ms | 1337.1 ms | 57.16 s |
  | high | 86 | 100.0% | 3.2 | 14.8 | 13.2 | 14.5 | 605.6 ms | 3402.2 ms | 111.73 s |
  | xhigh | 86 | 100.0% | 2.8 | 15.0 | 13.2 | 14.7 | 606.1 ms | 3155.9 ms | 129.79 s |
- **README best-config:** All three configurations tie at Primary 86 / 100% complete. `low` is correctly selected: it has the fastest Total Time P50, the tightest Turn P90, and Turn P50 `594.0 ms < 4000 ms`, so it qualifies for the README table.
- **Filtered output:** `leaderboard-natural-filtered.md` is currently byte-identical to `leaderboard-natural.md`; applying the same approved scratch bytes to both is correct.
