# Step 5 — judge-all and scratch-leaderboard validation

Status: **COMPLETE AND PUBLISHED LOCALLY**

Date: 2026-07-18

Approved preflight: `step5-judge-scratch-preflight.md` at SHA-256
`312b2a804a87691ff2a5fb6e43f7e651f16ee27c26e78b96136900723e358c5a`.

## Outcome

The approved non-publishing package completed successfully. All 159 frozen
GPT-5.6 JSON artifacts were copied byte-for-byte to the derivative tree and
evaluated. The production-v3 manifest selected exactly 150 enriched rows, 25
for every Luna/Terra low/xhigh/max configuration. Those rows were joined to
the existing enriched data and built into an isolated scratch leaderboard.

No benchmark model or Sol run occurred. Raw runs, the production state and
manifest, the canonical leaderboard input directory, both committed
leaderboards, and the repository README were not modified.

## Judge execution and budget

- Evaluator: `evaluate_runs.py`, sequential, exit 0.
- Judge: `claude-sonnet-4-6`, temperature 0, 30-second request timeout.
- Initial requests: 152 of the approved 152 maximum.
- Parse-correction requests: 6 of the approved 152 maximum.
- Total requests: 158 of the approved 304 maximum.
- Accounted request-timeout seconds: 4,740 of 9,120.
- Reserve for the actual request topology: at most 790,000 input tokens and
  9,776 output tokens, or $2.51664 at the preflight rates. The evaluator does
  not retain provider usage, so this is a conservative cap rather than a claim
  of measured token consumption. It remains below the approved 1,520,000 /
  10,944 / $5.00 limits.

Judge disposition across all 159 rows:

| Disposition | Count |
|---|---:|
| LLM PASS | 133 |
| LLM FAIL | 18 |
| No final report, judge not run | 7 |
| Unparseable after the one permitted correction | 1 |

The unparseable result is the canonical Luna-xhigh `r24` row, run ID
`a9535fcb-336b-454d-97bd-1f943af2f8b3`. It remains in the dataset with
`report_accuracy=null` and `report_accuracy_method=llm_unparseable`; it was
not retried or replaced.

## Integrity and joins

- Frozen raw count/digest after all work: 159 /
  `337ad2c0c5289d999926147ae6a6b165b7e4f17b8a6ddfc6b1622717ef05b97c`.
- Derivatives: 159; every derivative is byte-identical to its raw artifact.
- Enriched rows: 159; resolved paths and run IDs are each unique.
- Canonical join: 150 rows with 150 unique
  `(model, effective_effort, round_id)` keys; both anti-joins are empty.
- Each of Luna/Terra low/xhigh/max has exactly 25 canonical rows. Native
  `xhigh` and explicit `max` remain separate groups.
- The two production-v1 `inference_error` rows and seven smoke rows remain
  audit-only.
- Existing inputs: all 1,475 still resolve to their original enriched rows.
- Combined enriched data: 1,775 rows. The prior 1,625 rows are an exact
  byte-for-byte prefix, followed only by the 150 canonical GPT-5.6 rows.
- Scratch inputs: 1,625 links with no missing enriched join.

The post-observation report-predicate correction disclosed in Step 4 is
visible but does not affect the production leaderboard selection. The
audit-only Terra-max v5 smoke raw artifact remains immutable with
`summary.coherent_report=false`; evaluation recomputes it as coherent and
strict/lenient success because its exact report says the net on-hand balance
increased by 2,004 credits. Sonnet's report judge returned `PASS`. The legacy
leaderboard baseline remained byte-identical, proving that this predicate
change did not alter any pre-existing leaderboard row.

## Canonical production results

| Model | Effort | N | Primary | Task complete | Trade | Path | Tools | Report | Turn P50 | Turn P90 | Total P50 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gpt-5.6-terra | xhigh | 25 | 92 | 100% | 7.4 | 15.0 | 14.7 | 15.0 | 2253.3 ms | 6374.1 ms | 136.56 s |
| gpt-5.6-terra | max | 25 | 92 | 100% | 8.4 | 15.0 | 14.3 | 15.0 | 3238.7 ms | 16364.3 ms | 263.17 s |
| gpt-5.6-terra | low | 25 | 89 | 100% | 4.2 | 14.4 | 14.9 | 14.9 | 1244.2 ms | 2824.5 ms | 84.24 s |
| gpt-5.6-luna | xhigh | 25 | 88 | 96% | 6.8 | 12.9 | 14.1 | 14.0 | 1490.2 ms | 5967.5 ms | 125.40 s |
| gpt-5.6-luna | max | 25 | 88 | 84% | 8.4 | 11.6 | 14.1 | 12.0 | 1467.1 ms | 10290.2 ms | 189.36 s |
| gpt-5.6-luna | low | 25 | 85 | 88% | 2.6 | 11.4 | 13.5 | 14.1 | 1165.2 ms | 2484.4 ms | 77.92 s |

