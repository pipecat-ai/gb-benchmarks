# Primary Leaderboard Summary (11 Columns)

- Leaderboard prompt: `natural`
- Prompt hash: `68d2c77be6548b77cd2e65ca0489edb2080c4a652feeb11f5ef5317f91e4b1f0`
- Score rubric version: `port_to_port_primary_v1`
- Aggregation: Primary=median, Task Complete=rate, Trade/Path/Tools/Report=mean
- Source runs: `runs/leaderboard-natural-v1-input/*.json`
- Enriched scores: `runs/leaderboard-natural-v1-input.jsonl`
- Sort: Primary /100 desc, Task Complete % desc, Total Time P50 (s) asc

| Model | N | Primary /100 | Task Complete % | Trade /15 Avg | Path /15 Avg | Tools /15 Avg | Report /15 Avg | Turn P50 (ms) | Turn P90 (ms) | Total Time P50 (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gpt-5.4 (th=medium, mt=4096) | 25 | 97 | 100.0% | 12.2 | 15.0 | 15.0 | 14.9 | 6309.5 | 25817.6 | 347.89 |
| glm-5-fp8 (th=high, mt=4096, base=daily--glm5-sglang-serve.modal.run) | 25 | 92 | 100.0% | 5.9 | 14.8 | 15.0 | 14.9 | 1420.1 | 4623.0 | 107.98 |
| claude-sonnet-4-6 (th=none) | 25 | 92 | 100.0% | 8.2 | 15.0 | 14.5 | 13.6 | 1998.1 | 4948.2 | 125.53 |
| gpt-5.4 (th=low, mt=4096) | 25 | 92 | 100.0% | 7.6 | 15.0 | 15.0 | 14.9 | 2433.8 | 10455.4 | 136.22 |
| claude-sonnet-4-6 (th=medium) | 25 | 92 | 100.0% | 9.3 | 15.0 | 13.6 | 15.0 | 2452.7 | 10638.6 | 200.09 |
| gpt-5.1 (th=medium) | 25 | 92 | 100.0% | 8.0 | 15.0 | 15.0 | 14.2 | 13615.7 | 49692.4 | 647.86 |
| gpt-5.2 (th=medium) | 25 | 91 | 100.0% | 6.5 | 14.8 | 14.1 | 14.6 | 1047.9 | 10482.2 | 149.98 |
| claude-sonnet-4-6 (th=low) | 25 | 90 | 100.0% | 5.8 | 15.0 | 13.6 | 14.6 | 1957.0 | 6899.5 | 139.09 |
| claude-haiku-4-5-20251001 (th=low) | 25 | 89 | 100.0% | 4.3 | 14.1 | 14.4 | 14.8 | 2157.9 | 6863.1 | 125.41 |
| qwen3.5-27b (th=high, mt=4096, base=daily--qwen35-sglang-serve-27b.modal.run) | 25 | 89 | 100.0% | 5.4 | 14.3 | 14.8 | 15.0 | 4281.0 | 11008.7 | 200.22 |
| gpt-5.1 (th=low) | 25 | 88 | 100.0% | 4.2 | 15.0 | 14.8 | 14.4 | 1798.2 | 12660.8 | 162.69 |
| gemini-3.1-flash-lite-preview (th=high) | 25 | 87 | 100.0% | 2.4 | 14.8 | 14.6 | 14.3 | 802.8 | 2814.8 | 67.01 |
| claude-haiku-4-5-20251001 (th=medium) | 25 | 87 | 100.0% | 3.3 | 14.2 | 14.4 | 14.8 | 2151.4 | 7263.9 | 131.10 |
| gpt-5.4 (th=none, mt=4096) | 25 | 87 | 96.0% | 4.0 | 14.0 | 14.6 | 14.6 | 1206.0 | 2547.9 | 50.23 |
| gpt-4.1 (th=medium) | 25 | 86 | 100.0% | 2.4 | 14.3 | 14.4 | 13.7 | 805.9 | 1395.4 | 61.33 |
| gpt-4.1 (th=low) | 25 | 85 | 100.0% | 2.4 | 14.8 | 14.0 | 14.0 | 814.5 | 1455.0 | 63.23 |
| glm-5-fp8 (th=none, mt=4096, base=daily--glm5-sglang-serve.modal.run) | 25 | 85 | 96.0% | 2.9 | 13.6 | 14.5 | 13.8 | 988.5 | 1906.0 | 74.06 |
| claude-haiku-4-5-20251001 (th=none) | 25 | 85 | 84.0% | 2.1 | 11.2 | 14.7 | 13.7 | 1991.1 | 3785.7 | 108.06 |
| gemini-3.1-flash-lite-preview (th=minimal) | 25 | 84 | 100.0% | 0.8 | 15.0 | 14.2 | 14.3 | 735.3 | 940.8 | 54.30 |
| gpt-4.1 (th=none) | 25 | 84 | 100.0% | 1.3 | 14.7 | 13.9 | 14.4 | 702.1 | 1177.2 | 59.66 |
| gemini-2.5-flash (th=high, tb=2048) | 25 | 84 | 100.0% | 2.3 | 15.0 | 12.8 | 14.3 | 2352.2 | 3831.5 | 126.25 |
| gemini-3.1-flash-lite-preview (th=medium) | 25 | 83 | 96.0% | 0.4 | 15.0 | 14.0 | 13.9 | 745.4 | 944.1 | 53.75 |
| nemotron-3-super-120b (th=medium, tb=512, mt=4096, base=daily--nemotron-super-b200-sglang-serve.modal.run) | 25 | 82 | 100.0% | 1.4 | 13.0 | 13.1 | 14.1 | 2854.6 | 7666.1 | 109.38 |
| gpt-4o (th=none) | 25 | 82 | 92.0% | 1.1 | 15.0 | 10.2 | 13.9 | 822.7 | 1951.9 | 70.70 |
| nemotron-3-super-120b (th=high, tb=2048, mt=4096, base=daily--nemotron-super-b200-sglang-serve.modal.run) | 25 | 82 | 76.0% | 1.1 | 13.4 | 12.6 | 14.4 | 2659.7 | 25082.0 | 189.59 |
| gemini-3.1-pro-preview (th=medium) | 25 | 81 | 100.0% | 1.7 | 15.0 | 10.9 | 15.0 | 3062.6 | 5958.4 | 155.53 |
| nemotron-3-super-120b (th=low, tb=128, mt=4096, base=daily--nemotron-super-b200-sglang-serve.modal.run) | 25 | 81 | 92.0% | 2.2 | 12.3 | 11.1 | 13.7 | 1692.2 | 3566.0 | 101.81 |
| qwen3.5-9b (th=high, mt=4096, base=daily--qwen35-sglang-serve-9b.modal.run) | 25 | 64 | 56.0% | 0.6 | 7.8 | 5.8 | 10.8 | 3237.6 | 9443.8 | 270.02 |
| nemotron-3-nano-30b (th=high, tb=2048, mt=4096, base=daily--nemotron-nano-b200-sglang-serve.modal.run) | 25 | 45 | 8.0% | 0.1 | 12.5 | 8.6 | 10.0 | 9494.3 | 17104.7 | 228.91 |
| qwen3.5-27b (th=none, mt=4096, base=daily--qwen35-sglang-serve-27b.modal.run) | 25 | 39 | 8.0% | 2.5 | 14.5 | 0.0 | 1.8 | 1932.7 | 4479.8 | 282.62 |
| nemotron-3-super-120b (th=none, tb=0, mt=4096, base=daily--nemotron-super-b200-sglang-serve.modal.run) | 25 | 37 | 16.0% | 1.6 | 14.2 | 0.2 | 2.3 | 826.3 | 2994.8 | 156.01 |
| qwen3.5-4b (th=none, mt=4096, base=daily--qwen35-sglang-serve-4b.modal.run) | 25 | 37 | 12.0% | 0.8 | 13.5 | 0.1 | 2.8 | 1178.9 | 3033.4 | 241.03 |
| nemotron-3-nano-30b (th=medium, tb=512, mt=4096, base=daily--nemotron-nano-b200-sglang-serve.modal.run) | 25 | 37 | 0.0% | 0.2 | 11.0 | 5.1 | 9.3 | 2857.7 | 5633.4 | 130.77 |
| qwen3.5-4b (th=high, mt=4096, base=daily--qwen35-sglang-serve-4b.modal.run) | 25 | 34 | 28.0% | 1.0 | 3.5 | 8.3 | 7.0 | 2372.3 | 6146.6 | 222.93 |
| glm-4.7-flash (th=none, mt=4096, base=daily--glm47-sglang-serve.modal.run) | 25 | 29 | 12.0% | 1.1 | 6.6 | 6.9 | 3.4 | 1875.3 | 3692.8 | 168.69 |
| nemotron-3-nano-30b (th=low, tb=128, mt=4096, base=daily--nemotron-nano-b200-sglang-serve.modal.run) | 25 | 28 | 0.0% | 0.0 | 11.4 | 5.5 | 8.1 | 1218.5 | 4918.5 | 65.03 |
| qwen3.5-122b (th=high, mt=4096, base=daily--qwen35-sglang-serve-122b.modal.run) | 25 | 22 | 4.0% | 0.2 | 15.0 | 7.2 | 0.5 | 976.0 | 4021.8 | 27.00 |
| nemotron-3-nano-30b (th=none, tb=0, mt=4096, base=daily--nemotron-nano-b200-sglang-serve.modal.run) | 25 | 16 | 0.0% | 0.2 | 4.6 | 4.1 | 3.0 | 477.0 | 1291.6 | 61.52 |
