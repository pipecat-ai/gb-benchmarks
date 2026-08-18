# Primary Leaderboard Summary (11 Columns)

- Leaderboard prompt: `natural`
- Prompt hash: `68d2c77be6548b77cd2e65ca0489edb2080c4a652feeb11f5ef5317f91e4b1f0`
- Score rubric version: `port_to_port_primary_v1`
- Aggregation: Primary=median, Task Complete=rate, Trade/Path/Tools/Report=mean
- Source runs: `runs/leaderboard-natural-v2-linked-qwen36-27b-35b-inkling-small-20260731/*.json`, `runs/muse-glimmer-30b-natural-high-card-nomax-dflash15-n25-20260810T213830Z/raw/*.json`, `runs/nemotron-3.5-lightning-natural-*-sglang-20260811T223912Z-r*.json`, `runs/nemotron-3-nano-30b-nvfp4-natural-*-sglang-prod-native-20260812T192200Z-r*.json`, `runs/deepseek-v4-baseten-full3-20260818T044040Z/{flash-low,flash-high,pro0813-low}/*.json`, `runs/gemini37-flash-production-20260813T194708Z/{high,medium}/raw/*.json`, `runs/grok-4.6-xai-{low,high}-production-*/*.json`, `runs/gemini35-flash-lite-replacement-20260814T153547Z/production-high/raw/*.json`, and `runs/qwen38-local-sglang-max12-production-r2-gb-{low,xhigh}-r*-a01-v1.json`
- Enriched scores: `runs/leaderboard-natural-v2-linked-refresh-qwen36-27b-35b-inkling-small-20260731.jsonl`, `runs/muse-glimmer-30b-natural-high-card-nomax-dflash15-n25-20260810T213830Z/eval/enriched_runs.jsonl`, `runs/eval-nemotron-3.5-lightning-natural-*-sglang-20260811T223912Z/enriched_runs.jsonl`, `runs/eval-nemotron3-nano-native-prod-20260812T192200Z/enriched_runs.jsonl`, `runs/deepseek-v4-baseten-full3-20260818T044040Z/{eval-flash-low,eval-flash-high,eval-pro0813-low}/enriched_runs.jsonl`, `runs/gemini37-flash-production-20260813T194708Z/publication/enriched_runs.jsonl`, `runs/eval-grok-4.6-xai-{low,high}-production-*/enriched_runs.jsonl`, `runs/gemini35-flash-lite-replacement-20260814T153547Z/production-high/eval/enriched_runs.jsonl`, and `runs/eval-qwen38-local-sglang-max12-production-r2-gb-{low,xhigh}-v1/enriched_runs.jsonl`
- Sort: Primary /100 desc, Task Complete % desc, Total Time P50 (s) asc

Gemini 3.7 Flash uses the exact Google AI Studio model ID and native `thinking_level`; this model supports `low`, `medium`, and `high` but not `minimal`. The high and medium rows are independent 25-run cohorts with no output-token cap or sampling override. Pricing is not part of this score table; see the companion cost leaderboard for Google’s introductory rate through December 31, 2026.

Gemini 3.5 Flash-Lite uses Google's stable `gemini-3.5-flash-lite` model ID and native `thinking_level`, with no output-token cap or sampling override. A judged five-run sweep selected high over medium (92 versus 89, both 100% complete); the independent N=25 high cohort scored 91 with 100% task completion. The retired `gemini-3.1-flash-lite-preview` rows have been removed.

Kimi K2.6 uses Baseten's public Model API with the exact `moonshotai/Kimi-K2.6` slug and binary native thinking. Thinking used the model-card sampling values `temperature=1.0` and `top_p=0.95`; instant mode used `temperature=0.6` and `top_p=0.95`. Both rows are independent 25-run cohorts with no output-token cap. One run in each cohort exhausted the benchmark's 50-turn limit and was retained and judged. Pricing is not part of this score table; see the companion cost leaderboard for the measured Baseten token cost.