Using the declared unrounded tie-break, `xhigh` is the best configuration for
both models. Terra xhigh ties max on primary and completion, then wins on
unrounded per-turn P50 (2253.35 ms versus 3238.73 ms). Luna xhigh ties max on
primary, then wins on completion (96% versus 84%). Both winners are below the
README's 4,000 ms cutoff.

## Staged publication diff

The scratch leaderboard changes only:

1. `Enriched scores` from
   `runs/leaderboard-natural-v1-refresh-20260716.jsonl` to
   `runs/leaderboard-natural-v1-refresh-20260718.jsonl`; and
2. the six GPT-5.6 rows in the table above.

Removing those six rows and restoring the old enriched-source line reproduces
the committed leaderboard byte-for-byte. The staged natural and
natural-filtered leaderboards are byte-identical. The separate README diff
adds only the two qualifying winner rows, `gpt-5.6-terra (xhigh)` and
`gpt-5.6-luna (xhigh)`.

Scratch files:

- `runs/step5-gpt56-20260718-scratch/leaderboard.diff`
- `runs/step5-gpt56-20260718-scratch/README.diff`
- `runs/step5-gpt56-20260718-scratch/validation.json`
- `runs/step5-gpt56-20260718-scratch/best-config-selection.json`

Key SHA-256 values:

| Artifact | SHA-256 |
|---|---|
| Judge enriched JSONL | `24a4650e949e50a7bcb3d6a5f17c68e3235032ef6f3d7095dafe185d381efed4` |
| Canonical GPT-5.6 enriched JSONL | `a4a6a88797050c961ab3880322b2d22866a1c3b0bc4c24afb4b50539db59b5a8` |
| Combined enriched JSONL | `c5ad6f9b8c4cc8e76b95b5391f3273d890e8e846f90d079f25f211d900b3d796` |
| Staged leaderboard | `68b26c31c967e8005d38ecf216d1f0067756e0380d5e822e27b95dc4cfe357cf` |
| Staged README | `64f595490f3360e8b9359e59c89162639dcddecce72e23cbc81a718fbf6052a7` |

## Publication closure

The user approved local publication, branch creation, and a scoped commit.
Publication installed the 1,625-input local set, the 1,775-row combined
enriched JSONL, the two byte-identical natural leaderboards, and the two-row
README update. A fresh builder run from the installed inputs and enriched data
is byte-identical to both published leaderboards at SHA-256
`68b26c31c967e8005d38ecf216d1f0067756e0380d5e822e27b95dc4cfe357cf`.

The first atomic exchange attempt rolled back before any tracked write. The
reason was that 53 of the 1,475 legacy inputs are regular ignored JSON files,
not symlinks; staging them as symlinks to their original paths made them
self-referential after directory exchange. The corrected staging preserved
those 53 entries as regular files and retained 1,572 symlinks. The
relocation-stable digest over entry name, entry type, external link target
when applicable, and content hash is
`ed824cda9cc86aec849ea44ca0095a48a38cbc3116055e1bf16cade8fae8aaed`.
The content set and canonical selection did not change.

The prior 1,475-input local set is retained at
`runs/leaderboard-natural-v1-input-pre-gpt56-20260718/` with digest
`7adb2cd7b8eb43177e354bcfe1e962a0325fb8ecdef597a4f95ab70b5b790cf4`.
All `runs/` material remains Git-ignored.

## Commit verification

- Full offline `unittest` selection: 235 passed, 52 skipped historical or
  retired validators.
- GPT-5.6 probe `pytest` module: 25 passed.
- The published-input builder regression uses the 1,625-input / 1,775-enriched
  pairing and reproduces the committed leaderboard bytes.
- The full live probe artifact is not a code dependency and is not included in
  the commit. Tests retain only the minimal sanitized Responses event sequence
  in `step1-gpt56-event-fixtures.json`.
