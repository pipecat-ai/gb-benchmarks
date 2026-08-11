# Step 1 Diagnostic Script Review

Reviewed `/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/baseten_empty_turn_probe.py` against `PLAN.md:33-60`. Review only; no diagnostic, harness, sweep, or run files were modified.

## Verdict

Not clean yet. Safety posture is good, and the four requested probes are mostly present, but a few summary/classification paths can overclaim or misclassify evidence that later steps are supposed to gate on.

## Blocking

None found.

## Should-fix

1. **Reasoning-only responses can be counted as Mechanism-B empty/no-usage.** `extract_nonstream_shape()` records `message.reasoning_content` at `diagnostics/baseten_empty_turn_probe.py:584-598`, and `extract_stream_shape()` records streamed `delta.reasoning_content` at `diagnostics/baseten_empty_turn_probe.py:643-654`, but both `empty_no_usage` classifiers ignore those fields (`diagnostics/baseten_empty_turn_probe.py:600-604`, `diagnostics/baseten_empty_turn_probe.py:679-683`). The Step 3 Rule defines B as empty text/raw text, empty thought, no usage, and no error (`PLAN.md:42-46`). For reasoning-on probes, the script should separate true empty transport responses from reasoning-only/no-tool responses instead of folding both into `empty_no_usage`.

2. **Streaming reasoning/tool ordering can misreport same-chunk events.** `extract_stream_shape()` emits separate `reasoning_content` and `tool_calls` events in fixed code order when both fields are present in one delta (`diagnostics/baseten_empty_turn_probe.py:643-664`), then `streaming_reasoning_shape()` compares event-list indexes (`diagnostics/baseten_empty_turn_probe.py:1164-1178`). That makes `reasoning_content_same_event_as_tool_call` effectively unreachable and can report "before" when both fields were in the same streamed choice delta. Step 4 depends on exact reasoning/tool shape (`PLAN.md:59-60`, `PLAN.md:71-72`), so the classifier should compare chunk/choice identity and preserve same-delta evidence.

3. **`force_nonempty_content` classification overclaims rejection/honor.** `classify_force_result()` labels any all-failed forced condition as `rejected` (`diagnostics/baseten_empty_turn_probe.py:1390-1394`), even if controls also failed or the failures are network/auth/timeouts caught at `diagnostics/baseten_empty_turn_probe.py:1461-1469`. It also treats small count differences as honored (`diagnostics/baseten_empty_turn_probe.py:1395-1398`). Because `PLAN.md:39` forbids adding `chat_template_kwargs` unless Step 1 proves support, this should distinguish API parameter rejection from transport/auth failure and phrase positive results as weak evidence unless sample design supports stronger claims.

4. **Bounded-sample safety is incomplete.** The concurrency probe caps samples at 500 (`diagnostics/baseten_empty_turn_probe.py:853-854`), but reasoning-shape and force-nonempty accept any positive `--samples` (`diagnostics/baseten_empty_turn_probe.py:1671-1675`, `diagnostics/baseten_empty_turn_probe.py:1701-1704`, guarded only by `diagnostics/baseten_empty_turn_probe.py:1720-1723`). Step 1 is explicitly a bounded diagnostic exception (`PLAN.md:48-50`, `PLAN.md:59-60`); add caps for every repeated live probe.

## Nice-to-have

1. **Raw replay works, but default run-json selection is easy to misuse.** The loader correctly reads `inference_inputs[].messages_for_llm` and falls back to captured provider params (`diagnostics/baseten_empty_turn_probe.py:522-574`, `diagnostics/baseten_empty_turn_probe.py:966-1009`). However, with `--run-json` and no index it replays entry 0 (`diagnostics/baseten_empty_turn_probe.py:514-520`), which is usually not a real B turn. Consider requiring `--entry-index`/`--inference-index` or auto-selecting a no-tool/no-usage inference when raw-capturing B evidence.

2. **Non-streaming "relative order" is key-order, not temporal evidence.** `nonstream_reasoning_shape()` reports `message_reasoning_content_key_before_tool_calls_key` based on serialized dict key order (`diagnostics/baseten_empty_turn_probe.py:1192-1224`). That is useful shape evidence, but the wording should avoid implying runtime order in a non-streaming response.

3. **Bad `--levels` input escapes the diagnostic error path.** `int(item)` can raise a raw `ValueError` before the explicit positive-level check (`diagnostics/baseten_empty_turn_probe.py:850-852`), while `main()` only converts `DiagnosticError` to a clean operator error (`diagnostics/baseten_empty_turn_probe.py:1716-1727`).

## Clean

- Concurrency levels 1/2/6 are actually exercised via a bounded `ThreadPoolExecutor` per model/level (`diagnostics/baseten_empty_turn_probe.py:879-904`), and the script keeps models/levels sequential outside each diagnostic concurrency burst.
- Raw capture covers streaming and non-streaming for the same request, includes per-choice deltas, finish reasons, usage summaries, and raw responses/chunks for empty cases (`diagnostics/baseten_empty_turn_probe.py:1012-1091`, `diagnostics/baseten_empty_turn_probe.py:1094-1154`).
- The script reads only `BASETEN_API_KEY` from the dotenv file and does not print it (`diagnostics/baseten_empty_turn_probe.py:57-85`).
- It is clearly labeled diagnostic-only and writes markdown findings, not run JSONs or leaderboard inputs (`diagnostics/baseten_empty_turn_probe.py:1-7`, `diagnostics/baseten_empty_turn_probe.py:748-778`).
- Malformed run JSON, missing `inference_inputs`, missing messages/tools shape errors, and per-request OpenAI/network failures have readable handling paths (`diagnostics/baseten_empty_turn_probe.py:493-502`, `diagnostics/baseten_empty_turn_probe.py:528-539`, `diagnostics/baseten_empty_turn_probe.py:687-709`, `diagnostics/baseten_empty_turn_probe.py:837-843`, `diagnostics/baseten_empty_turn_probe.py:1134-1150`, `diagnostics/baseten_empty_turn_probe.py:1294-1330`).
