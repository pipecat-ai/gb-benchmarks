# Step 4 — Live smoke gate + full sequential run

## Smoke gate (2 episodes, strictly sequential, mt=16384, FC_TIMEOUT=30)

Dir: `runs/inkling-smoke-20260716-025350/` (smoke artifacts kept separate from the canonical run dir).

| Config | thinking→effort | temp | reasoning_tok (min/med/max) | turns | no_tool_call | empties | rate_limit | terminal | JSON+log | rc | success |
|---|---|---|---|---|---|---|---|---|---|---|---|
| inkling-low | low→`low` | 1.0 | 57/89/104 | 30 | 0 | 0 | 0 | finished_tool | ✓ | 0 | True |
| inkling-max | xhigh→`max` | 1.0 | 95/176/421 | 33 | 0 | 0 | 0 | finished_tool | ✓ | 1 | False |

**Gate criteria — ALL PASS:**
1. Correct model / thinking / max_tokens=16384 in config. ✓
2. `temperature=1.0` and exactly one effort control — top-level native `reasoning_effort` on the wire (`low`, and xhigh→`max`); no nested `reasoning.effort`. ✓
3. Successful multi-turn tool-call parsing (30 / 33 turns, `no_tool_call_count=0`). ✓
4. No Baseten API error (`empty_response_count=0`, `rate_limit_count=0`, no inference_failure). ✓
5. Expected reasoning-token behavior — reasoning ON and graded (median 89 @ low → 176 @ max; zero zero-token turns). ✓
6. Run JSON + console log landed for both. ✓

**On the `inkling-max` rc=1:** `mini-rl-env.py:3086` returns `1` when `summary.success` is False. This episode reached the mega-port, recharged to full, returned to start (all True) but `coherent_report=False` — a **task-quality miss, NOT infra** (terminal_reason=`finished_tool`, valid JSON). Per AGENTS.md:502 + the plan's infra-classifier, it is judged, not rerun.

## Cost / stopping estimate
Per-episode wall time: low 62s, max(xhigh) 110s. Full run = 25 × 3 = 75 canonical episodes, strictly sequential at mt=16384 on the 975B Inkling MoE → **≈ 1.5–2 h** (plus any infra reruns). Bounded, comparable to the prior GLM/Nemotron effort. **Decision: GO** (smoke gate passed).

## Full run — RESULTS
CONFIG_FILTER=`inkling-low,inkling-high,inkling-max` (exact list), ROUNDS=25, strictly sequential (one episode/process), preflight asserted 3 selected configs. Initial full-run dir: `runs/inkling-sweep-20260716-025854/` (gitignored — raw JSON/logs preserved on disk per repo convention). Wall time ≈ 2 h.

| Config | JSON | success | task-fail | infra | effort (wire) | temp | reasoned turns | reasoning_tok med(nz)/p90/max | empties | rate-limit |
|---|---|---|---|---|---|---|---|---|---|---|
| inkling-low | 25/25 | **25/25** | 0 | 0 | `low` | 1.0 | 21% | 88 / 353 / 1735 | 0 | 0 |
| inkling-high | 25/25 | **25/25** | 0 | 0 | `high` | 1.0 | 21% | 338 / 4571 / 12626 | 0 | 0 |
| inkling-max | 25/25 | **25/25** | 0 | 0 | `max` | 1.0 | 19% | 336 / 5518 / 13640 | 0 | 0 |

**100% task success across all 75 episodes. Zero infra failures, zero empties, zero rate-limits, zero timeouts.** Every episode terminated `finished_tool` with valid JSON.

**Effort took effect** (spot-check): each config sends exactly its mapped `reasoning_effort` on the wire (`low`/`high`/`max`) at `temperature=1`. Inkling reasons on ~20% of turns (planning) and answers the rest directly. On reasoned turns, effort scales: low median 88 vs high/max ~337 (4×), and the tail grows sharply low→high→max (p90 353→4571→5518; max 1735→12626→13640) — matching the integration doc's "effort inflates the reasoning tail."

**Canonical set:** zero infra failures ⇒ all 25/config in the initial full-run dir are canonical; no reruns, no separate attempt dirs needed. Manifest: `proj-2026-07-15-1700/step4-canonical-manifest.tsv` (75 rows, 25/config, all success=True, all `finished_tool`).

Note: the single smoke `inkling-max` failure (coherent_report=False) was episode variance — the full-run max config scored 25/25.
