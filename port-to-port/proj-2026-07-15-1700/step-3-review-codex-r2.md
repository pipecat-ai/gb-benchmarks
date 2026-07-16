# Step 3 focused re-review — Codex R2

## Verdict

**Clean.** The prior Should-fix is resolved: `parse_config` now validates the actual pipe count before parsing, including trailing empty extra fields. I found no new defect in the requested scope.

## Blocking

None.

## Should-fix

None.

## Nice-to-have

None.

## Clean

- [`run_baseten_sweep.sh:58`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:58) derives a string containing only the actual `|` delimiters and rejects every count except two or three before `read` runs ([`run_baseten_sweep.sh:60`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:60)). This rejects fewer than three fields, five-or-more fields, and trailing empty fifth/sixth fields. The four fields are then read explicitly, an omitted/empty optional fourth field defaults to `MAX_TOKENS`, and empty slug/model/thinking values remain hard errors ([`run_baseten_sweep.sh:67`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:67)).
- Positional specs are copied from `$@` only inside the `PRINT_CONFIGS=1` branch, which exits at line 89 ([`run_baseten_sweep.sh:75`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:75)). The non-print path never reads `$@`: its live loop consumes only `"${CONFIGS[@]}"` at line 122, and the synchronous harness pipeline remains nested inside that loop at line 154. Therefore a positional spec cannot select, modify, or reach a live request; sequential live execution is unchanged.
- The literal array remains exactly five GLM/Nemotron configs resolving to 8192 plus three Inkling configs resolving to 16384, with no `inkling-none` ([`run_baseten_sweep.sh:33`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:33)). The resolved cap is assigned to `mt`, passed as `--max-tokens "$mt"`, and logged by `CONFIG_START`, `RUN_START`, and `RUN_EXIT` ([`run_baseten_sweep.sh:129`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:129), [`run_baseten_sweep.sh:138`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:138), [`run_baseten_sweep.sh:160`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:160), [`run_baseten_sweep.sh:172`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:172)).
- The focused tests invoke the real shell parser through its print-only positional hook for both default and explicit valid caps, and assert nonzero exit plus `malformed config` stderr for the requested malformed cases ([`test_baseten_sweep_configs.py:92`](/home/khkramer/src/gb-benchmarks/port-to-port/tests/test_baseten_sweep_configs.py:92), [`test_baseten_sweep_configs.py:104`](/home/khkramer/src/gb-benchmarks/port-to-port/tests/test_baseten_sweep_configs.py:104)). Exact ordered tuple, `inkling-none` absence, filter, no-`RUN_DIR`-creation, and live cap-wiring coverage remain intact ([`test_baseten_sweep_configs.py:53`](/home/khkramer/src/gb-benchmarks/port-to-port/tests/test_baseten_sweep_configs.py:53), [`test_baseten_sweep_configs.py:81`](/home/khkramer/src/gb-benchmarks/port-to-port/tests/test_baseten_sweep_configs.py:81), [`test_baseten_sweep_configs.py:118`](/home/khkramer/src/gb-benchmarks/port-to-port/tests/test_baseten_sweep_configs.py:118)).
- Verification passed: `bash -n run_baseten_sweep.sh`; focused sweep tests 6/6; full offline suite 128/128; `git diff --check`.