Grok 4.6 uses xAI's exact `grok-4.6` model ID and native `reasoning.effort` through the Responses API. Requests used stateful `previous_response_id` chaining, one stable `prompt_cache_key` per conversation, no sampling override, and no output-token cap. Independent N=25 cohorts scored 99 at high and 92 at low, both with 100% task completion. Pricing is not part of this score table; see the companion cost leaderboard for xAI's measured token cost.

The local Nemotron rows used official NVIDIA NVFP4 checkpoints on one RTX 5090 with SGLang and binary native thinking, without a thinking-token budget. Nano used a 262,144-token context, `max_tokens=10000`, model-card tool sampling (`temperature=0.6`, `top_p=0.95`) when thinking was on, greedy decoding when off, and a cache flush between conversations. Lightning used `temperature=1.0`, `top_p=0.95`, no output-token ceiling, and did not flush between conversations, so its latency regime is not identical to Nano's.

DeepSeek V4 Flash 0731 and V4 Pro 0813 were independent judged N=25 cohorts through Baseten's Model API, with native `reasoning_effort`, temperature 1.0, model-default top-p, and `max_tokens=8192`. Flash low and Pro low each scored 97 with 100% completion; Flash high scored 95 with 100% completion.

The local Qwen 3.8 rows used the community Unsloth `Qwen3.8-27B-NVFP4` checkpoint on one RTX 5090 with pinned SGLang, a 32,768-token context, BF16 KV cache, radix prefix caching, and no output-token cap. The 68% and 60% completion rates are no-tool reasoning stalls against that context ceiling; runaway reasoning is measured rather than capped. See `proj-2026-08-14-qwen38-27b-fp8-baseten/`.

