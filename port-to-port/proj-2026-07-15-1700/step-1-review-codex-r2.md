# Step 1 focused re-review — Codex R2

Verdict: **Clean.** All six prior should-fix items are correctly resolved, no new defect was found in the reviewed changes, and the effort-field gate remains the previously reviewed Clean logic. The live findings are consistent with those predicates, but this verdict is based on latent logic review rather than rerun success.

## Blocking

None.

## Should-fix

None.

## Nice-to-have

None. The prior latency-reporting note is also resolved: wall time is explicitly qualified as including configured inter-turn sleep, while summed request time excludes it.

## Clean

1. **`none` folding:** `selected_text_request` omits `tools` and `tool_choice`, and `run_followups` uses it for a distinct `none_text` probe while retaining the forced-tool probe only for usability ([inkling_probe.py:938](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:938), [inkling_probe.py:1505](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1505)). Folding becomes `OBSERVED` only when every requested textual sample succeeds and every successful sample has at least 200 content characters and at most 5 reasoning tokens; otherwise it is `not established` ([inkling_probe.py:1288](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1288)). The Markdown makes canonical exclusion plan-driven when folding is not observed and does not claim diagnostic non-comparability ([inkling_probe.py:1333](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1333)).

2. **Truncation:** `analyze_truncation_record` implements the required four categories. Only an explicit `max_tokens` cutoff, `finish_reason == "length"`, or a well-formed exact prefix proven to hit the cap becomes `confirmed_truncation`; errors/non-2xx become `request_failure`, successful non-length wrong/incomplete results become `model_noncompliance`, and insufficient/complete evidence remains `inconclusive` ([inkling_probe.py:1029](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1029)). The summary counts only `confirmed_truncation` as truncation and displays all four categories separately ([inkling_probe.py:1344](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1344)).

3. **Success predicates:** expected forced calls require exactly one real-ID function call, the correct function name, an argument object, all required keys, and all expected literal values ([inkling_probe.py:428](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:428)). The two-turn episode advances only after the validated turn-1 `lookup_probe` call and completes only when turn 2 has no error, `finish_reason == "stop"`, no tool calls, and exact normalized content equal to `EPISODE_EXPECTED_FINAL` ([inkling_probe.py:1133](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1133)).

4. **Bounds:** all three follow-up sample counts are restricted to `1..20`, and truncation items to `1..20000`; larger values are rejected before client construction ([inkling_probe.py:43](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:43), [inkling_probe.py:1651](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1651)).

5. **Output boundary:** output resolution and validation reject protected harness names, any `runs`/`leaderboards` path component, non-Markdown targets, and paths outside the project or diagnostics-findings roots ([inkling_probe.py:1618](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1618)). `main()` resolves and validates the output and runtime arguments before reading credentials, constructing the client, or issuing a request ([inkling_probe.py:1797](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1797)).

6. **Sweep recommendation:** the emitted section clearly separates diagnostic-inferred `low`/`high`/API-`max`, integration-doc guidance favoring `low` as one pick, and the plan-driven exclusion of `none` ([inkling_probe.py:1430](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1430)).

The bodies of `build_effort_kwargs` and `evaluate_effort_records` remain byte-for-byte the reviewed-Clean implementations: exactly three mutually exclusive request shapes; the exact `max-none >= 50`, `none <= 5`, no-400 control rule; inert classification within ±10 of control; native → chat-template → nested selection; blocking only when no shape controls or the selected field has a 400; and no monotonicity test ([inkling_probe.py:276](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:276), [inkling_probe.py:679](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:679)).

Finally, static inspection shows no harness, run, or leaderboard import. The only filesystem mutation sites are the validated findings-output directory creation and Markdown write, so no harness, `runs/`, or `leaderboards/` file can be written through this script ([inkling_probe.py:1598](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1598)).
