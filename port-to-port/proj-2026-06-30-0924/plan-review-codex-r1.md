# Review: PLAN.md for GLM-5.2 / Nemotron-3-Ultra fixes

Reviewed against the current code in `mini-rl-env.py`, `llm_factory.py`, `system_instruction.txt`, `run_baseten_sweep.sh`, `evaluate_runs.py`, `build_primary_leaderboard.py`, and installed pipecat under `.venv`.

## Verdict

The plan has the right broad shape: diagnose B before retrying it, keep transport empties out of bad-action accounting, do not edit installed pipecat, raise the Baseten token cap, then validate in a fresh run directory.

It is not implementation-ready as written. The main blockers are (1) the retry path does not specify how to handle active inference captures and the already-armed no-tool watchdog, (2) GLM `reasoning_content` preservation is materially under-specified and cannot be implemented by simply retaining an existing pipecat field, (3) prompt changes would not be separated by the current leaderboard prompt hash, and (4) the validation sweep currently runs multiple configs in parallel against one Baseten base URL, contrary to the repo ops rule.

## Current-State Reference Check

Mostly accurate:

- `mini-rl-env.py:156-158`: `MAX_NO_TOOL_NUDGES`, `NO_TOOL_WATCHDOG_DELAY`, and `EVENT_BATCH_INFERENCE_DELAY` are as described.
- `mini-rl-env.py:585-610`: empty assistant context detection/pruning is here; the function actually continues to `612`.
- `mini-rl-env.py:1401-1427`: no-tool watchdog/nudge/stall logic is accurately cited.
- `mini-rl-env.py:1485-1546`: frame capture is accurately cited.
- `mini-rl-env.py:1553-1607`, especially `1563-1567`: bad-action/no-tool increment is accurately cited.
- `mini-rl-env.py:2455-2458`: synthesized inference failure accounting is accurately cited.
- `llm_factory.py:211-261`, especially `229-232`: OpenAI service creation and `max_tokens` pass-through are accurately cited.
- `run_baseten_sweep.sh:17` and `85`: `MAX_TOKENS=4096` default and `--max-tokens "$MAX_TOKENS"` pass-through are accurately cited.
- `system_instruction.txt` is 218 lines.

Corrections:

- `PLAN.md:47` says replay contexts from `runs/.../.../inference_inputs`. In current run JSONs, `inference_inputs` are embedded in each run payload because `--capture-inference-inputs` defaults true (`mini-rl-env.py:2621-2624`); there is no separate `inference_inputs` directory in the sweep tree.
- The pipecat note at `PLAN.md:24` should be more precise: `base_llm.py:398-408` records usage `reasoning_tokens`; it does not parse or emit `reasoning_content`. `base_llm.py:423-451` handles streamed `delta.tool_calls` and `delta.content` only.

## Blocking

1. **Step 2 will corrupt inference capture bookkeeping unless the retry lifecycle is specified.**

   `PLAN.md:51` says the retry is transparent and happens in `_finalize_if_ready`, but current capture state is tied to each queued inference:

   - `mini-rl-env.py:1377` queues a new capture before each `LLMRunFrame`.
   - `mini-rl-env.py:1477` activates the next capture on response start.
   - `mini-rl-env.py:1884-1896` keeps an active capture index until it is claimed.
   - `mini-rl-env.py:1908-1917` claims/attaches that active capture only when a turn log is finalized.

   If an empty attempt is retried without finalizing a turn, the first attempt's capture remains active. A second retry capture can be queued, but `activate_next_inference_capture()` will keep returning the already-active first index. The successful retry can then attach to the wrong inference input and leave the retry capture pending for a later turn.

   Required plan change: define retry capture semantics before implementation. Either reuse the same inference record for all retry attempts, or explicitly mark/discard the active empty-attempt capture before queueing a retry. Add tests asserting `inference_index`, `response_start_llm_turn`, `finalized_llm_turn`, and pending capture queues after empty->success and empty->exhausted flows.

