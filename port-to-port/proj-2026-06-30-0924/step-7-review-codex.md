# Step 7 Review: GLM-5.2 Baseten Reasoning + API Error Surfacing

## Verdict

Clean, with two nice-to-have coverage additions. I found no blocking or should-fix issues in the step-7 implementation.

## Blocking

None.

## Should-fix

None.

## Nice-to-have

1. Add a regression for the mixed sequence "429 retry attempt, then non-429 APIError". The implementation should handle it correctly: prior 429s only increment `rate_limit_count`, the later non-429 error sets `api_error_pending`, and finalization classifies the turn as `inference_failure` rather than `rate_limit_exhausted` (`mini-rl-env.py:641`, `mini-rl-env.py:647`, `mini-rl-env.py:652`, `mini-rl-env.py:677`, `mini-rl-env.py:1919`, `mini-rl-env.py:1927`, `mini-rl-env.py:1972`). Current tests cover pure 429 exhaustion and pure 400 APIStatusError finalization, but not the mixed retry edge case (`tests/test_rate_limit.py:275`, `tests/test_rate_limit.py:364`).

2. Add explicit validation pass-through tests for Baseten Nemotron non-GLM levels and non-Baseten GLM allowed levels. The code is correctly gated to Baseten GLM before rejecting `minimal|low|medium` (`mini-rl-env.py:980`, `mini-rl-env.py:988`, `mini-rl-env.py:998`), and non-Baseten GLM still flows to the SGLang-specific branch (`mini-rl-env.py:1000`). Existing tests prove Baseten Nemotron uses the generic mapper for `none|high` and GLM SGLang still gets the binary toggle path (`tests/test_regressions.py:1606`, `tests/test_regressions.py:1660`, `tests/test_regressions.py:1880`), but they do not directly assert `_validate_generation_controls` allows Baseten Nemotron `minimal|low|medium|xhigh` or non-Baseten GLM `none|high`.

## Clean

- GLM Baseten effort mapping is correct: `_baseten_glm_reasoning_effort` maps `none -> none`, `high -> high`, and `xhigh -> max`, and rejects other levels with a clear error (`mini-rl-env.py:327`). It is only selected inside the Baseten OpenAI-compatible branch when `_is_baseten_glm_reasoning_model` matches (`mini-rl-env.py:1158`, `mini-rl-env.py:1161`); all other Baseten models keep `_baseten_reasoning_effort` (`mini-rl-env.py:1164`).

- Preflight validation runs before any invalid GLM Baseten effort can be sent: `main()` calls `_validate_generation_controls` during argument handling (`mini-rl-env.py:3141`), while request mutation happens later in `_apply_benchmark_thinking_mode` (`mini-rl-env.py:1093`). The Baseten GLM branch rejects `minimal|low|medium`, allows `none|high|xhigh`, rejects exact budgets for Baseten, and returns before later OpenAI-compatible GLM/SGLang validation can over-reject it (`mini-rl-env.py:980`, `mini-rl-env.py:983`, `mini-rl-env.py:988`, `mini-rl-env.py:998`).

- Non-429 API surfacing mirrors the rate-limit-exhausted marker pattern. The wrapper now catches OpenAI API errors, leaves 429 handling on the existing retry path, marks non-429 errors with `api_error_pending` and `api_error_event`, and re-raises immediately without sleeping or retrying (`mini-rl-env.py:647`, `mini-rl-env.py:648`, `mini-rl-env.py:649`, `mini-rl-env.py:671`, `mini-rl-env.py:673`). The tracker excludes `api_error_pending` from transport-empty matching (`mini-rl-env.py:1817`, `mini-rl-env.py:1818`, `mini-rl-env.py:1934`), classifies it as `inference_failure` before `no_tool_call` (`mini-rl-env.py:1972`, `mini-rl-env.py:1974`, `mini-rl-env.py:1976`), records the API event (`mini-rl-env.py:2013`), clears the marker (`mini-rl-env.py:2041`), and stops with `inference_error` (`mini-rl-env.py:2065`).

- The rate-limit and API-error markers do not collide in the wrapper: 429s go through `_is_openai_rate_limit_error` and never call `_mark_baseten_api_error`; non-429 API errors mark only `api_error_pending` (`mini-rl-env.py:647`, `mini-rl-env.py:648`, `mini-rl-env.py:652`, `mini-rl-env.py:665`). If both markers were somehow set externally, finalization gives `rate_limit_exhausted` precedence over `api_error_pending` (`mini-rl-env.py:1972`), but the step-7 wrapper does not create that double-marker state.

- `run_baseten_sweep.sh` has the requested five configs: GLM `none|high|xhigh` and Nemotron `none|high` (`run_baseten_sweep.sh:43`, `run_baseten_sweep.sh:45`, `run_baseten_sweep.sh:49`).

- The new tests are not superficial. They assert GLM Baseten effort mapping and cleanup of stale Baseten-inapplicable controls (`tests/test_regressions.py:1624`), generic Baseten Nemotron mapping for `none|high` (`tests/test_regressions.py:1660`), GLM Baseten validation reject/allow behavior (`tests/test_regressions.py:1894`, `tests/test_regressions.py:1915`), non-429 APIStatusError no-retry behavior plus final turn classification/event/marker clearing/stop reason (`tests/test_rate_limit.py:364`), and non-status `openai.APIError` marker behavior (`tests/test_rate_limit.py:434`).

## Verification

- `git diff --check -- mini-rl-env.py run_baseten_sweep.sh tests/test_rate_limit.py tests/test_regressions.py`: passed.
- `.venv/bin/python -m pytest tests/test_rate_limit.py tests/test_regressions.py -q`: not runnable in this venv because `pytest` is not installed.
- `.venv/bin/python -m unittest tests.test_rate_limit tests.test_regressions`: passed, 93 tests.