| Model | N | Primary /100 | Task Complete % | Trade /15 Avg | Path /15 Avg | Tools /15 Avg | Report /15 Avg | Turn P50 (ms) | Turn P90 (ms) | Total Time P50 (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| grok-4.6 (th=high, base=api.x.ai) | 25 | 99 | 100.0% | 15.0 | 15.0 | 15.0 | 15.0 | 1690.1 | 5550.2 | 155.75 |
| gemini-3.7-flash (th=high) | 25 | 97 | 100.0% | 10.7 | 15.0 | 14.4 | 15.0 | 1143.2 | 3145.7 | 97.03 |
| gemini-3.6-flash (th=high) | 25 | 97 | 100.0% | 9.2 | 15.0 | 15.0 | 15.0 | 1176.2 | 3498.5 | 97.07 |
| deepseek-ai/DeepSeek-V4-Flash-0731 (th=low, mt=8192, base=inference.baseten.co) | 25 | 97 | 100.0% | 12.4 | 15.0 | 14.0 | 15.0 | 859.1 | 3268.6 | 98.93 |
| deepseek-ai/DeepSeek-V4-Pro-0813 (th=low, mt=8192, base=inference.baseten.co) | 25 | 97 | 100.0% | 10.7 | 14.7 | 14.8 | 15.0 | 1255.0 | 13914.4 | 178.56 |
| glm-5.2 (th=xhigh, mt=8192, base=inference.baseten.co) | 25 | 97 | 100.0% | 11.0 | 14.8 | 14.3 | 14.8 | 1190.8 | 14458.6 | 212.72 |
| gpt-5.4 (th=medium, mt=4096) | 25 | 97 | 100.0% | 12.2 | 15.0 | 15.0 | 14.9 | 6309.5 | 25817.6 | 347.89 |
| moonshotai/Kimi-K2.6 (th=high, base=inference.baseten.co) | 25 | 97 | 96.0% | 10.5 | 14.8 | 14.4 | 14.4 | 1034.0 | 3221.8 | 99.07 |
| deepseek-ai/DeepSeek-V4-Flash-0731 (th=high, mt=8192, base=inference.baseten.co) | 25 | 95 | 100.0% | 12.2 | 15.0 | 12.8 | 14.8 | 860.9 | 4866.8 | 121.98 |
| glm-5.2 (th=high, mt=8192, base=inference.baseten.co) | 25 | 94 | 100.0% | 10.2 | 14.7 | 15.0 | 14.9 | 809.4 | 6025.9 | 117.31 |
| claude-sonnet-5 (th=xhigh) | 25 | 93 | 100.0% | 9.6 | 15.0 | 14.1 | 15.0 | 2527.3 | 13172.9 | 246.87 |
| gemini-3.7-flash (th=medium) | 25 | 92 | 100.0% | 10.6 | 15.0 | 14.8 | 15.0 | 1013.0 | 2196.7 | 79.51 |
| glm-5.2 (th=none, mt=8192, base=inference.baseten.co) | 25 | 92 | 100.0% | 8.9 | 14.5 | 14.8 | 14.9 | 784.6 | 2447.0 | 80.42 |
| gemini-3.6-flash (th=low) | 25 | 92 | 100.0% | 8.7 | 14.7 | 14.9 | 15.0 | 1020.2 | 2186.8 | 81.51 |
| gemini-3.6-flash (th=medium) | 25 | 92 | 100.0% | 9.0 | 15.0 | 14.9 | 15.0 | 1111.3 | 2904.5 | 90.13 |
| grok-4.6 (th=low, base=api.x.ai) | 25 | 92 | 100.0% | 7.0 | 15.0 | 15.0 | 15.0 | 1376.1 | 3362.2 | 96.10 |
| glm-5-fp8 (th=high, mt=4096, base=daily--glm5-sglang-serve.modal.run) | 25 | 92 | 100.0% | 5.9 | 14.8 | 15.0 | 14.9 | 1420.1 | 4623.0 | 107.98 |
| claude-sonnet-4-6 (th=none) | 25 | 92 | 100.0% | 8.2 | 15.0 | 14.5 | 13.6 | 1998.1 | 4948.2 | 125.53 |
| gpt-5.4 (th=low, mt=4096) | 25 | 92 | 100.0% | 7.6 | 15.0 | 15.0 | 14.9 | 2433.8 | 10455.4 | 136.22 |
| gpt-5.6-terra (eff=xhigh, mt=50000) | 25 | 92 | 100.0% | 7.4 | 15.0 | 14.7 | 15.0 | 2253.3 | 6374.1 | 136.56 |
| claude-sonnet-5 (th=medium) | 25 | 92 | 100.0% | 6.1 | 15.0 | 14.9 | 15.0 | 2160.9 | 6969.5 | 137.68 |
| claude-sonnet-5 (th=high) | 25 | 92 | 100.0% | 8.1 | 15.0 | 14.4 | 15.0 | 2354.7 | 9222.9 | 193.52 |
| claude-sonnet-4-6 (th=medium) | 25 | 92 | 100.0% | 9.3 | 15.0 | 13.6 | 15.0 | 2452.7 | 10638.6 | 200.09 |
| gpt-5.6-terra (eff=max, mt=50000) | 25 | 92 | 100.0% | 8.4 | 15.0 | 14.3 | 15.0 | 3238.7 | 16364.3 | 263.17 |
| gpt-5.1 (th=medium) | 25 | 92 | 100.0% | 8.0 | 15.0 | 15.0 | 14.2 | 13615.7 | 49692.4 | 647.86 |
| gemini-3.5-flash-lite (th=high) | 25 | 91 | 100.0% | 7.0 | 15.0 | 15.0 | 15.0 | 786.9 | 1710.7 | 71.85 |
| gpt-5.2 (th=medium) | 25 | 91 | 100.0% | 6.5 | 14.8 | 14.1 | 14.6 | 1047.9 | 10482.2 | 149.98 |
| claude-sonnet-4-6 (th=low) | 25 | 90 | 100.0% | 5.8 | 15.0 | 13.6 | 14.6 | 1957.0 | 6899.5 | 139.09 |
| Qwen/Qwen3.6-27B (th=high, mt=4096, base=model-w67n482q.api.baseten.co/deployment/wxpnlg5/sync) | 25 | 90 | 100.0% | 6.6 | 14.5 | 14.5 | 14.9 | 1611.2 | 7699.3 | 144.80 |
| gemma-4-31b (th=high, mt=4096, base=daily--gemma4-31b-vllm.modal.run) | 25 | 89 | 100.0% | 4.0 | 15.0 | 15.0 | 15.0 | 850.6 | 1065.5 | 60.43 |
| gpt-5.6-terra (eff=low, mt=50000) | 25 | 89 | 100.0% | 4.2 | 14.4 | 14.9 | 14.9 | 1244.2 | 2824.5 | 84.24 |
| claude-sonnet-5 (th=low) | 25 | 89 | 100.0% | 4.3 | 14.8 | 15.0 | 15.0 | 2068.8 | 5695.2 | 119.40 |
| claude-haiku-4-5-20251001 (th=low) | 25 | 89 | 100.0% | 4.3 | 14.1 | 14.4 | 14.8 | 2157.9 | 6863.1 | 125.41 |
| claude-sonnet-5 (th=none) | 25 | 89 | 100.0% | 6.1 | 14.0 | 14.6 | 15.0 | 2543.8 | 10036.0 | 189.48 |
| qwen3.5-27b (th=high, mt=4096, base=daily--qwen35-sglang-serve-27b.modal.run) | 25 | 89 | 100.0% | 5.4 | 14.3 | 14.8 | 15.0 | 4281.0 | 11008.7 | 200.22 |
| moonshotai/Kimi-K2.6 (th=none, base=inference.baseten.co) | 25 | 89 | 96.0% | 5.8 | 14.1 | 14.3 | 13.5 | 604.8 | 1466.8 | 67.63 |
| nemotron-3-ultra-550b (th=high, mt=8192, base=inference.baseten.co) | 25 | 88 | 100.0% | 4.6 | 13.2 | 14.9 | 14.0 | 989.3 | 2817.5 | 81.03 |
| Qwen/Qwen3.6-35B-A3B-FP8 (th=high, mt=4096, base=model-qzkm8mpq.api.baseten.co/deployment/qe20zvr/sync) | 25 | 88 | 100.0% | 5.3 | 13.6 | 13.4 | 15.0 | 1091.1 | 4003.3 | 101.04 |
| gpt-5.1 (th=low) | 25 | 88 | 100.0% | 4.2 | 15.0 | 14.8 | 14.4 | 1798.2 | 12660.8 | 162.69 |
| gpt-5.6-luna (eff=xhigh, mt=50000) | 25 | 88 | 96.0% | 6.8 | 12.9 | 14.1 | 14.0 | 1490.2 | 5967.5 | 125.40 |
| poolside/laguna-s-2.1 (th=none, mt=4096, base=openrouter.ai/api) | 25 | 88 | 84.0% | 4.8 | 12.0 | 14.4 | 12.0 | 834.0 | 2592.3 | 93.44 |
| gpt-5.6-luna (eff=max, mt=50000) | 25 | 88 | 84.0% | 8.4 | 11.6 | 14.1 | 12.0 | 1467.1 | 10290.2 | 189.36 |
| qwen3.8-27b-nvfp4-unsloth (th=low, base=127.0.0.1:30186) | 25 | 88 | 68.0% | 6.5 | 14.7 | 8.3 | 10.2 | 3139.6 | 21740.0 | 371.18 |
| gpt-5.6-sol (eff=medium, mt=16384) | 25 | 87 | 100.0% | 3.6 | 15.0 | 14.8 | 14.8 | 1809.4 | 4705.2 | 116.62 |
| claude-haiku-4-5-20251001 (th=medium) | 25 | 87 | 100.0% | 3.3 | 14.2 | 14.4 | 14.8 | 2151.4 | 7263.9 | 131.10 |
| gpt-5.4 (th=none, mt=4096) | 25 | 87 | 96.0% | 4.0 | 14.0 | 14.6 | 14.6 | 1206.0 | 2547.9 | 50.23 |
| muse-glimmer-30b (th=high, base=127.0.0.1:8080) | 25 | 87 | 92.0% | 4.1 | 14.1 | 13.0 | 13.7 | 487.0 | 9429.3 | 166.07 |
| qwen3.8-27b-nvfp4-unsloth (th=xhigh, base=127.0.0.1:30186) | 25 | 87 | 60.0% | 7.4 | 15.0 | 10.4 | 9.0 | 2529.8 | 22390.0 | 352.03 |
| inkling (th=low, mt=16384, base=inference.baseten.co) | 25 | 86 | 100.0% | 2.6 | 15.0 | 13.7 | 14.6 | 594.0 | 1337.1 | 57.16 |
| gpt-4.1 (th=medium) | 25 | 86 | 100.0% | 2.4 | 14.3 | 14.4 | 13.7 | 805.9 | 1395.4 | 61.33 |
| inkling (th=high, mt=16384, base=inference.baseten.co) | 25 | 86 | 100.0% | 3.2 | 14.8 | 13.2 | 14.5 | 605.6 | 3402.2 | 111.73 |
| inkling (th=xhigh, mt=16384, base=inference.baseten.co) | 25 | 86 | 100.0% | 2.8 | 15.0 | 13.2 | 14.7 | 606.1 | 3155.9 | 129.79 |
| gpt-4.1 (th=low) | 25 | 85 | 100.0% | 2.4 | 14.8 | 14.0 | 14.0 | 814.5 | 1455.0 | 63.23 |
| gpt-5.6-sol (eff=none, mt=16384) | 25 | 85 | 100.0% | 0.0 | 15.0 | 14.9 | 15.0 | 1472.0 | 3100.0 | 85.31 |
| gpt-5.6-sol (eff=xhigh, mt=16384) | 25 | 85 | 100.0% | 2.0 | 15.0 | 14.9 | 14.9 | 1844.2 | 9069.8 | 154.77 |
| gemini-3.6-flash (th=minimal) | 25 | 85 | 96.0% | 3.2 | 12.9 | 13.7 | 14.3 | 813.3 | 935.2 | 60.58 |
| glm-5-fp8 (th=none, mt=4096, base=daily--glm5-sglang-serve.modal.run) | 25 | 85 | 96.0% | 2.9 | 13.6 | 14.5 | 13.8 | 988.5 | 1906.0 | 74.06 |
| gpt-5.6-luna (eff=low, mt=50000) | 25 | 85 | 88.0% | 2.6 | 11.4 | 13.5 | 14.1 | 1165.2 | 2484.4 | 77.92 |
| claude-haiku-4-5-20251001 (th=none) | 25 | 85 | 84.0% | 2.1 | 11.2 | 14.7 | 13.7 | 1991.1 | 3785.7 | 108.06 |
| gemini-3.5-flash-lite (th=minimal) | 25 | 84 | 100.0% | 0.7 | 15.0 | 13.4 | 14.4 | 598.2 | 717.2 | 49.87 |
| gpt-4.1 (th=none) | 25 | 84 | 100.0% | 1.3 | 14.7 | 13.9 | 14.4 | 702.1 | 1177.2 | 59.66 |
| gemini-2.5-flash (th=high, tb=2048) | 25 | 84 | 100.0% | 2.3 | 15.0 | 12.8 | 14.3 | 2352.2 | 3831.5 | 126.25 |
| nemotron-3-ultra-550b (th=none, mt=8192, base=inference.baseten.co) | 25 | 83 | 100.0% | 2.9 | 15.0 | 11.7 | 14.8 | 753.6 | 940.8 | 61.52 |
| nemotron-3-super-120b (th=medium, tb=512, mt=4096, base=daily--nemotron-super-b200-sglang-serve.modal.run) | 25 | 82 | 100.0% | 1.4 | 13.0 | 13.1 | 14.1 | 4877.7 | 7666.1 | 182.42 |
| gpt-4o (th=none) | 25 | 82 | 92.0% | 1.1 | 15.0 | 10.2 | 13.9 | 822.7 | 1951.9 | 70.70 |
| nemotron-3-super-120b (th=high, tb=2048, mt=4096, base=daily--nemotron-super-b200-sglang-serve.modal.run) | 25 | 82 | 76.0% | 1.1 | 13.4 | 12.6 | 14.4 | 4552.8 | 25082.0 | 316.11 |
| nemotron-3-super-120b (th=low, tb=128, mt=4096, base=daily--nemotron-super-b200-sglang-serve.modal.run) | 25 | 81 | 92.0% | 2.2 | 12.3 | 11.1 | 13.7 | 2940.4 | 3566.0 | 169.80 |
| gpt-5.4-mini (th=medium) | 25 | 81 | 80.0% | 4.1 | 9.8 | 13.9 | 12.5 | 2874.2 | 11905.3 | 222.19 |
| gpt-5.4-mini (th=low) | 25 | 80 | 64.0% | 2.6 | 9.7 | 14.6 | 13.6 | 1351.9 | 2880.5 | 79.00 |
| Qwen/Qwen3.6-35B-A3B-FP8 (th=none, mt=4096, base=model-qzkm8mpq.api.baseten.co/deployment/qe20zvr/sync) | 25 | 79 | 88.0% | 3.5 | 13.6 | 5.2 | 13.0 | 889.5 | 1533.6 | 104.05 |
| inkling-small (th=high, mt=16384, base=inference.baseten.co) | 25 | 79 | 76.0% | 2.8 | 13.7 | 7.7 | 10.8 | 411.2 | 475.8 | 66.12 |
| Qwen/Qwen3.6-27B (th=none, mt=4096, base=model-w67n482q.api.baseten.co/deployment/wxpnlg5/sync) | 25 | 72 | 56.0% | 3.8 | 15.0 | 0.0 | 8.4 | 998.2 | 2520.2 | 215.26 |
| gpt-5.4-mini (th=high, mt=4096) | 25 | 71 | 56.0% | 5.6 | 11.9 | 4.5 | 8.2 | 7661.1 | 26354.6 | 465.29 |
| qwen3.5-9b (th=high, mt=4096, base=daily--qwen35-sglang-serve-9b.modal.run) | 25 | 64 | 56.0% | 0.6 | 7.8 | 5.8 | 10.8 | 3237.6 | 9443.8 | 270.02 |
| nemotron-3-nano-30b (th=high, tb=2048, mt=4096, base=daily--nemotron-nano-b200-sglang-serve.modal.run) | 25 | 45 | 8.0% | 0.1 | 12.5 | 8.6 | 10.0 | 15943.9 | 17104.7 | 381.63 |
| inkling-small (th=xhigh, mt=16384, base=inference.baseten.co) | 25 | 44 | 20.0% | 2.3 | 13.7 | 5.6 | 2.8 | 416.3 | 485.6 | 73.22 |
| inkling-small (th=low, mt=16384, base=inference.baseten.co) | 25 | 43 | 0.0% | 0.0 | 14.4 | 14.5 | 12.6 | 378.0 | 621.6 | 8.02 |
| gpt-5.4-mini (th=none, mt=4096) | 25 | 42 | 8.0% | 0.2 | 11.2 | 14.2 | 10.1 | 911.5 | 1990.9 | 21.41 |
| qwen3.5-27b (th=none, mt=4096, base=daily--qwen35-sglang-serve-27b.modal.run) | 25 | 39 | 8.0% | 2.5 | 14.5 | 0.0 | 1.8 | 1932.7 | 4479.8 | 282.62 |
| nemotron-3-super-120b (th=none, tb=0, mt=4096, base=daily--nemotron-super-b200-sglang-serve.modal.run) | 25 | 37 | 16.0% | 1.6 | 14.2 | 0.2 | 2.3 | 1497.1 | 2994.8 | 260.14 |
| qwen3.5-4b (th=none, mt=4096, base=daily--qwen35-sglang-serve-4b.modal.run) | 25 | 37 | 12.0% | 0.8 | 13.5 | 0.1 | 2.8 | 1178.9 | 3033.4 | 241.03 |
| nemotron-3-nano-30b-nvfp4 (th=high, mt=10000, base=127.0.0.1:8000) | 25 | 37 | 12.0% | 1.6 | 14.5 | 4.8 | 5.6 | 6753.2 | 31781.8 | 358.18 |
| nemotron-3-nano-30b (th=medium, tb=512, mt=4096, base=daily--nemotron-nano-b200-sglang-serve.modal.run) | 25 | 37 | 0.0% | 0.2 | 11.0 | 5.1 | 9.3 | 4882.8 | 5633.4 | 218.07 |
| gemma-4-e4b (th=high, mt=4096, base=daily--gemma4-e4b-vllm.modal.run) | 25 | 35 | 20.0% | 0.6 | 11.5 | 1.7 | 5.4 | 1001.9 | 5828.9 | 180.49 |
| qwen3.5-4b (th=high, mt=4096, base=daily--qwen35-sglang-serve-4b.modal.run) | 25 | 34 | 28.0% | 1.0 | 3.5 | 8.3 | 7.0 | 2372.3 | 6146.6 | 222.93 |
| nemotron-3.5-lightning (th=high, base=127.0.0.1:8000) | 25 | 31 | 48.0% | 1.0 | 5.9 | 7.5 | 8.0 | 470.1 | 3457.3 | 107.87 |
| glm-4.7-flash (th=none, mt=4096, base=daily--glm47-sglang-serve.modal.run) | 25 | 29 | 12.0% | 1.1 | 6.6 | 6.9 | 3.4 | 1875.3 | 3692.8 | 168.69 |
| nemotron-3-nano-30b (th=low, tb=128, mt=4096, base=daily--nemotron-nano-b200-sglang-serve.modal.run) | 25 | 28 | 0.0% | 0.0 | 11.4 | 5.5 | 8.1 | 2150.8 | 4918.5 | 108.50 |
| gemma-4-e4b (th=none, mt=4096, base=daily--gemma4-e4b-vllm.modal.run) | 25 | 27 | 28.0% | 0.5 | 11.4 | 3.0 | 4.6 | 1045.6 | 6246.7 | 172.13 |
| nemotron-3.5-lightning (th=none, base=127.0.0.1:8000) | 25 | 23 | 0.0% | 0.8 | 7.0 | 4.3 | 0.0 | 163.5 | 230.4 | 61.47 |
| qwen3.5-122b (th=high, mt=4096, base=daily--qwen35-sglang-serve-122b.modal.run) | 25 | 22 | 4.0% | 0.2 | 15.0 | 7.2 | 0.5 | 976.0 | 4021.8 | 27.00 |
| gpt-5.4-mini (th=xhigh, mt=4096) | 25 | 20 | 0.0% | 0.0 | 15.0 | 4.7 | 0.0 | 24118.1 | 28550.8 | 221.99 |
| nemotron-3-nano-30b (th=none, tb=0, mt=4096, base=daily--nemotron-nano-b200-sglang-serve.modal.run) | 25 | 16 | 0.0% | 0.2 | 4.6 | 4.1 | 3.0 | 915.0 | 1291.6 | 102.65 |
| nemotron-3-nano-30b-nvfp4 (th=none, mt=10000, base=127.0.0.1:8000) | 25 | 13 | 0.0% | 0.0 | 9.6 | 4.7 | 0.0 | 246.4 | 282.5 | 62.17 |