2. **Step 2 must cancel/own the no-tool watchdog during retries.**

   The no-tool watchdog is armed before `_finalize_if_ready` can classify the empty response: `process_frame(LLMFullResponseEndFrame)` calls `await self._controller.on_response_end(has_function_calls=False)` at `mini-rl-env.py:1547`, and `on_response_end()` starts the no-tool watchdog at `1193-1200`.

   If Step 2 only calls `request_inference("transport_empty_retry")`, the inference watchdog will usually cancel the no-tool watchdog later at `1356-1358`, but there is still a pending watchdog during the retry window. The plan needs to require immediate cancellation of `_no_tool_watchdog_handle` for transport-empty retries, and to restart/fall through to the existing watchdog only after retries are exhausted. Add a test that no nudge is appended during retry and that exhausted retries still reach the existing nudge/stall path.

3. **The proposed Mechanism-B signature is close but not sufficient as written.**

   `PLAN.md:51` proposes: no function calls + empty `_response_text`/`_response_text_raw` + `_usage_metrics is None`. It should also require empty `_response_thought` and no observed inference/error frame. The prior evidence defines B as no content, no tool call, no thought, no usage; preserving that distinction matters once Step 3 introduces reasoning capture.

   The implementation must also be explicitly gated to Baseten GLM/Nemotron or Baseten-only. The global rule says behavior changes must be model/endpoint gated, but Step 2's local text does not say this. Without the gate, any provider that omits final stream usage on an empty but genuine model no-action turn would be silently retried and removed from bad-action accounting.

   Telemetry separation is directionally correct, but the plan should state that successful transport retries must not append a normal `turn_log` or increment `turn_count`; otherwise `turns_executed`, max-turns behavior, latency aggregation, and leaderboard grouping are changed even if `bad_actions_count` stays clean.

4. **Step 3 is under-specified and needs its own spike/design before implementation.**

   The plan's goal is feasible only with a deliberate harness-side adapter, not by "retaining" an existing pipecat field:

   - Installed `base_llm.py` ignores streamed `delta.reasoning_content`; it only processes `delta.tool_calls` and `delta.content` at `423-451`.
   - Installed `llm_response_universal.py` appends assistant tool-call messages at `974-988` with `role` and `tool_calls`, but no `content` and no `reasoning_content`.
   - The existing thought-frame path (`llm_response_universal.py:1128-1159`) would append an `LLMSpecificMessage` shaped like `{"type": "thought", "text": ...}`, which is not the OpenAI/GLM assistant message shape likely needed for `reasoning_content`.
   - The OpenAI adapter simply passes `LLMSpecificMessage.message` through (`open_ai_adapter.py:113-124`), so a custom provider-specific message is possible, but the plan must say how it is created and how duplicate assistant tool-call messages are avoided.

   Required plan change: make Step 3 a spike first. It should inspect successful GLM raw chunks for `reasoning_content`, define the exact assistant message shape to re-submit, define whether this is done by subclassing `OpenAILLMService`, monkey-patching `_process_context`, adding a custom assistant aggregator, or inserting a harness processor, and include a captured-context test.

   Also do not reuse `_is_glm_sglang_binary_reasoning_model()` as-is for Baseten GLM gating. It matches names starting with `glm-5`, but the sweep config uses `zai-org/GLM-5.2` (`run_baseten_sweep.sh:38`), which does not start with `glm-5`.

5. **Step 5 changes prompt behavior without changing the leaderboard prompt scope.**

   `PLAN.md:63` edits `system_instruction.txt`. Current metadata records `system_instruction_hash` (`mini-rl-env.py:1722-1723`), but the leaderboard prompt guard uses `metadata.task_prompt_hash` and `leaderboard_prompt_id` (`build_primary_leaderboard.py:178-214`). The task prompt hash is computed from `args.task`, not the system instruction (`mini-rl-env.py:1727`).

   As a result, old and new runs with different system prompts can still share `leaderboard_prompt_id=natural` and the same `task_prompt_hash`, so `build_primary_leaderboard.py` will not reject mixing them. Required plan change: either include `system_instruction_hash` in leaderboard prompt scoping for this validation, or explicitly bump/scope the prompt version before collecting prompt-iteration data and keep prompt-change validation separate from harness-fix validation.

6. **Step 6 violates the sequential-per-endpoint run rule unless `run_baseten_sweep.sh` is changed or wrapped.**

   `PLAN.md:67` says to re-run `run_baseten_sweep.sh`. The script uses a single `BASE_URL` (`run_baseten_sweep.sh:21`) and launches every config as a background worker (`98-107`). That parallelizes six configs against the same OpenAI-compatible Baseten base URL.

   The repo instructions say runs must stay sequential per provider endpoint. Required plan change: add a validation-run step that makes Baseten configs sequential for this sweep, or add a concurrency knob and set it to 1 for the validation sweep. This also improves interpretability of retry/empty-rate telemetry.

