# Step 2 re-review — Codex R2

## Verdict

**Clean.** Both Blocking findings, both Should-fix findings, and the Nice-to-have from the prior review are resolved. I found no new defect in the scoped Step 2 changes; non-Inkling behavior remains unchanged.

## Blocking

None.

1. **Resolved — competing `extra_body.reasoning_effort` is removed.** The exact Inkling+Baseten branch copies `extra_body`, removes `reasoning`, `reasoning_effort`, `chat_template_kwargs`, and `vllm_xargs`, preserves unrelated siblings, and removes `extra_body` when empty (`mini-rl-env.py:1198-1218`). The settings test preserves `top_k` (`tests/test_inkling_harness.py:60-106`); the real request-boundary spy seeds all four stale controls and proves mapped top-level `reasoning_effort`, `temperature=1.0`, `max_tokens=16384`, and no final `extra_body` (`tests/test_inkling_harness.py:142-207`).
2. **Resolved — retry eligibility uses the exact Inkling set.** `_is_baseten_retry_eligible_model` retains the GLM/Nemotron substring arms and delegates only its Inkling arm to `_is_baseten_inkling_model` (`mini-rl-env.py:300-312`). Exact positives and the `my-inkling`, `inkling-v2`, and `thinkingmachines/inkling-preview` negatives are asserted, including disabled runtime/tracker gates (`tests/test_empty_retry.py:235-290`).

## Should-fix

None.

1. **Resolved — complete boundary and mapper coverage.** All six levels traverse the real `get_chat_completions`/`create()` boundary with `none/minimal/low/medium/high/xhigh -> none/minimal/low/medium/high/max` (`tests/test_inkling_harness.py:142-207`), and unknown mapper input raises `ValueError` (`tests/test_inkling_harness.py:108-113`).
2. **Resolved — one shared transport-retry predicate.** `_baseten_transport_retry_enabled` contains the prior endpoint-and-model conjunction (`mini-rl-env.py:315-320`) and is used by both the tracker recheck (`mini-rl-env.py:1861-1867`) and runtime initializer (`mini-rl-env.py:2164-2169`). Direct tests cover Inkling on/off Baseten, another Baseten model, all three Inkling near-misses, and the existing GLM/Nemotron positives (`tests/test_empty_retry.py:259-290`).

## Nice-to-have

None. The non-interference test now uses the truthy non-Baseten `https://api.openai.com/v1` path and adds an Anthropic negative whose settings remain unchanged (`tests/test_inkling_harness.py:264-304`).

## Clean

- Step 1's selected representation still holds: Pipecat state sets native `settings["extra"]["reasoning_effort"]`, which reaches `create()` as the top-level `reasoning_effort` kwarg; nested `extra_body.reasoning.effort` is absent (`mini-rl-env.py:1199-1214`, `tests/test_inkling_harness.py:181-195`).
- The new `temperature=1.0` override is confined to OpenAI-provider + Baseten-endpoint + exact Inkling model. The pre-existing GLM/Nemotron Baseten branch remains nested `reasoning.effort` with no temperature change (`mini-rl-env.py:1198-1236`), and the scoped diff leaves generic non-Baseten and other-provider branch bodies unchanged. Their outputs/settings are explicitly checked (`tests/test_inkling_harness.py:115-140,230-304`).
- Verification: focused Inkling tests **7/7**, focused empty-retry tests **10/10**, and full offline `unittest` discovery **122/122** pass. `git diff --check` is clean for the scoped tracked files.
