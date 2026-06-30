# Baseten Empty-Turn Diagnostic Findings (step 1)

> Diagnostic-only evidence for `proj-2026-06-30-0924` step 1. NOT a benchmark run, NOT eval input, NOT leaderboard data. Bounded sample counts. The endpoint was idle (no concurrent sweeps) during these probes except where the concurrency probe deliberately varies concurrency.
>
> Probes run live against `https://inference.baseten.co/v1` on 2026-06-30 via `diagnostics/baseten_empty_turn_probe.py`. The full raw-chunk dumps are intentionally omitted here (they ran to ~240K); a representative streaming excerpt is retained below.

## Summary & Gating Decisions

**Mechanism B is a transient, non-deterministic empty response from the Baseten endpoint.** It did **not** reproduce in any bounded probe:
- Concurrency **1 / 2 / 6**, reasoning **off**: **0%** empty (25 samples/level).
- Concurrency **1 / 2 / 6**, reasoning **high**: **0%** empty (12 samples/level).
- **Replay of a real B context** (the exact `messages_for_llm` of turns that returned empty in the 2026-06-29 sweep): healthy every time — short context (turn 1) and long context (turn 29, 110 messages) ×3, both streaming and non-streaming.

The single strongest datum: replaying an input that originally returned empty now returns reasoning + content + tool calls. Same input → success on retry.

Gating decisions for the rest of the plan:
1. **Step 3 (empty-turn retry): IMPLEMENT — do NOT downscope to telemetry-only.** B is transient and a retry of the identical request recovers it (directly demonstrated by replay). Retry is the correct fix.
2. **Concurrency hypothesis: NOT supported by the probe.** Raw endpoint load (even at 6×) did not induce B. Running one-at-a-time remains correct practice (`AGENTS.md` + conservative isolation of harness changes), but it is **not** what fixes B — the retry is.
3. **Step 4 (GLM reasoning preservation): feasible.** GLM emits `reasoning_content` as a **separate field** — a distinct streaming `delta.reasoning_content` (strictly before `tool_calls`, 3/3 samples) and a separate `message.reasoning_content` non-streaming. Preservation = re-attach the harness's already-captured reasoning (`_response_thought`) onto the GLM assistant message.
4. **`force_nonempty_content`: keep OUT of the harness path.** Baseten *accepts* the param (does not reject), but evidence of effect is only weak/observational for GLM and none for Nemotron — not the proof the plan requires. Note as a possible future lever.

Caveat: the bounded probes (≤25 samples) captured **zero** B events, so the per-request B rate cannot be quantified here, and a concurrency contribution at sustained scale is not fully excluded. The non-determinism on replay is the decisive evidence; it both identifies B as transient transport behavior and validates retry as the fix.

## Concurrency Probe (GLM-5.2, streaming)

Counts true Mechanism-B `empty_no_usage` (no content, no tool calls, no reasoning, usage missing/zero) separately from `reasoning_only_no_tool`.

reasoning_effort = `none`, 25 samples/level:

| concurrency | ok | errors | empty_no_usage | reasoning_only_no_tool | empty_rate | avg_latency_ms |
|---|---|---|---|---|---|---|
| 1 | 25 | 0 | 0 | 0 | 0.0% | 1062 |
| 2 | 25 | 0 | 0 | 0 | 0.0% | 712 |
| 6 | 25 | 0 | 0 | 0 | 0.0% | 1244 |

reasoning_effort = `high`, 12 samples/level:

| concurrency | ok | errors | empty_no_usage | reasoning_only_no_tool | empty_rate | avg_latency_ms |
|---|---|---|---|---|---|---|
| 1 | 12 | 0 | 0 | 0 | 0.0% | 3020 |
| 2 | 12 | 0 | 0 | 0 | 0.0% | 2320 |
| 6 | 12 | 0 | 0 | 0 | 0.0% | 3852 |

## Replay reproducibility (raw-capture)

Real captured contexts from `runs/baseten-sweep-20260629-231133/glm52-high/glm52-high-r17.json` (these turns returned empty in the original sweep):

| inference_index | context | mode | empty_no_usage | content_len | tool_calls | finish |
|---|---|---|---|---|---|---|
| 1 (initial_run) | 4 msgs | stream | False | 180 | 10 | tool_calls |
| 1 | 4 msgs | non-stream | False | (healthy) | 1 | tool_calls |
| 29 (run 1) | 110 msgs | stream / non-stream | False / False | 274 / 247 | 3 / 1 | tool_calls |
| 29 (run 2) | 110 msgs | stream / non-stream | False / False | 210 / 73 | 4 / 1 | tool_calls |
| 29 (run 3) | 110 msgs | stream / non-stream | False / False | 127 / 241 | 3 / 1 | tool_calls |

Every replay of an originally-empty turn returned a healthy response.

## Reasoning-shape Probe (GLM-5.2 reasoning-on, step-4 evidence)

Streaming (`delta.reasoning_content` is a separate field; order vs `tool_calls`):

| sample | tool_deltas | reasoning_len | content_len | completion_tokens | order |
|---|---|---|---|---|---|
| 1 | 3 | 2676 | 88 | 904 | reasoning_content_strictly_before_tool_call |
| 2 | 3 | 927 | 40 | 331 | reasoning_content_strictly_before_tool_call |
| 3 | 3 | 180 | 0 | 102 | reasoning_content_strictly_before_tool_call |

Non-streaming: `message.reasoning_content` present as a separate field on the assistant message (serialized after `tool_calls` — dict key order, not temporal).

Representative streaming excerpt (reasoning streams first, as its own field):
```json
{"chunk_index":0,"delta":{"role":"assistant","reasoning_content":"Let","content":null,"tool_calls":null}}
{"chunk_index":1,"delta":{"reasoning_content":" me break","content":null,"tool_calls":null}}
...   (reasoning_content continues, then content, then tool_calls deltas)
```

## force_nonempty_content Probe (chat_template_kwargs)

5 samples; control (no flag) vs forced (`chat_template_kwargs.force_nonempty_content=true`):

| model | classification | control_content/ok | forced_content/ok |
|---|---|---|---|
| zai-org/GLM-5.2 | weak_observational_evidence_honored_more_nonempty_content | 2/5 | 4/5 |
| nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B | accepted_no_effect_observed | 5/5 | 5/5 |

Baseten accepts the parameter (no rejection). Effect is weak/observational for GLM, none for Nemotron — insufficient proof to add to the harness path per the plan rule.
