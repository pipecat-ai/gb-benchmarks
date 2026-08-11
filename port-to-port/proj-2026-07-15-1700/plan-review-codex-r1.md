# Plan review — Codex R1

## Verdict

Not ready to implement as written. The central risk is correctly identified and the ordering `probe -> gated harness change -> sweep -> judge` is sound, but the plan has several execution and reproducibility blockers. In particular, the Step 4 filter would run zero Inkling configs, the proposed one-off `MAX_TOKENS` alternative leaves the default sweep capable of running Inkling at the wrong cap, the rerun policy deletes benchmark data, and the leaderboard workflow is too ambiguous to preserve existing rows safely.

## Blocking

### 1. Step 4's `CONFIG_FILTER=inkling-*` selects nothing

Plan section: Step 4 (`PLAN.md:50-52`).

`run_baseten_sweep.sh:67-75` implements `CONFIG_FILTER` as an exact, comma-separated slug membership test. It does not implement glob matching. The literal value `inkling-*` therefore skips every Inkling config while still allowing the sweep to exit normally after printing skips/tally output.

Required plan change: use an explicit comma-separated list such as `CONFIG_FILTER=inkling-low,inkling-high,inkling-max`, derived from the Step 1 decision. Require a preflight/structural assertion that the selected-config count equals the expected count and that the final raw-JSON count is `25 * selected_configs`; zero selected configs must be a hard error.

### 2. Step 3 must choose a durable per-config token-cap design; the one-off invocation alternative is not sufficient

Plan section: Step 3 (`PLAN.md:46-48`). Code: `run_baseten_sweep.sh:21,43-50,78-83,107-116`.

The current script has one global `MAX_TOKENS`, and every config receives it. A one-off Inkling invocation with `MAX_TOKENS=16384` works only when the exact Inkling filter is supplied. Once Inkling entries live in the common `CONFIGS` array, an ordinary unfiltered sweep would run them at the default 8192; conversely, a global 16384 override on an unfiltered sweep would change GLM/Nemotron. That is an unsafe permanent configuration.

Choose one of these in the plan:

- extend each config to carry its effective cap and parse `slug|model|thinking|max_tokens`, defaulting omitted fourth fields to 8192; or
- put Inkling in a separate sweep script/config list whose fixed/default cap is 16384.

If the four-field design is chosen, explicitly rewrite the parser. The current `thinking="${rest##*|}"` at `run_baseten_sweep.sh:82` would read the fourth field as the thinking level. Tests must assert the effective `(slug, model, thinking, max_tokens)` tuples and the actual command arguments, not only `bash -n`. Log `max_tokens` in `CONFIG_START`, `RUN_START`, and `RUN_EXIT` as well.

### 3. Step 4's deletion/rerun policy violates the repository rules and risks cherry-picking

Plan section: Step 4 (`PLAN.md:50-52`). Code: `run_baseten_sweep.sh:55-64,98-101`.

The instruction to "delete their JSONs to defeat the resume-skip" conflicts with the governing rule that a failed run is benchmark data when raw JSON exists and must be judged rather than discarded. It also makes the canonical sample unclear: replacing failed attempts until 25 successful artifacts remain can hide provider reliability and bias the leaderboard.

Required plan change: preserve every raw JSON and log. Classify reruns using `termination.terminal_reason`/failure telemetry, write reruns under a new attempt stem or run directory, and predeclare which 25 attempts per config are canonical. Judge failed runs that produced raw JSON. If genuine infrastructure replacements are reported separately, document both the original and replacement attempts and the inclusion rule; never delete the originals.

Also tighten resume validation: `round_is_done` currently checks only that `summary.success` is a boolean, not that model/thinking/max_tokens/git SHA match the requested config. Reusing a `RUN_DIR` after changing config can silently skip stale artifacts.

### 4. Step 1 needs an explicit controlled protocol; the existing probe cannot resolve the key question without material work

