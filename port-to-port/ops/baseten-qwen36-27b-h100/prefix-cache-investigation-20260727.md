# Qwen3.6 hybrid prefix-cache investigation

Date: 2026-07-27

## Scope

The original single-H100 deployment used vLLM 0.20.0 with MTP speculative
decoding. Enabling automatic prefix caching on that stack produced duplicated
automatic tool calls and malformed forced tool-call output. Disabling prefix
caching restored protocol correctness.

## Upstream status

- [vLLM 0.26.0](https://github.com/vllm-project/vllm/releases/tag/v0.26.0)
  is the latest stable release as of this investigation.
- Mamba/Gated DeltaNet `align`-mode prefix caching was merged in
  [#30877](https://github.com/vllm-project/vllm/pull/30877).
- Model Runner V2 support for hybrid `align` prefix caching was merged in
  [#42406](https://github.com/vllm-project/vllm/pull/42406).
- Fine-grained hybrid prefix-hit convergence and copy-on-write were merged in
  [#46384](https://github.com/vllm-project/vllm/pull/46384).
- Selective hybrid-cache retention was fixed in
  [#47782](https://github.com/vllm-project/vllm/pull/47782).
- Upstream's proposed end-to-end corruption tests
  [#48970](https://github.com/vllm-project/vllm/pull/48970) report that current
  `main` is green because #46384 and #47782 contain the production fixes.

Several related patches remain open, including
[#42792](https://github.com/vllm-project/vllm/pull/42792) and
[#43650](https://github.com/vllm-project/vllm/pull/43650). They are draft or
stale against older `main` revisions, so none was applied directly. The stable
release must be tested before considering an unmerged backport.

## v0.26.0 prefix-cache control: MTP disabled

Configuration:

- one H100, BF16, tensor parallelism 1;
- vLLM 0.26.0;
- `--enable-prefix-caching`;
- `--mamba-cache-mode align`;
- MTP disabled.

Results:

- five of five short protocol suites passed;
- two of two 29K-token shared-prefix suites passed;
- streamed text, forced tools, automatic tools, and reasoning-preserving
  continuation were correct in every suite;
- no duplicated, malformed, or leaked tool call was observed;
- vLLM metrics reported 170,912 local cached tokens from 238,080 prefix-query
  tokens, a 71.8% hit rate;
- the repeated long-prefix text request improved from 3.38 seconds to
  0.88 seconds.

The original short protocol prompts were smaller than the hybrid cache's
effective match granularity and therefore recorded no cache hits. The 29K-token
probe is the correctness test that demonstrates actual cached execution.

## v0.26.0 prefix cache with MTP

Configuration:

- one H100, BF16, tensor parallelism 1;
- vLLM 0.26.0;
- `--enable-prefix-caching`;
- `--mamba-cache-mode align`;
- MTP speculative decoding with two speculative tokens.

Results:

- five of five 29K-token shared-prefix suites passed;
- all 20 constituent checks passed: streamed text, forced tools, automatic
  tools, and reasoning-preserving continuation;
- no duplicated, malformed, or leaked tool call was observed;
- vLLM metrics reported 500,800 local cached tokens from 579,305 prefix-query
  tokens, an 86.4% hit rate;
- the first long-prefix text request took 7.07 seconds and warmed repetitions
  took about 0.82 seconds;
- a full `thinking=high` benchmark episode completed successfully in 32 turns,
  with no bad actions or no-tool turns;
- the official judge scored that episode 92/100: trade 7/15, path 15/15, tools
  15/15, and report 15/15;
- benchmark turn latency was 1.35 seconds at P50 and 5.69 seconds at P90.
  Four of 32 turns exceeded four seconds, all while producing longer reasoning
  for trade, recharge, or the final report.

The stable v0.26.0 release fixes the protocol corruption seen with v0.20.0 for
this tested workload. No unmerged patch is needed. The remaining draft or stale
patches should not be backported unless a new reproducible failure demonstrates
that the merged fixes are insufficient.

## `thinking=none` benchmark result

The v0.20.0 no-prefix-cache deployment was also tested for three sequential
episodes with reasoning disabled:

- official median score: 53/100;
- task completion: one of three episodes (33.3%);
- warm turn latency: 2.61 seconds at P50 and 4.34 seconds at P90;
- 21 of 139 warm turns (15.1%) exceeded four seconds;
- the two failures exhausted all 50 turns, with 14 and 19 no-tool narration
  turns respectively.

Disabling reasoning therefore does not meet the quality requirement and still
does not enforce a hard four-second turn limit. Use the v0.26.0 cached
`thinking=high` configuration for any further Qwen3.6 27B work.

## Cached MTP `high` versus `none`

The v0.26.0 prefix-cache-plus-MTP deployment was subsequently tested with
three valid sequential episodes per reasoning mode. The existing validated
`high` episode was retained, and the remaining episodes were interleaved on
the same warm replica.

| Configuration | N | Score | Completion | Turn P50 | Turn P90 | Turns over 4s |
|---|---:|---:|---:|---:|---:|---:|
| cached MTP, `high` | 3 | 92 | 100% | 1.43s | 7.16s | 15/99 (15.2%) |
| cached MTP, `none` | 3 | 72 | 66.7% | 0.99s | 2.15s | 4/148 (2.7%) |

The `high` runs scored 92, 100, and 91. All three completed in 32--34 turns,
made a tool call on every turn, and had zero no-tool turns. Their median total
episode time was 126.76 seconds.

The `none` runs scored 77, 52, and 72. They used 48--50 turns and produced
56 no-tool narration turns across 148 total turns (37.8%). One run returned
to the starting sector on turn 49 but narrated on turn 50 instead of calling
`finished`, so it correctly failed strict completion. Median total episode
time was 213.58 seconds despite the lower per-turn latency.

One `none` attempt stalled in the Baseten serving path at turn 46 and caused
the immediately queued `high` attempt to stall before its first turn. Both
were interrupted, preserved as diagnostic artifacts, excluded from the
canonical comparison, and replaced. The vLLM metrics subsequently showed zero
running or waiting requests, and a small health request succeeded before the
replacement runs. No malformed, duplicated, or leaked tool call occurred in
any valid episode.

This comparison confirms that disabling reasoning is not a viable latency
optimization for this benchmark. Cached MTP `high` is the recommended
configuration: it preserves reliable tool use and completion while keeping
typical turns well below four seconds. Prefix caching and MTP cannot eliminate
the remaining reasoning-heavy latency tail.
