# Primary Leaderboard Summary (11 Columns)

- Leaderboard prompt: `natural`
- Prompt hash: `68d2c77be6548b77cd2e65ca0489edb2080c4a652feeb11f5ef5317f91e4b1f0`
- Score rubric version: `port_to_port_primary_v1`
- Aggregation: Primary=median, Task Complete=rate, Trade/Path/Tools/Report=mean
- Source runs: `runs/leaderboard-natural-v1-input/*.json`, `runs/muse-glimmer-30b-natural-high-card-nomax-dflash15-n25-20260810T213830Z/raw/*.json`, `runs/nemotron-3.5-lightning-natural-*-sglang-20260811T223912Z-r*.json`, and `runs/nemotron-3-nano-30b-nvfp4-natural-*-sglang-prod-native-20260812T192200Z-r*.json`
- Enriched scores: `runs/leaderboard-natural-v1-refresh-20260722-newmodels.jsonl`, `runs/muse-glimmer-30b-natural-high-card-nomax-dflash15-n25-20260810T213830Z/eval/enriched_runs.jsonl`, `runs/eval-nemotron-3.5-lightning-natural-*-sglang-20260811T223912Z/enriched_runs.jsonl`, and `runs/eval-nemotron3-nano-native-prod-20260812T192200Z/enriched_runs.jsonl`
- Sort: Primary /100 desc, Task Complete % desc, Total Time P50 (s) asc

The local Nemotron rows used official NVIDIA NVFP4 checkpoints on one RTX 5090 with SGLang and binary native thinking, without a thinking-token budget. Nano used a 262,144-token context, `max_tokens=10000`, model-card tool sampling (`temperature=0.6`, `top_p=0.95`) when thinking was on, greedy decoding when off, and a cache flush between conversations. Lightning used `temperature=1.0`, `top_p=0.95`, no output-token ceiling, and did not flush between conversations, so its latency regime is not identical to Nano's.

