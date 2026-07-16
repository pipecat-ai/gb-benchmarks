# Plan review — Codex R4

## Verdict

Both R3 blockers and the cost should-fix are resolved. No new blocker or should-fix was introduced by these revisions.

| R3 item | R4 status | Evidence |
|---|---|---|
| B3. Missing-artifact hole in canonical eligibility | **Resolved** | Rules—Data integrity & ops (`PLAN.md:31`) now makes a valid run JSON an independent prerequisite for canonical eligibility, makes every no-JSON attempt non-canonical and rerunnable regardless of exit code, preserves the deterministic first-25-by-attempt-number rule, and caps infra/no-JSON reruns at ≤10 per config before stop-and-report. Step 4 (`PLAN.md:55`) continues to require separate replacement attempt directories and a canonical manifest, while Step 5 (`PLAN.md:59`) consumes only the canonical 25/config. This closes the non-124/no-JSON path without excluding genuine model outcomes that have JSON artifacts. |
| B4. Operational probe rule and dual-working representations | **Resolved** | Step 1 (`PLAN.md:40-43`) specifies five samples for every field/level and five for the no-effort control; exact controlling and inert median thresholds; the native SDK form for the top-level shape; and a deterministic preference order of top-level native `reasoning_effort` → `chat_template_kwargs.reasoning_effort` → nested `reasoning.effort`. It explicitly treats multiple controlling shapes as normal and blocks Step 2 only when no shape controls or the selected field 400s. The expected dual-working result therefore has an executable outcome. |
| Cost/stopping bound | **Resolved** | Rules (`PLAN.md:31`) cap infra/no-JSON reruns at ≤10/config; Step 1 (`PLAN.md:43`) states the approximately 110-request probe matrix; and Step 4 (`PLAN.md:55`) retains the 75-episode base, smoke/rerun accounting, timing estimate, spend confirmation, and smoke go/no-go checkpoint. |

The revised rules remain consistent with the existing preservation/judging split (`PLAN.md:31,33,59`), the smoke and canonical-manifest workflow (`PLAN.md:55`), and the single-control harness implementation gate (`PLAN.md:27,47`). No new ambiguity or workflow regression was found.

**Implementation-ready: Yes.**
