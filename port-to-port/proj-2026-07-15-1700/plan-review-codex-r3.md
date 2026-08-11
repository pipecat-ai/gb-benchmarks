# Plan review — Codex R3

## Verdict

**Not implementation-ready.** The revision resolves both R2 Step-5 blockers and all five R2 should-fixes. The Step-1 decision gate is still not operational, however, and the tightened infrastructure `iff` rule introduces a missing-artifact hole that can make the canonical manifest impossible to realize.

## R2 blockers

| R2 blocker | R3 status | Evidence / remaining issue |
|---|---|---|
| B3. Exact infra classifier and deterministic canonical set | **Resolved for the named terminal/timeout cases; still open for missing artifacts** | Rules—Data integrity & ops (`PLAN.md:31`) now uses the correct `inference_error`, handles exit 124 with no JSON, and selects the first 25 eligible attempts by monotonic attempt number; Step 4 (`PLAN.md:52`) requires a canonical manifest and separate replacement dirs. But the classifier is `iff` and declares “everything else” eligible. A non-124 worker failure that produces no JSON is therefore canonical-eligible, although Step 5 cannot copy, judge, or symlink it. This also conflicts with `../AGENTS.md:502`, which says any no-JSON run must be rerun. Require a valid run JSON for canonical eligibility, or explicitly classify and rerun every missing-artifact attempt regardless of exit code. |
| B4. Predeclared probe threshold and one SDK form | **Still open — blocking** | Step 1 (`PLAN.md:39-40`) now fixes five samples per `(field, level)`, uses medians and a none-to-max effect, rejects monotonicity, and selects the native SDK kwarg for shape (ii). It still leaves the no-effort control's sample count unstated and uses undefined tests/thresholds: `~0`, `>= ~50`, “at high/max,” and “statistically indistinguishable.” More importantly, the authoritative integration doc says both top-level `reasoning_effort` and `extra_body.chat_template_kwargs.reasoning_effort` work (`inkling-baseten-integration.md:28-31`), while Step 1 declares two moving shapes inconclusive. Thus the expected result blocks Step 2. Predeclare exact numeric bounds/equivalence handling and a preference rule when multiple representations work (normally the documented top-level native field). |
| B6a. Judge every new JSON but use only canonical runs for the leaderboard | **Resolved** | Rules (`PLAN.md:33`) and Step 5 (`PLAN.md:55-56`) create derivatives for all new run JSONs and judge all derivatives, while only the canonical 25/config are symlinked into leaderboard input. |
| B6b. Align derivative paths with the builder's resolved-path join | **Resolved** | Rules (`PLAN.md:33`) and Step 5 (`PLAN.md:56`) specify the correct order: create derivatives, judge those exact derivative paths, then symlink those derivatives. |

## R2 should-fixes

All five are resolved:

- `none` is probe/smoke-only and never canonical (Rules, `PLAN.md:34`; Steps 3-4, `PLAN.md:48,52`).
- `leaderboard-natural-filtered.md` receives the same approved scratch bytes (Step 5, `PLAN.md:56`).
- The `25 x 3` assertion is scoped to the initial full-run directory, with a separate canonical manifest for smoke/replacements (Step 4, `PLAN.md:52`).
- The scratch diff explicitly permits Source-runs/Enriched-scores header changes plus Inkling rows (Step 5, `PLAN.md:56`).
- `FC_TIMEOUT=30` is explicitly retained as the Baseten-baseline exception (Step 4, `PLAN.md:52`).

## Other check

The R2 cost/stopping nice-to-have is improved but not actually bounded. Step 4 (`PLAN.md:52`) has a base episode count and requires a pre-launch wall-time/spend check, but infra reruns have no attempt ceiling, no spend ceiling, and the estimate omits the Step-1 matrix (at least 105 requests plus controls/follow-ups). This is a should-fix, not the main readiness blocker.

**Implementation-ready: No.** Make the Step-1 pass/fail rule executable (including the known dual-working representations) and ensure no attempt without a valid JSON can enter the canonical 25.
