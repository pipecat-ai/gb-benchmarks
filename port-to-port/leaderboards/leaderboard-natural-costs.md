# Natural Leaderboard Cost Estimates

Pricing snapshot: 2026-08-13 (USD).

Estimated cost per completed task is mean representative cost per attempt divided by the official-judge Task Complete rate. API-provider estimates use all 25 canonical traces, regardless of where the benchmark ran. Cost per turn is aggregate estimated cost divided by all observed LLM turns in those traces. GPT-5.6 uses one sanity-checked sample.

| Model | Method | Cost samples | Task complete | Cost / turn | Cost / attempt | Est. cost / complete | Sample check | Provider |
|---|---|---:|---:|---:|---:|---:|---|---|
| grok-4.6 (high) | 25-run token usage | 25 | 100.0% | $0.0117 | $0.4062 | $0.4062 | n/a | xAI |
| grok-4.6 (low) | 25-run token usage | 25 | 100.0% | $0.0091 | $0.2926 | $0.2926 | n/a | xAI |
| gemini-3.7-flash (high) | 25-run token usage | 25 | 100.0% | $0.0074 | $0.2609 | $0.2609 | n/a | AI Studio |
| gemini-3.7-flash (medium) | 25-run token usage | 25 | 100.0% | $0.0072 | $0.2484 | $0.2484 | n/a | AI Studio |
| gemini-3.6-flash (high) | 25-run token usage | 25 | 100.0% | $0.0130 | $0.4487 | $0.4487 | n/a | AI Studio |
| gemini-3.5-flash (high) | 25-run token usage | 25 | 100.0% | $0.0148 | $0.5353 | $0.5353 | n/a | AI Studio |
| glm-5.2 (max) | 25-run token usage | 25 | 100.0% | $0.0050 | $0.1742 | $0.1742 | n/a | Baseten |
| claude-sonnet-5 (xhigh) | 25-run token usage | 25 | 100.0% | $0.0109 | $0.3837 | $0.3837 | n/a | Anthropic |
| kimi-2.6 (thinking) | 25-run token usage | 25 | 96.0% | $0.0039 | $0.1367 | $0.1424 | n/a | Baseten |
| deepseek-v4-flash-0731 (low) | 25-run token usage | 25 | 100.0% | $0.0009 | $0.0326 | $0.0326 | n/a | Baseten |
| deepseek-v4-flash-0731 (high) | 25-run token usage | 25 | 100.0% | $0.0010 | $0.0354 | $0.0354 | n/a | Baseten |
| deepseek-v4-pro-0813 (low) | 25-run token usage | 25 | 100.0% | $0.0095 | $0.3136 | $0.3136 | n/a | Baseten |
| claude-sonnet-4-6 (none) | 25-run token usage | 25 | 100.0% | $0.0086 | $0.2809 | $0.2809 | n/a | Anthropic |
| gpt-5.4 (low) | 25-run token usage | 25 | 100.0% | $0.0080 | $0.2564 | $0.2564 | n/a | OpenAI |
| gpt-5.6-terra (xhigh) | 1-run token sample | 1 | 100.0% | $0.0065 | $0.2217 | $0.2217 | pass | OpenAI |
| gpt-5.2 (medium) | 25-run token usage | 25 | 100.0% | $0.0051 | $0.1706 | $0.1706 | n/a | OpenAI |
| qwen3.6-27b (high) | 25-run token usage, price proxy | 25 | 100.0% | $0.0057 | $0.1940 | $0.1940 | n/a | OpenRouter |
| qwen3.6-35b-a3b (high, FP8) | 25-run token usage, price proxy | 25 | 100.0% | $0.0028 | $0.0970 | $0.0970 | n/a | OpenRouter |
| gemma-4-31b (thinking) | 25-run token usage | 25 | 100.0% | $0.0017 | $0.0512 | $0.0512 | n/a | AWS Bedrock |
| claude-haiku-4-5-20251001 (low) | 25-run token usage | 25 | 100.0% | $0.0037 | $0.1159 | $0.1159 | n/a | Anthropic |
| nemotron-3-ultra-550b (thinking) | 25-run token usage | 25 | 100.0% | $0.0092 | $0.2992 | $0.2992 | n/a | Baseten |
| gpt-5.1 (low) | 25-run token usage | 25 | 100.0% | $0.0056 | $0.1729 | $0.1729 | n/a | OpenAI |
| gpt-5.6-luna (xhigh) | 1-run token sample | 1 | 96.0% | $0.0033 | $0.1065 | $0.1110 | pass | OpenAI |
| poolside/laguna-s-2.1 (none) | 25-run token usage | 25 | 84.0% | $0.0003 | $0.0109 | $0.0130 | n/a | OpenRouter |
| gemini-3.5-flash-lite (high) | 25-run token usage | 25 | 100.0% | $0.0032 | $0.1132 | $0.1132 | n/a | AI Studio |
| inkling (low) | 25-run token usage | 25 | 100.0% | $0.0025 | $0.0735 | $0.0735 | n/a | Baseten |
| gpt-4.1 | 25-run token usage | 25 | 100.0% | $0.0066 | $0.2103 | $0.2103 | n/a | OpenAI |
| gemini-2.5-flash (2048) | 25-run token usage | 25 | 100.0% | $0.0017 | $0.0589 | $0.0589 | n/a | AI Studio |
| gemini-3.5-flash-lite (minimal) | 25-run token usage | 25 | 100.0% | $0.0035 | $0.1043 | $0.1043 | n/a | AI Studio |
| nemotron-3-super-120b (tb=512) | 25-run token usage | 25 | 100.0% | $0.0014 | $0.0439 | $0.0439 | n/a | OpenRouter |
| gpt-4o | 25-run token usage | 25 | 92.0% | $0.0134 | $0.4286 | $0.4659 | n/a | OpenAI |
| gemini-3.1-pro-preview (medium) | 25-run token usage | 25 | 100.0% | $0.0088 | $0.2873 | $0.2873 | n/a | AI Studio |
| qwen3.5-9b (thinking) | 25-run token usage | 25 | 56.0% | $0.0015 | $0.0576 | $0.1029 | n/a | OpenRouter |
| qwen3.5-27b (none) | 25-run token usage | 25 | 8.0% | $0.0031 | $0.1497 | $1.871 | n/a | OpenRouter |
| nemotron-3-super-120b (none) | 25-run token usage | 25 | 16.0% | $0.0013 | $0.0626 | $0.3913 | n/a | OpenRouter |
| qwen3.5-4b | 25-run token usage | 25 | 12.0% | $0.0006 | $0.0301 | $0.2509 | n/a | EmpirioLabs |
| glm-4.7-flash | 25-run token usage | 25 | 12.0% | $0.0008 | $0.0357 | $0.2975 | n/a | OpenRouter |

Notes:

- Grok 4.6 uses xAI's standard-context rates because every benchmark request remained below 200K input tokens; Responses output tokens already include billed reasoning tokens.
- Kimi K2.6 score, latency, and token usage all come from Baseten's public Model API; its cost uses that endpoint's public list price.
- Gemma 4 uses Amazon Bedrock US Standard on-demand pricing; Bedrock does not publish a separate cached-input rate for this model.
- Qwen 3.6 benchmark scores and latency come from Baseten single-H100 vLLM deployments. OpenRouter supplies same-model price proxies; the 27B estimate conservatively prices all input at the standard rate because historical traces do not expose API cache-read token buckets, and OpenRouter does not promise that its 35B serving precision matches the scored official FP8 checkpoint.
- Other self-hosted benchmark runs are priced against a public same-model API endpoint. OpenRouter supplies Nemotron Super, Qwen 3.5 9B/27B, and GLM 4.7 Flash prices; EmpirioLabs supplies Qwen 3.5 4B.
- Google reasoning tokens are billed as output. OpenAI-compatible reasoning tokens are already included in completion tokens. Anthropic base input, 5-minute cache-write, cache-read, and output buckets are priced separately.
- These are list-price workload estimates, not invoice reconciliation.