Plan sections: Current state's probe claim (`PLAN.md:20`) and Step 1 (`PLAN.md:38-40`). Code: `diagnostics/baseten_empty_turn_probe.py:27-49,219-271,1389-1400,1866-2017`.

The current-state claim that the diagnostic is "model-agnostic enough" is misleading for this task:

- `build_extra_body` only emits nested `extra_body.reasoning.effort` (`219-238`);
- its CLI effort choices stop at `high` (`1907-1911`, `1932-1935`, `1957-1960`), so it cannot probe `xhigh` or `max`;
- `reasoning-shape` is GLM-specific and hard-codes `GLM_MODEL` (`1389-1400`);
- request construction does not set Inkling's required `temperature=1` (`241-272`).

Because reasoning-token counts are stochastic and the reference data itself shows overlapping/plateauing counts, one request per field/level cannot reliably distinguish "controlled" from "accepted but ignored." Step 1 should preferably add a small Inkling-specific probe with:

- mutually exclusive request shapes plus a no-effort control (never leave a competing nested/top-level/template control in the same request);
- fixed messages/tools, `temperature=1`, and fixed `max_tokens` for the field comparison;
- repeated samples per field/level and raw request kwargs, status/error, finish reason, content/reasoning lengths, and `usage.completion_tokens_details.reasoning_tokens` recorded;
- explicit coverage of API `max` as well as `none/minimal/low/medium/high/xhigh`;
- a stated decision threshold for selecting the controlling field, with inconclusive evidence blocking Step 2.

The 8192-vs-16384 truncation experiment should be a separate comparison after the controlling field is known, so cap effects do not confound field selection.

### 5. Add a live harness smoke gate before launching 25 rounds/config

Plan sections: Steps 2-4 (`PLAN.md:42-52`). Code: `mini-rl-env.py:2283-2325,2847-2872`; installed read-only Pipecat `services/openai/base_llm.py:249-267`.

Step 1 exercises the OpenAI SDK directly and Step 2 proposes only offline state-mutation tests. The next live harness action is the full sweep. Add a one-episode live harness smoke for every selected effort config (or at minimum the lowest and maximum efforts, plus `none` if included) before the 25-round run. Gate expansion on:

- correct model/thinking/max_tokens in `HARNESS_CONFIG` and raw config;
- `llm_settings` showing temperature 1 and exactly one chosen effort control;
- successful multi-turn tool-call parsing, no Baseten API error, and expected reasoning-token behavior;
- the output JSON and console log both landing.

The plan's proposed verification source is not quite correct: `inference_inputs[].provider_invocation_params` is produced by the adapter at `mini-rl-env.py:2317-2319` and contains context messages/tools, not Pipecat generation settings. `inference_inputs[].llm_settings` (`2323-2325`) shows local state, but not independently the final SDK call. Add an offline request-boundary test that spies on `chat.completions.create` (or asserts `build_chat_completion_params`) and verifies the final kwargs include `temperature=1.0`, `max_tokens=16384`, and the selected effort field. This requires no edit to installed Pipecat.

### 6. Step 5's leaderboard/alias workflow is not reproducible or safely scoped

Plan section: Step 5 (`PLAN.md:54-56`). Code: `build_primary_leaderboard.py:272-278,295-319,329-360,485-540`; root `README.md:23-49`.

Several details must be resolved before implementation:

- The README is `/home/khkramer/src/gb-benchmarks/README.md` (from `port-to-port`, `../README.md`), not `port-to-port/README.md` as the Step 5 key-file list implies.
- `build_primary_leaderboard.py` needs no code alias merely to accept Inkling; it will group/render the raw model `thinkingmachines/inkling`. It supports `--model-name-aliases-json`, but `_build_model_label` deliberately renders an alias as `inkling [thinkingmachines/inkling]` (`295-299`). The vague instruction to "rename model field" risks mutating the authoritative raw JSON (the prior Baseten pipeline did post-process model fields). State whether the full raw name is acceptable or define a non-destructive derivative-copy/alias policy. Do not rewrite raw run artifacts in place.
- The builder requires one enriched row for every resolved canonical input path (`281-291`, `338-346`). To satisfy "without disturbing existing rows," judge only the new Inkling artifacts, combine those enriched rows with the existing canonical enriched JSONL without changing existing entries, then rebuild into a scratch output. Rejudging the entire canonical set with an LLM judge can change unrelated rows.
- `leaderboard-natural-filtered.md` is currently byte-identical to `leaderboard-natural.md`, and there is no separate filtered-builder step in this repository. Specify whether both files intentionally receive the same generated bytes or define the missing filter operation.
- Generate and diff scratch leaderboard/README outputs first; only copy them over the committed files after approval. The plan currently combines "show the diff first" with an underspecified in-place rebuild.