| Model | N | Primary /100 | Task Complete % | Trade /15 Avg | Path /15 Avg | Tools /15 Avg | Report /15 Avg | Turn P50 (ms) | Turn P90 (ms) | Total Time P50 (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini-3.6-flash (th=high) | 25 | 97 | 100.0% | 9.2 | 15.0 | 15.0 | 15.0 | 1176.2 | 3498.5 | 97.07 |
| glm-5.2 (th=xhigh, mt=8192, base=inference.baseten.co) | 25 | 97 | 100.0% | 11.0 | 14.8 | 14.3 | 14.8 | 1190.8 | 14458.6 | 212.72 |
| gpt-5.4 (th=medium, mt=4096) | 25 | 97 | 100.0% | 12.2 | 15.0 | 15.0 | 14.9 | 6309.5 | 25817.6 | 347.89 |
| glm-5.2 (th=high, mt=8192, base=inference.baseten.co) | 25 | 94 | 100.0% | 10.2 | 14.7 | 15.0 | 14.9 | 809.4 | 6025.9 | 117.31 |
| claude-sonnet-5 (th=xhigh) | 25 | 93 | 100.0% | 9.6 | 15.0 | 14.1 | 15.0 | 2527.3 | 13172.9 | 246.87 |
| glm-5.2 (th=none, mt=8192, base=inference.baseten.co) | 25 | 92 | 100.0% | 8.9 | 14.5 | 14.8 | 14.9 | 784.6 | 2447.0 | 80.42 |
| gemini-3.6-flash (th=low) | 25 | 92 | 100.0% | 8.7 | 14.7 | 14.9 | 15.0 | 1020.2 | 2186.8 | 81.51 |
| gemini-3.6-flash (th=medium) | 25 | 92 | 100.0% | 9.0 | 15.0 | 14.9 | 15.0 | 1111.3 | 2904.5 | 90.13 |
| glm-5-fp8 (th=high, mt=4096, base=daily--glm5-sglang-serve.modal.run) | 25 | 92 | 100.0% | 5.9 | 14.8 | 15.0 | 14.9 | 1420.1 | 4623.0 | 107.98 |
| claude-sonnet-4-6 (th=none) | 25 | 92 | 100.0% | 8.2 | 15.0 | 14.5 | 13.6 | 1998.1 | 4948.2 | 125.53 |
| gpt-5.4 (th=low, mt=4096) | 25 | 92 | 100.0% | 7.6 | 15.0 | 15.0 | 14.9 | 2433.8 | 10455.4 | 136.22 |
| gpt-5.6-terra (eff=xhigh, mt=50000) | 25 | 92 | 100.0% | 7.4 | 15.0 | 14.7 | 15.0 | 2253.3 | 6374.1 | 136.56 |
| claude-sonnet-5 (th=medium) | 25 | 92 | 100.0% | 6.1 | 15.0 | 14.9 | 15.0 | 2160.9 | 6969.5 | 137.68 |
| claude-sonnet-5 (th=high) | 25 | 92 | 100.0% | 8.1 | 15.0 | 14.4 | 15.0 | 2354.7 | 9222.9 | 193.52 |
| claude-sonnet-4-6 (th=medium) | 25 | 92 | 100.0% | 9.3 | 15.0 | 13.6 | 15.0 | 2452.7 | 10638.6 | 200.09 |
| gpt-5.6-terra (eff=max, mt=50000) | 25 | 92 | 100.0% | 8.4 | 15.0 | 14.3 | 15.0 | 3238.7 | 16364.3 | 263.17 |
| gpt-5.1 (th=medium) | 25 | 92 | 100.0% | 8.0 | 15.0 | 15.0 | 14.2 | 13615.7 | 49692.4 | 647.86 |
| gpt-5.2 (th=medium) | 25 | 91 | 100.0% | 6.5 | 14.8 | 14.1 | 14.6 | 1047.9 | 10482.2 | 149.98 |
| claude-sonnet-4-6 (th=low) | 25 | 90 | 100.0% | 5.8 | 15.0 | 13.6 | 14.6 | 1957.0 | 6899.5 | 139.09 |
| gemma-4-31b (th=high, mt=4096, base=daily--gemma4-31b-vllm.modal.run) | 25 | 89 | 100.0% | 4.0 | 15.0 | 15.0 | 15.0 | 850.6 | 1065.5 | 60.43 |
| gpt-5.6-terra (eff=low, mt=50000) | 25 | 89 | 100.0% | 4.2 | 14.4 | 14.9 | 14.9 | 1244.2 | 2824.5 | 84.24 |
| claude-sonnet-5 (th=low) | 25 | 89 | 100.0% | 4.3 | 14.8 | 15.0 | 15.0 | 2068.8 | 5695.2 | 119.40 |
| claude-haiku-4-5-20251001 (th=low) | 25 | 89 | 100.0% | 4.3 | 14.1 | 14.4 | 14.8 | 2157.9 | 6863.1 | 125.41 |
| claude-sonnet-5 (th=none) | 25 | 89 | 100.0% | 6.1 | 14.0 | 14.6 | 15.0 | 2543.8 | 10036.0 | 189.48 |
| qwen3.5-27b (th=high, mt=4096, base=daily--qwen35-sglang-serve-27b.modal.run) | 25 | 89 | 100.0% | 5.4 | 14.3 | 14.8 | 15.0 | 4281.0 | 11008.7 | 200.22 |
| nemotron-3-ultra-550b (th=high, mt=8192, base=inference.baseten.co) | 25 | 88 | 100.0% | 4.6 | 13.2 | 14.9 | 14.0 | 989.3 | 2817.5 | 81.03 |
| gpt-5.1 (th=low) | 25 | 88 | 100.0% | 4.2 | 15.0 | 14.8 | 14.4 | 1798.2 | 12660.8 | 162.69 |
| gpt-5.6-luna (eff=xhigh, mt=50000) | 25 | 88 | 96.0% | 6.8 | 12.9 | 14.1 | 14.0 | 1490.2 | 5967.5 | 125.40 |
| poolside/laguna-s-2.1 (th=none, mt=4096, base=openrouter.ai/api) | 25 | 88 | 84.0% | 4.8 | 12.0 | 14.4 | 12.0 | 834.0 | 2592.3 | 93.44 |
| gpt-5.6-luna (eff=max, mt=50000) | 25 | 88 | 84.0% | 8.4 | 11.6 | 14.1 | 12.0 | 1467.1 | 10290.2 | 189.36 |
| gemini-3.1-flash-lite-preview (th=high) | 25 | 87 | 100.0% | 2.4 | 14.8 | 14.6 | 14.3 | 802.8 | 2814.8 | 67.01 |
| claude-haiku-4-5-20251001 (th=medium) | 25 | 87 | 100.0% | 3.3 | 14.2 | 14.4 | 14.8 | 2151.4 | 7263.9 | 131.10 |
| gpt-5.4 (th=none, mt=4096) | 25 | 87 | 96.0% | 4.0 | 14.0 | 14.6 | 14.6 | 1206.0 | 2547.9 | 50.23 |
| muse-glimmer-30b (th=high, base=127.0.0.1:8080) | 25 | 87 | 92.0% | 4.1 | 14.1 | 13.0 | 13.7 | 487.0 | 9429.3 | 166.07 |
| inkling (th=low, mt=16384, base=inference.baseten.co) | 25 | 86 | 100.0% | 2.6 | 15.0 | 13.7 | 14.6 | 594.0 | 1337.1 | 57.16 |
| gpt-4.1 (th=medium) | 25 | 86 | 100.0% | 2.4 | 14.3 | 14.4 | 13.7 | 805.9 | 1395.4 | 61.33 |
| inkling (th=high, mt=16384, base=inference.baseten.co) | 25 | 86 | 100.0% | 3.2 | 14.8 | 13.2 | 14.5 | 605.6 | 3402.2 | 111.73 |
| inkling (th=xhigh, mt=16384, base=inference.baseten.co) | 25 | 86 | 100.0% | 2.8 | 15.0 | 13.2 | 14.7 | 606.1 | 3155.9 | 129.79 |
| gpt-4.1 (th=low) | 25 | 85 | 100.0% | 2.4 | 14.8 | 14.0 | 14.0 | 814.5 | 1455.0 | 63.23 |
| gemini-3.6-flash (th=minimal) | 25 | 85 | 96.0% | 3.2 | 12.9 | 13.7 | 14.3 | 813.3 | 935.2 | 60.58 |
| glm-5-fp8 (th=none, mt=4096, base=daily--glm5-sglang-serve.modal.run) | 25 | 85 | 96.0% | 2.9 | 13.6 | 14.5 | 13.8 | 988.5 | 1906.0 | 74.06 |
| gpt-5.6-luna (eff=low, mt=50000) | 25 | 85 | 88.0% | 2.6 | 11.4 | 13.5 | 14.1 | 1165.2 | 2484.4 | 77.92 |
| claude-haiku-4-5-20251001 (th=none) | 25 | 85 | 84.0% | 2.1 | 11.2 | 14.7 | 13.7 | 1991.1 | 3785.7 | 108.06 |
| gemini-3.5-flash-lite (th=minimal) | 25 | 84 | 100.0% | 0.7 | 15.0 | 13.4 | 14.4 | 598.2 | 717.2 | 49.87 |
| gemini-3.1-flash-lite-preview (th=minimal) | 25 | 84 | 100.0% | 0.8 | 15.0 | 14.2 | 14.3 | 735.3 | 940.8 | 54.30 |
| gpt-4.1 (th=none) | 25 | 84 | 100.0% | 1.3 | 14.7 | 13.9 | 14.4 | 702.1 | 1177.2 | 59.66 |
| gemini-2.5-flash (th=high, tb=2048) | 25 | 84 | 100.0% | 2.3 | 15.0 | 12.8 | 14.3 | 2352.2 | 3831.5 | 126.25 |
| nemotron-3-ultra-550b (th=none, mt=8192, base=inference.baseten.co) | 25 | 83 | 100.0% | 2.9 | 15.0 | 11.7 | 14.8 | 753.6 | 940.8 | 61.52 |
| gemini-3.1-flash-lite-preview (th=medium) | 25 | 83 | 96.0% | 0.4 | 15.0 | 14.0 | 13.9 | 745.4 | 944.1 | 53.75 |
| nemotron-3-super-120b (th=medium, tb=512, mt=4096, base=daily--nemotron-super-b200-sglang-serve.modal.run) | 25 | 82 | 100.0% | 1.4 | 13.0 | 13.1 | 14.1 | 4877.7 | 7666.1 | 182.42 |
| gpt-4o (th=none) | 25 | 82 | 92.0% | 1.1 | 15.0 | 10.2 | 13.9 | 822.7 | 1951.9 | 70.70 |
| nemotron-3-super-120b (th=high, tb=2048, mt=4096, base=daily--nemotron-super-b200-sglang-serve.modal.run) | 25 | 82 | 76.0% | 1.1 | 13.4 | 12.6 | 14.4 | 4552.8 | 25082.0 | 316.11 |
| gemini-3.1-pro-preview (th=medium) | 25 | 81 | 100.0% | 1.7 | 15.0 | 10.9 | 15.0 | 3062.6 | 5958.4 | 155.53 |
| nemotron-3-super-120b (th=low, tb=128, mt=4096, base=daily--nemotron-super-b200-sglang-serve.modal.run) | 25 | 81 | 92.0% | 2.2 | 12.3 | 11.1 | 13.7 | 2940.4 | 3566.0 | 169.80 |
| gpt-5.4-mini (th=medium) | 25 | 81 | 80.0% | 4.1 | 9.8 | 13.9 | 12.5 | 2874.2 | 11905.3 | 222.19 |
| gpt-5.4-mini (th=low) | 25 | 80 | 64.0% | 2.6 | 9.7 | 14.6 | 13.6 | 1351.9 | 2880.5 | 79.00 |
| gpt-5.4-mini (th=high, mt=4096) | 25 | 71 | 56.0% | 5.6 | 11.9 | 4.5 | 8.2 | 7661.1 | 26354.6 | 465.29 |
| qwen3.5-9b (th=high, mt=4096, base=daily--qwen35-sglang-serve-9b.modal.run) | 25 | 64 | 56.0% | 0.6 | 7.8 | 5.8 | 10.8 | 3237.6 | 9443.8 | 270.02 |
| nemotron-3-nano-30b (th=high, tb=2048, mt=4096, base=daily--nemotron-nano-b200-sglang-serve.modal.run) | 25 | 45 | 8.0% | 0.1 | 12.5 | 8.6 | 10.0 | 15943.9 | 17104.7 | 381.63 |
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
