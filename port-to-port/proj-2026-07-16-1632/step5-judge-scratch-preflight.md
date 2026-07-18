# Step 5 judge-all and scratch-leaderboard preflight

Status: **READY FOR USER APPROVAL; NO JUDGE CALL AUTHORIZED YET**

Date: 2026-07-18

## Scope

This package performs the non-publishing portion of Step 5. It will:

1. create normalized derivative copies of all 159 preserved GPT-5.6 run JSONs;
2. evaluate every derivative with `evaluate_runs.py` and
   `claude-sonnet-4-6` as the report-accuracy judge;
3. retain enriched rows for all 159 derivatives, including the two preserved
   production-v1 infrastructure artifacts and the five production model
   outcomes that exhausted the benchmark turn limit;
4. select only the production-v3 manifest's 150 canonical rows for leaderboard
   staging;
5. enforce one-to-one `(model, effective_effort, round_id)` joins and both
   anti-joins;
6. combine the 150 canonical enriched rows with the existing 1,625-row natural
   enriched dataset in a scratch tree; and
7. build and show scratch leaderboard and README diffs for a later publishing
   decision.

This package does not run Luna, Terra, Sol, or any other benchmark model. It
does not alter raw run JSON/log files, the production state or manifest, the
canonical leaderboard input directory, either committed leaderboard, or the
repository README. Publishing remains a separate approval boundary because
the resulting bytes do not exist yet.

## Bound input set

The input set is exactly the 159 files matching `runs/gpt56-*.json` at
preflight time:

- 150 production-core-v3 artifacts;
- two preserved production-v1 infrastructure artifacts;
- six core smoke artifacts; and
- one parallel-replay-v6 smoke artifact.

There are 152 artifacts with a final `finished` report and seven without one.
`evaluate_runs.py` only calls the LLM report judge for artifacts with a final
report, but all 159 artifacts receive an enriched row.

The bound-set digest is SHA-256
`337ad2c0c5289d999926147ae6a6b165b7e4f17b8a6ddfc6b1622717ef05b97c`
over the UTF-8 sequence of sorted lines
`<relative-path>\t<file-sha256>\n`. The worker must recompute this digest and
the 159-file count before extracting `ANTHROPIC_API_KEY`; any mismatch stops
before client construction.

The canonical selector is
`proj-2026-07-16-1632/step4-core-production-v3-runner-state.json` at SHA-256
`50207b5359d2647aba6bac5d2036c4ed52cf54f2c4342c95ed335d4594ec6888`.
Its corresponding manifest is
`proj-2026-07-16-1632/core-production-v3-manifest.json` at SHA-256
`ce4479626a2031c66514d22c181e6b5078d16fe4efcfa975613bdd8d5015c076`.
Both contain 150 attempts and 150 canonical selections, exactly 25 for each
Luna/Terra low/xhigh/max configuration.

## Reproducibility baseline

Before adding GPT-5.6, the updated builder was run against the existing
`runs/leaderboard-natural-v1-input/*.json` and
`runs/leaderboard-natural-v1-refresh-20260716.jsonl`. The scratch rebuild is
byte-identical to `leaderboards/leaderboard-natural.md`; both have SHA-256
`dd8d00c01adf316abe2a390fb8222b1bfdcd5df675093604dda4faff1f5e7da7`.
The committed natural and natural-filtered leaderboards are also byte-identical.

## Judge request and budget bounds

The judge uses the Anthropic Messages API with model
`claude-sonnet-4-6`, temperature zero, a 30-second per-request timeout, and a
64-token output cap. The verdict parser accepts `PASS` or `FAIL`; only an
unparseable response permits one follow-up request capped at eight output
tokens. Network errors are retained as unavailable judge results and are not
retried by the evaluator.

Therefore the package permits:

- at most 152 initial judge requests;
- at most 152 parse-correction requests;
- at most 304 total Anthropic requests;
- at most 5,000 input tokens reserved per request, or 1,520,000 input tokens;
- at most 10,944 output tokens (`152 × (64 + 8)`);
- at most $5.00 estimated judge cost; and
- at most 9,120 accounted request-timeout seconds (`304 × 30`).

The longest final report in the bound set is 560 UTF-8 bytes, so the 5,000
input-token reservation per request conservatively dominates the fixed judge
rubric, ground-truth JSON, report, and parse-correction suffix. At the current
Sonnet 4.6 standard rates of $3 per million input tokens and $15 per million
output tokens, the full token reservations project $4.72416. Pricing source,
retrieved 2026-07-18:
`https://www.anthropic.com/claude/sonnet`. The command gets an outer
10,000-second timeout. No request may be added after the 304-request maximum,
and unused headroom is not authority for another judge model, a benchmark run,
or publishing.

## Non-destructive outputs and validation

All new files stay under fresh scratch paths:

- `runs/leaderboard-derivatives-gpt56-20260718/`;
- `runs/eval-gpt56-20260718/`;
- `runs/step5-gpt56-20260718-scratch/`; and
- `proj-2026-07-16-1632/step5-validation.md`.

The derivative step refuses pre-existing destination files. Raw file hashes
are checked before and after derivative creation and judging. Since the raw
models already use the exact house labels `gpt-5.6-luna` and
`gpt-5.6-terra`, normalization preserves those labels and changes no benchmark
outcome data.

Validation must prove:

- 159 raw JSONs = 159 derivatives = 159 enriched rows;
- all resolved derivative paths and all run IDs are unique;
- the two production-v1 infrastructure rows remain audit-only;
- the canonical join contains exactly 150 rows, 25 per config;
- every `(model, effective_effort, round_id)` key is unique on both sides;
- native xhigh and explicit max remain distinct `N=25` groups;
- the existing 1,625 enriched rows are a byte-identical prefix of the scratch
  combined dataset;
- all 1,475 existing leaderboard inputs still resolve to their original
  enriched rows; and
- the scratch diff changes only the six GPT-5.6 rows and the expected enriched
  source line.

The best configuration for each model is selected from unrounded canonical
statistics by highest primary median, then task-complete rate, then lowest
per-turn P50, then lexicographic effective effort. A README row is staged only
when that winner's unrounded P50 is below 4,000 ms. No staged bytes are copied
to canonical paths without a second, explicit publishing approval after the
diffs are shown.

## Approval text

> I approve Step 5 judge-all and scratch-leaderboard validation exactly as
> documented in step5-judge-scratch-preflight.md, limited to the bound set of
> 159 GPT-5.6 derivative artifacts, at most 304 sequential
> claude-sonnet-4-6 judge requests, 1,520,000 input tokens, 10,944 output
> tokens, $5.00, and 9,120 request-timeout seconds. Benchmark model runs, Sol,
> retries other than the documented parse correction, canonical leaderboard
> input mutation, committed leaderboard writes, README writes, and publishing
> remain unauthorized.
