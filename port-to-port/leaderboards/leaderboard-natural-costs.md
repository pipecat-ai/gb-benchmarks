# Natural Leaderboard Cost Estimates

Pricing snapshot: 2026-07-22 (USD).

Estimated cost per completed task is mean representative cost per attempt divided by the official-judge Task Complete rate. Token-priced APIs use all 25 canonical traces. GPT-5.6 uses one sanity-checked sample. Modal rows price the 25 canonical active-request traces; Modal estimates are GPU-only active-request cost and exclude between-request idle capacity, CPU, memory, credits, and discounts.

| Model | Method | Cost samples | Task complete | Cost / attempt | Est. cost / complete | Sample check |
|---|---|---:|---:|---:|---:|---|
| gemini-3.5-flash (high) | 25-run token usage | 25 | 100.0% | $0.5353 | $0.5353 | n/a |
| glm-5.2 (max) | 25-run token usage | 25 | 100.0% | $0.2275 | $0.2275 | n/a |
| claude-sonnet-5 (xhigh) | 25-run token usage | 25 | 100.0% | $0.3837 | $0.3837 | n/a |
| kimi-2.6 Cerebras (thinking) | 25-run token usage, price proxy | 25 | 100.0% | $0.1369 | $0.1369 | n/a |
| glm-5 (thinking) | 25-run GPU active time | 25 | 100.0% | $1.046 | $1.046 | n/a |
| claude-sonnet-4-6 (none) | 25-run token usage | 25 | 100.0% | $0.2809 | $0.2809 | n/a |
| gpt-5.4 (low) | 25-run token usage | 25 | 100.0% | $0.2564 | $0.2564 | n/a |
| gpt-5.6-terra (xhigh) | 1-run token sample | 1 | 100.0% | $0.2217 | $0.2217 | pass |
| gpt-5.2 (medium) | 25-run token usage | 25 | 100.0% | $0.1706 | $0.1706 | n/a |
| gemma-4-31b (thinking) | 25-run GPU active time | 25 | 100.0% | $0.0416–$0.0658 | $0.0416–$0.0658 | n/a |
| claude-haiku-4-5-20251001 (low) | 25-run token usage | 25 | 100.0% | $0.1159 | $0.1159 | n/a |
| nemotron-3-ultra-550b (thinking) | 25-run token usage | 25 | 100.0% | $0.2992 | $0.2992 | n/a |
| gpt-5.1 (low) | 25-run token usage | 25 | 100.0% | $0.1729 | $0.1729 | n/a |
| gpt-5.6-luna (xhigh) | 1-run token sample | 1 | 96.0% | $0.1065 | $0.1110 | pass |
| gemini-3.1-flash-lite-preview (high) | 25-run token usage | 25 | 100.0% | $0.0490 | $0.0490 | n/a |
| inkling (low) | 25-run token usage | 25 | 100.0% | $0.0735 | $0.0735 | n/a |
| gpt-4.1 | 25-run token usage | 25 | 100.0% | $0.2103 | $0.2103 | n/a |
| gemini-2.5-flash (2048) | 25-run token usage | 25 | 100.0% | $0.0589 | $0.0589 | n/a |
| nemotron-3-super-120b (tb=512) | 25-run GPU active time | 25 | 100.0% | $0.5479 | $0.5479 | n/a |
| gpt-4o | 25-run token usage | 25 | 92.0% | $0.4286 | $0.4659 | n/a |
| gemini-3.1-pro-preview (medium) | 25-run token usage | 25 | 100.0% | $0.2873 | $0.2873 | n/a |
| qwen3.5-9b (thinking) | 25-run GPU active time | 25 | 56.0% | $0.3634 | $0.6489 | n/a |
| qwen3.5-27b (none) | 25-run GPU active time | 25 | 8.0% | $0.2262 | $2.828 | n/a |
| nemotron-3-super-120b (none) | 25-run GPU active time | 25 | 16.0% | $0.3303 | $2.064 | n/a |
| qwen3.5-4b | 25-run GPU active time | 25 | 12.0% | $0.1672 | $1.393 | n/a |
| glm-4.7-flash | 25-run GPU active time | 25 | 12.0% | $0.2178 | $1.815 | n/a |

Notes:

- Kimi K2.6 uses Baseten's public Kimi K2.6 token price as a market proxy; the measured Cerebras dedicated-endpoint contract is not public.
- Gemma 4 is shown as a range: the configured two-A100 primary allocation through the two-H100 fallback.
- Google reasoning tokens are billed as output. OpenAI-compatible reasoning tokens are already included in completion tokens. Anthropic base input, 5-minute cache-write, cache-read, and output buckets are priced separately.
- These are list-price workload estimates, not invoice reconciliation.