## Should-fix

### 1. Clarify the effort field in terms of both Pipecat state and the HTTP body

Plan sections: Context and Step 2 (`PLAN.md:6,42-44`). Code: `mini-rl-env.py:1110-1117,1158-1175`; installed read-only Pipecat `services/openai/base_llm.py:249-267`.

The key risk is correctly framed, and Step 1 precedes Step 2, so the ordering is correct. However, "top-level `extra_body[\"reasoning_effort\"]`" is ambiguous: it is nested in Pipecat's local `extra_body` kwargs but the OpenAI SDK merges it into the top-level HTTP JSON. The installed SDK also accepts a direct `reasoning_effort` kwarg, which Pipecat can produce via `settings["extra"]["reasoning_effort"]`.

After Step 1, name both shapes explicitly—for example, Pipecat `_settings.extra.reasoning_effort` -> SDK `reasoning_effort` -> top-level HTTP `reasoning_effort`. Whichever representation is selected, remove competing stale controls (`extra_body.reasoning`, direct `reasoning_effort`, and/or `chat_template_kwargs.reasoning_effort`) in the Inkling branch. If the template field wins, the current unconditional `chat_template_kwargs` removal at `mini-rl-env.py:1173` must be changed only for Inkling.

### 2. Temperature and max-token pass-through are viable, but the Current state wording should be tightened

Plan sections: Current state and Step 2 (`PLAN.md:14,17-18,42-47`). Code: `llm_factory.py:246-296`; `mini-rl-env.py:1105-1113,2847-2872`; installed read-only Pipecat `services/openai/base_llm.py:123-133,249-267`.

The proposed approach will reach the request:

- `settings["temperature"] = 1.0` is valid after construction because Pipecat reads `_settings["temperature"]` when building every request;
- `--max-tokens 16384` flows through `LLMServiceConfig`, and `llm_factory.py:263-267` makes that flag override raw OpenAI params.

Thus `--openai-params-json` is not required for the sweep if Step 2 mutates temperature. The Current state claim that temperature "only flows if present in openai_params" is true only of factory construction, not of the full post-construction harness path. Add a conflict test proving an input `temperature=0.2` is overwritten to 1.0 for Baseten Inkling but remains unchanged for every other model/endpoint.

### 3. Test both retry gates explicitly

Plan sections: Current state and Step 2 (`PLAN.md:13,16,43`). Code: `mini-rl-env.py:300-306,622-683,1800-1808,2106-2113,2894-2899`.

Adding Inkling to `_is_baseten_retry_eligible_model` is necessary for transport-empty retry. It must be tested through both runtime initialization (`2106-2108`) and the response tracker's recheck (`1800-1808`), with a non-Baseten Inkling negative case.

The 429/non-429 wrapper already covers Inkling: its behavioral gate is provider OpenAI plus Baseten endpoint at `622-631`, and it is installed at `2894-2899`. No Inkling model alias is needed there. The plan's `2106-2111` citation proves the runtime telemetry flag but is not the wrapper itself; cite both to prevent an implementer from adding an unnecessary model gate to 429 handling.

### 4. Avoid a redundant or misleading Inkling validation branch

Plan section: Step 2 (`PLAN.md:42-44`). Code: `mini-rl-env.py:168,980-998,3076-3079`.

