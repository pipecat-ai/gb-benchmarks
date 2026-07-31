# Inkling Small on Baseten — port-to-port notes

_Added 2026-07-31. Integrated, benchmarked, and added to the full natural
leaderboard._

## Model and endpoint

[Thinking Machines describes Inkling Small](https://thinkingmachines.ai/news/introducing-inkling/)
as a preview 276B-parameter MoE with 12B active parameters. Baseten serves it
from the same OpenAI-compatible Model API used for the larger Inkling:

- base URL: `https://inference.baseten.co/v1`
- model: `thinkingmachines/inkling-small`
- live metadata on 2026-07-31: FP8, 1M-token context, 32,768-token maximum
  completion, tool calling, structured output, and reasoning support

A direct streaming smoke test verified a tool call, arguments, tool-result
continuation, and a final streamed response before benchmark collection.

## Harness and sweep

Inkling Small uses the existing Inkling-specific Baseten path: native top-level
`reasoning_effort`, `temperature=1`, automatic cache accounting, transport
retries, and `max_tokens=16384`. Exact model matching keeps this behavior from
leaking into other OpenAI-compatible models. Benchmark levels map as usual:
`low -> low`, `high -> high`, and `xhigh -> max`.

```bash
CONFIG_FILTER=inkling-small-low,inkling-small-high,inkling-small-max \
ROUNDS=25 bash run_baseten_sweep.sh
```

All runs used the natural v1 prompt (`68d2c77b...`), 50 turns, a 20-second
function-call timeout, and strictly sequential requests to the shared Baseten
endpoint. Failed tasks remained in their original 25-run cohorts and were
judged rather than replaced.

## Official results

Judged with `claude-sonnet-4-6`.

| Config | Primary /100 | Task Complete | Trade /15 | Path /15 | Tools /15 | Report /15 | Turn P50 | Turn P90 | Total P50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Inkling Small (high) | **79** | **76%** | 2.8 | 13.7 | 7.7 | 10.8 | 411 ms | 476 ms | 66.1 s |
| Inkling Small (max) | 44 | 20% | 2.3 | 13.7 | 5.6 | 2.8 | 416 ms | 486 ms | 73.2 s |
| Inkling Small (low) | 43 | 0% | 0.0 | 14.4 | 14.5 | 12.6 | 378 ms | 622 ms | 8.0 s |

The high configuration is the clear default for this task, but its score of 79
falls just below the README's curated 80-point floor. All three configurations
remain in the full natural leaderboard.

## What happened

- **Low gives up early.** All 25 runs called `finished`, but none found and
  completed the mega-port round trip. The model emitted no reasoning tokens at
  this level and usually stopped after only a few turns.
- **High is capable but brittle.** Nineteen runs completed the task; six reached
  the 50-turn cap. Repeated speculative trades account for much of the weak tool
  discipline and trading score.
- **Max over-operates.** Twenty of 25 runs exhausted 50 turns. More reasoning did
  not improve planning discipline: max completed only five tasks.
- **The service was robust and very fast.** Across all 75 production episodes
  there were no empty responses, rate limits, asynchronous tool timeouts, or
  missing JSON artifacts. Every cohort's turn P90 stayed below 0.7 seconds.
- **Reasoning was sparse even when enabled.** High recorded 688 reasoning tokens
  over 17 of 1,120 turns; max recorded 1,458 over 25 of 1,240 turns. Low recorded
  none. This confirms that the native effort control changes behavior, but the
  extra reasoning is concentrated in very few turns.
- **Automatic prefix caching worked.** Cache reads accounted for about 96% of
  low input tokens and 98% of high/max input tokens. Baseten's authenticated
  `/v1/models` response advertised zero prompt, cached-input, and output rates
  for this preview on 2026-07-31; treat that as provisional rather than a durable
  list price.

The practical takeaway is that Inkling Small is an excellent-latency endpoint,
but this benchmark exposes a long-horizon control gap relative to the larger
Inkling, whose low configuration scored 86 with 100% completion.
