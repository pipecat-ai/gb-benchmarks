# Step 3 code review — Codex

## Verdict

**Should-fix.** The eight current configs resolve correctly, the live command uses the per-config cap, and `PRINT_CONFIGS=1` cannot reach the API-key/run/live-request path. One latent parser edge means the claimed 5+-field guard is not complete.

## Blocking

None.

## Should-fix

1. **Trailing empty extra fields are silently accepted.** [`run_baseten_sweep.sh:61`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:61) relies on the fifth `read` target, `_rest`, to detect excess fields, and [`run_baseten_sweep.sh:63`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:63) rejects only a non-empty `_rest`. Bash discards trailing empty IFS fields, so malformed specs such as `slug|model|thinking|16384|` and `slug|model|thinking|16384||` leave `_rest` empty and pass. This does not affect the eight literal entries, but it violates the stated 5+-field hard-error invariant and can hide a future trailing-delimiter typo. Validate the actual delimiter/field count, and add malformed-spec coverage for empty required fields, a non-empty fifth field, and trailing empty fifth/sixth fields.

## Nice-to-have

None.

## Clean

- [`run_baseten_sweep.sh:23`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:23) defines `MAX_TOKENS` before parser definition or invocation. The parser explicitly assigns slug/model/thinking/max-tokens, defaults omitted fourth fields to `MAX_TOKENS`, rejects empty required fields and non-empty remainder data, and no longer uses the old `${rest##*|}` expression ([`run_baseten_sweep.sh:54`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:54)). All five legacy tuples resolve to 8192; the three exact Inkling tuples resolve to 16384, map `inkling-max` to harness `xhigh`, and contain no `inkling-none` ([`run_baseten_sweep.sh:33`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:33)). None of the current model/thinking values contains a pipe.
- The resolved `mt` is assigned from parser output and passed by the only `mini-rl-env.py` invocation as `--max-tokens "$mt"`, not the global cap ([`run_baseten_sweep.sh:111`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:111), [`run_baseten_sweep.sh:143`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:143)). `CONFIG_START`, `RUN_START`, and `RUN_EXIT` all log the same value ([`run_baseten_sweep.sh:127`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:127), [`run_baseten_sweep.sh:141`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:141), [`run_baseten_sweep.sh:161`](/home/khkramer/src/gb-benchmarks/port-to-port/run_baseten_sweep.sh:161)).
- `PRINT_CONFIGS=1` parses every entry, applies the unchanged exact comma-list membership predicate, emits exactly one `CONFIG_PLAN` per selected config, and exits at line 78. API-key access begins at line 88, `RUN_DIR` creation at line 95, and the harness launch at line 143, so none is reachable in print mode. A credential-free traced invocation returned 0, did not open `.env`, did not launch `mini-rl-env.py`, made no external network request, and did not create the supplied `RUN_DIR`.
- Sequential execution is preserved: one config loop contains one rounds loop and one synchronous harness pipeline; the next round/config cannot begin until the current process and `tee` finish. `round_is_done`, `CONFIG_FILTER`, `RUN_DIR` override, failure accumulation, and tally behavior are unchanged. Moving `config_is_selected` and defining `parse_config` earlier introduces no ordering problem or duplicate definition. `set -uo pipefail` is safe on the new path because all parser globals, `_rest`, `MAX_TOKENS`, `CONFIG_FILTER`, and `PRINT_CONFIGS` are initialized before use; failed live runs remain non-fail-fast as before.
- The tests exercise the real parser through `PRINT_CONFIGS`, assert the exact ordered eight-line tuple output, the exact filtered Inkling output, absence of `inkling-none`, no `RUN_DIR` creation, and structural `--max-tokens "$mt"` wiring ([`test_baseten_sweep_configs.py:46`](/home/khkramer/src/gb-benchmarks/port-to-port/tests/test_baseten_sweep_configs.py:46), [`test_baseten_sweep_configs.py:74`](/home/khkramer/src/gb-benchmarks/port-to-port/tests/test_baseten_sweep_configs.py:74), [`test_baseten_sweep_configs.py:85`](/home/khkramer/src/gb-benchmarks/port-to-port/tests/test_baseten_sweep_configs.py:85)). Verification passed: `bash -n`, focused tests 4/4, full offline suite 126/126, and `git diff --check`.