The CLI accepts benchmark levels only through `xhigh`; it does not accept literal `max`. Inkling's `max` is correctly reachable by mapping benchmark `xhigh -> max`. Since every CLI `THINKING_LEVELS` value is valid for Inkling and the generic Baseten branch already rejects exact `--thinking-budget`, an Inkling validation clause may be a no-op. Specify the invariant to validate (all six benchmark levels accepted; exact budget rejected; literal `max` not a CLI value) rather than requiring code solely for symmetry.

Use an exact normalized model-name set such as `{ "inkling", "thinkingmachines/inkling" }`; a broad substring match would create avoidable false positives.

### 5. The `none` gotcha is recognized, but the canonical-sweep rule should be explicit

Plan sections: Rules, Steps 1 and 3 (`PLAN.md:30,38-47`).

The plan does address the folded-CoT behavior before choosing the sweep. Tighten the outcome: either exclude `none` from canonical comparison and start at `low`, or include it as a deliberately labeled folded-CoT configuration and explain how its visible reasoning affects answer cleanliness/comparability. Do not leave the decision as an optional implementation-time choice. `low` should remain the clean-reasoning floor regardless.

### 6. Replace or define the unavailable `cx-delegate` review gate

Plan section: Process rule (`PLAN.md:34`).

No `cx-delegate` executable or callable capability is present in the current environment. Requiring it after every step can halt `/implement` even when the implementation is otherwise complete. Name an available review mechanism or make the second review conditional on availability. Also clarify who is authorized to commit each step; "independently committable" is safer than implicitly requiring automatic commits.

## Nice-to-have

### 1. Correct/qualify the remaining Current state references

- Most requested references are accurate: helpers at `mini-rl-env.py:291,300-338`, Baseten effort construction at `1158-1175`, validation at `980-998`, and runtime gates at `2106-2113`.
- `_create_openai_service` begins at `llm_factory.py:246`; `249-282` lands inside its signature/body and the described max-token/params behavior is accurate.
- The CLI option itself begins at `mini-rl-env.py:3058`; line 3062 is only its help example. Parsing/merge continues at `3135-3138` and `llm_factory.py:263-282`.
- Update the run-script header/config count and field-format comments when Inkling is added (`run_baseten_sweep.sh:2-7,43`).

### 2. Add a cost/time and stopping estimate

At 25 rounds per effort and 16384 tokens/turn on a 975B MoE serverless model, the full sweep can be expensive and slow. Record the selected number of configs, maximum episode count, timeout, and a smoke-to-full promotion criterion before starting. This also makes user approval of the live run meaningful.

## Direct answers to the requested checks

1. The cited harness/factory line ranges are substantially accurate; the diagnostic's claimed model-agnostic readiness and the CLI-option line are not. The actual 429 wrapper gate should also be cited at `mini-rl-env.py:622-683`.
2. The nested-vs-top-level effort risk is real and correctly prioritized. Step 1 is ordered correctly, but its protocol must be made controlled/repeatable and its selected local/wire representation must be unambiguous before Step 2.
3. Temperature 1 is reachable by the planned post-construction `_settings` mutation; no sweep `--openai-params-json` is required. Max tokens 16384 reaches the request through the existing flag/factory path. Add a final-call spy test and live smoke because `provider_invocation_params` does not prove these settings.
4. Per-config max tokens is sound if parsing is rewritten and tested. A mere filtered one-off invocation is not a safe permanent design for a shared config list.
5. The plan recognizes the `none` folded-CoT gotcha, but should turn the optional decision into an explicit canonical-data policy.
6. Inkling must be added to transport-empty eligibility. The 429/non-429 Baseten wrapper already covers it by endpoint. `build_primary_leaderboard.py` does not require a model alias to function; house-style naming needs an explicit non-destructive policy.
7. The zero-match filter, raw-JSON deletion, unspecified leaderboard merge/alias path, missing live harness smoke, and unavailable mandatory `cx-delegate` gate are the main ways `/implement` could fail or produce an unreviewable result.
