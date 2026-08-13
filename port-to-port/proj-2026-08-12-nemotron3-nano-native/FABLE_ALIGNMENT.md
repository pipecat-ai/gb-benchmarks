# Fable alignment check — revised PLAN.md vs FABLE_REVIEW.md and CODEX_REVIEW.md

Date: 2026-08-12. Scope: verify every FABLE_REVIEW blocker and required change
against the revised PLAN.md, and identify material disagreements with Codex's
final position. No files other than this one were modified.

## Blockers — all resolved

- **B1 (reasoning parser).** PLAN.md:37 now uses `--reasoning-parser
  nemotron_3`, with the correct rationale (PLAN.md:42-45): cookbook's
  `deepseek-r1` superseded, model card's `nano_v3` not registered in this
  image, `nemotron_3` keys off `enable_thinking` in both modes. Resolved.
- **B2 (`force_nonempty_content`).** PLAN.md:80-83 permits the harness's
  hardcoded `force_nonempty_content=true` (matching mini-rl-env.py:1561 as it
  exists), qualifies it in both modes, and forbids it from promoting a
  reasoning-truncated completion into an answer/tool call; step 3 flags every
  fallback invocation. This adopts FABLE_REVIEW's recommended option 1 —
  no harness edit needed. Resolved.
- **B3 (flush tooling).** Step 5 names the sequential collection script as a
  deliverable with correct semantics: `POST /flush_cache` before each
  conversation, status + body recorded, retry-while-idle, attempt never
  starts without HTTP 200 (i.e., status-code check, not fire-and-forget),
  Radix caching kept enabled within a conversation, infra-failure logging.
  Resolved.
- **B4 (unproduced metrics).** Step 7 schedules a read-only analysis script
  for completion/reasoning-token distributions, `finish_reason=length`
  (the truncation counter FABLE_REVIEW called non-optional), empty content,
  nonempty-fallback use, and malformed tools. Resolved.

## Required changes — all resolved

1. Image provenance: PLAN.md:21-23 states the image is a patched dirty dev
   build, makes the digest (not HEAD) the identity, and requires saving
   status + full diff with run evidence. Also mirrored in preflight step 1.
2. Flag attribution: PLAN.md:47-48 explicitly labels `--max-running-requests
   1 --context-length 65536 --mem-fraction-static 0.85 --kv-cache-dtype auto`
   as benchmark-local, not cookbook defaults, and pins the expected
   `fp8_e4m3` auto-resolution and FP32-temporal/BF16-conv Mamba state with a
   re-smoke-on-fallback rule (PLAN.md:57-61).
3. `--pipeline-idle-timeout-secs 900`: present (PLAN.md:66).
4. Leaderboard labeling: exact generated identity
   `nemotron-3-nano-30b-nvfp4 (th=none|high, mt=10000, base=127.0.0.1:8000)`;
   hardware/stack description routed to notes/README prose; publication via
   prompt-pure manifest + `build_primary_leaderboard.py` rebuild with diff
   review; no hand-editing or deletion of historical rows (PLAN.md:120-128).
   The served-model-name satisfies the harness's `nemotron*` gate, and the
   on/off → `--thinking high|none` mapping is now explicit (PLAN.md:39, 74).
5. Alternating cadence + "matched" wording: step 6 specifies alternating
   attempts and correctly describes `r01`–`r25` as paired cohort/order
   labels, not seeded scenario variants.
6. Comparability deltas: PLAN.md:133-136 documents Lightning's 1.0/0.95,
   uncapped, unflushed regime; PLAN.md:74-76 notes the 1.0/1.0 pure-reasoning
   vs 0.6/0.95 tool-calling sampling tension.

Non-blocking improvements were also adopted (launch-log acceptance gate with
kernel/backends/scale-warning checks in step 2; EOS 2/11 stop check and
multi-cycle history reconstruction in step 3; unrounded-score admission
wording; memory-fallback posture).

## Position vs Codex's final review

No material disagreement remains. Codex's updated review now specifies
`nemotron_3` (dropping its earlier keep-`deepseek-r1` position), matches on
the dirty-image identity, the permitted-but-flagged `force_nonempty_content`,
flush semantics (attempt excluded unless flush completed idle ≈ plan's
"never begin without HTTP 200"), alternating cadence, r-label semantics,
the reporting set including output-limit stops, and the pipeline idle
timeout. Both reviews and the plan are consistent.

## Residual minor notes (not blockers, no plan change required)

- Detecting "nonempty-fallback use" from client-side run JSON is necessarily
  heuristic (the server does not tag it); the step-3 direct-probe comparison
  makes it tractable, and step 7 should treat reasoning-shaped `content` as
  the flag signal.
- Git housekeeping from FABLE_REVIEW (committing the currently untracked
  canonical leaderboard files at publication time) is not mentioned in the
  plan; it is repository hygiene, not a measurement risk.

## Verdict

All FABLE_REVIEW blockers and required changes are resolved in the revised
PLAN.md, and Fable's and Codex's final positions agree. Clear to proceed to
the preflight smoke gates.
