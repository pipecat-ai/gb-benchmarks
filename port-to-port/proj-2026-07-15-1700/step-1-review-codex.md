# Step 1 code review — Codex

Verdict: the effort-field experiment supports the reported `PROCEED` / native-field selection. There are no blocking defects in that gate, but the follow-up classifications and safety guardrails have several should-fix gaps before Step 1 is fully complete.

## Blocking

None.

## Should-fix

1. **The `none` probe does not establish folded-CoT behavior.** It forces a tool call ([inkling_probe.py:1231](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1231)) and infers folding from visible `content_length` versus another forced-tool probe ([inkling_probe.py:1067](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1067)). Tool-only responses can legitimately have zero visible content, as the live run did. The report then states that “verbose folded reasoning” makes `none` non-comparable even when `folded_content_evidence` is false ([inkling_probe.py:1103](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1103)). Use a textual-answer `none` probe and report “not established” unless folding is observed; retain the forced-tool probe for tool usability.

2. **The truncation classifier conflates unrelated failures with truncation.** Any missing call, invalid JSON, wrong shape, or incomplete sequence becomes `truncation_observed=True` ([inkling_probe.py:920](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:920)), and the summary counts those records without separating request errors ([inkling_probe.py:1112](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1112)). A 401/429/timeout/refusal could therefore be reported as truncation. The live 8192 result is supported by its explicit “Tool calls cutoff by max_tokens” 400, but latent cases should be classified as confirmed truncation, model noncompliance, request failure, or inconclusive.

3. **Tool-call and episode success predicates are too weak for their claims.** `tool_calls_parse_ok` requires only nonempty calls with syntactically valid JSON ([inkling_probe.py:535](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:535)); it does not validate call count, ID, function name, argument object/schema, or expected values. Episodes proceed on any reconstructed call ([inkling_probe.py:971](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:971)) and count as complete when turn 2 merely returns nonempty content ([inkling_probe.py:1012](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1012)). Validate the expected forced-call shape and turn-2 result before claiming parse/episode success.

4. **Follow-up request counts and payload size are not bounded.** Runtime validation enforces positivity only ([inkling_probe.py:1327](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1327)); all sample counts and `truncation_items` remain arbitrarily large through CLI options ([inkling_probe.py:1373](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1373)). A typo can launch an unexpectedly large paid run or allocation. Add conservative upper bounds.

5. **The “only findings Markdown” write boundary is not enforced.** `--output` accepts any path ([inkling_probe.py:1334](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1334)), and the marker writer mutates that target ([inkling_probe.py:1298](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1298)). An accidental harness, run-JSON, or leaderboard path would violate the diagnostic’s read-only guarantee. Restrict output to the project findings Markdown or reject protected/non-Markdown targets.

6. **No sweep-level recommendation is emitted.** The report ends after raw follow-up records ([inkling_probe.py:1169](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1169)), and the result contains no recommendation ([inkling_probe.py:1286](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1286)). State the planned `low/high/max` sweep and explicit exclusion of `none`, or clearly label that choice as plan-driven rather than inferred by this diagnostic.

## Nice-to-have

- Episode wall time includes configurable inter-turn sleep ([inkling_probe.py:999](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:999)) but is reported without that qualification ([inkling_probe.py:1144](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:1144)). The default-zero measurement is accurate; nonzero runs should disclose or subtract the delay.

## Clean

- The control and all three effort shapes are exact and mutually exclusive, with a request-boundary assertion ([inkling_probe.py:247](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:247), [inkling_probe.py:280](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:280)).
- The exact control/inert thresholds, preference order, multiple-controller handling, and BLOCK rule are implemented correctly; there is no adjacent-level monotonicity test ([inkling_probe.py:599](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:599)). Missing token cells conservatively become `N/A` rather than fabricated medians.
- Stream parsing separately captures `reasoning_content`, answer content/tool deltas, and `usage.completion_tokens_details.reasoning_tokens` ([inkling_probe.py:459](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:459), [inkling_probe.py:477](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:477), [inkling_probe.py:494](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:494)).
- Secret and transport handling are sound in the intended invocation: only `BASETEN_API_KEY` is read without printing it ([inkling_probe.py:153](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:153)); SDK retries are zero ([inkling_probe.py:175](/home/khkramer/src/gb-benchmarks/port-to-port/diagnostics/inkling_probe.py:175)); requests are synchronous/sequential at temperature 1; and no harness module is imported.
