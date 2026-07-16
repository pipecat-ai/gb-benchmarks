# Step 2 review — Codex

## Verdict

**Blocking.** The selected native request path is correctly implemented and genuinely exercised at `chat.completions.create`, but two gating/control-leakage defects violate Step 2's exactness requirements.

## Blocking

1. **`mini-rl-env.py:1196-1205` leaves the alternative `extra_body.reasoning_effort` control in place, where it can override the selected native kwarg.** The cleanup removes nested `reasoning`, `chat_template_kwargs`, and `vllm_xargs`, but not `extra_body["reasoning_effort"]`. Since `--openai-params-json` can seed that form, the real final params can contain both `reasoning_effort="high"` and `extra_body={"reasoning_effort": "none"}`. The OpenAI SDK merges `extra_body` after the normal request body, so the stale value wins on the HTTP wire. This defeats Step 1's selected mapping and the exactly-one-control rule. Strip only this competing key from the copied body while preserving unrelated keys, and seed it in the request-boundary conflict test (`tests/test_inkling_harness.py:151-186`).

2. **`mini-rl-env.py:305-312` makes Inkling retry eligibility a substring match instead of the required exact set.** `my-inkling`, `inkling-v2`, and `thinkingmachines/inkling-preview` all return true and therefore enable both the tracker gate (`mini-rl-env.py:1852-1858`) and runtime gate (`mini-rl-env.py:2158-2160`) on Baseten. This violates the required non-Inkling-on-Baseten negative. Reuse `_is_baseten_inkling_model` for the Inkling arm and add near-miss negatives to `tests/test_empty_retry.py:235-278`.

## Should-fix

- **The boundary/mapper test contract is only partially covered.** The real boundary spy checks only `low` and `xhigh` (`tests/test_inkling_harness.py:188-190`); the other four levels are checked only in synthetic settings, and unknown input is not asserted. Run all six through the boundary spy and add the expected `ValueError` case so `minimal` is protected at the wire as well as in settings.
- **The new “runtime gate” test duplicates rather than executes the runtime initializer.** `_make_runtime` assigns the gate itself (`tests/test_empty_retry.py:138-140`), so `test_inkling_runtime_and_tracker_retry_gates_require_baseten` can pass even if `_BenchmarkRuntime.__init__` regresses. Exercise the real initializer or factor the shared gate into a helper used by both production sites and the test.

## Nice-to-have

- Use a truthy non-Baseten URL in the harness non-interference case (`tests/test_inkling_harness.py:247-258`) and add an explicit non-OpenAI provider negative. `openai_base_url=None` proves the no-custom-endpoint path but does not directly exercise `_is_baseten_endpoint(...) == False` for an alternate endpoint.

## Clean

- Step 1's selected representation is otherwise correct: `settings["extra"]["reasoning_effort"]` becomes a top-level native `create()` kwarg, and the spy calls the real service's `get_chat_completions` boundary rather than inspecting settings only (`tests/test_inkling_harness.py:134-186`). It also proves `temperature=1.0`, `max_tokens=16384`, and no `extra_body` for the controls it seeds.
- The mapper preserves `minimal`, maps `xhigh -> max`, maps the other four levels by identity, and raises `ValueError` for an unknown string (`mini-rl-env.py:347-369`). Validation is genuinely a no-op for the six CLI levels while the existing Baseten budget rejection remains effective (`mini-rl-env.py:1011-1030`).
- The Inkling effort/temperature branch is ordered first inside the Baseten block and is gated by provider, exact model, and endpoint. GLM retains nested `reasoning.effort` for `none/high/max` with no temperature override; Nemotron and the generic/non-Baseten paths are otherwise unchanged. The copied `extra_body` preserves unrelated sibling keys.
- Offline verification: full suite passes **121/121**. The two blockers above are uncovered edge cases, not suite failures.