## Should-Fix

1. **Move or split Step 4 so the simple Mechanism-A fix is not blocked by the Step-3 spike.**

   Raising `MAX_TOKENS` in `run_baseten_sweep.sh` and relying on `llm_factory.py:229-232` is independent of GLM reasoning preservation. Given Step 3 is high risk, put Step 4 before Step 3, or at least allow it to land and validate independently after Step 1/2.

2. **Step 1 should collect evidence for Step 3, not only empty completions.**

   The diagnostic currently focuses on empty turns. To decide Step 3, it should also capture raw streamed chunks for successful GLM tool-call turns with reasoning enabled and report whether `delta.reasoning_content` exists, where it appears relative to `tool_calls`, and whether non-streaming responses expose `message.reasoning_content`.

3. **Handle the Nemotron `force_nonempty_content` limitation explicitly.**

   The plan mentions that Baseten only honors `reasoning.effort`, and current harness code strips `chat_template_kwargs` in the Baseten branch (`mini-rl-env.py:890-904`). That means the NVIDIA-recommended `force_nonempty_content:true` is not addressed. Add a diagnostic/validation note that either confirms Baseten rejects/ignores it or documents it as an endpoint limitation. Do not let `/implement` add `chat_template_kwargs.force_nonempty_content` to the Baseten path without evidence.

4. **Add eval/leaderboard regression coverage for the new transport telemetry.**

   `evaluate_runs.py` reads `summary.no_tool_call_count` first (`1405-1409`) and `summary.bad_actions_count` first (`1431-1435`), so new fields will be ignored if the existing counters stay clean. Add a regression fixture proving that `empty_response_count` / `transport_empty_retries` does not affect `no_tool_call_count`, `bad_actions_count`, `tool_discipline_score`, or leaderboard grouping unless retries are exhausted and the existing no-tool path is used.

5. **Make validation attribution staged.**

   Step 6 says to run all fixes and compare target metrics, but that will not show which fix moved which metric. Add small staged sweeps or seed-matched smoke runs: baseline current, Step 2 only, Step 2+4, Step 2+4+3, then prompt. This is especially important because Step 5 changes behavior for all models.

6. **Clarify run logging and monitoring for the validation sweep.**

   The current Baseten script writes per-run output as `*.out` (`run_baseten_sweep.sh:88`) and progress logs, not the standard `runs/<stem>.log` pattern. If this script remains the validation path, the plan should explicitly accept `*.out` as the per-run log or rename to `.log`, and add `RUN_START` / `RUN_EXIT` markers around each run for easier postmortems.

7. **Account for the current Baseten timeout default.**

   `run_baseten_sweep.sh` sets `FC_TIMEOUT=30` at line `19`, while the general benchmark default is 20 seconds. For comparison to the 2026-06-29 Baseten baseline, keeping 30 may be right, but the plan should state that this is intentional.

## Nice-to-Have

1. **Add a retry reason and summary fields with stable names.**

   Suggested names: per-final-turn `transport_empty_retries`, per-attempt diagnostic entries under `transport_empty_attempts`, and summary `empty_response_count` plus `empty_response_retry_success_count`. Avoid overloading `failure_class`.

2. **Keep prompt hardening minimal and non-duplicative.**

   `system_instruction.txt:102-113` already says events drive state, only call tools, and never emit multiple tool calls. The new rule should be a small addition near that block. The route/trade checklist should avoid contradicting the built-in `literal` task rules at `mini-rl-env.py:104-139`.

3. **Use model-name predicates that cover both configured and normalized Baseten names.**

   Current and historical run payloads may use names like `zai-org/GLM-5.2`, `glm-5.2`, `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B`, or `nemotron-3-ultra-550b`. Step 2/3 gates should cover these explicitly and have unit tests.

4. **Add a negative test for text-only no-tool responses with missing usage.**

   The plan includes text-only no-tool coverage. Include the variant where usage is absent but `raw_response_text` is non-empty, to ensure the retry path does not swallow a genuine visible no-tool answer.
