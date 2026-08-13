# Fable second-pass review of revised PLAN.md

Reviewed: 2026-08-11. Reviewer: Claude (Fable 5). Scope per user decision:
binary comparison only (native reasoning off vs on-unbounded), model card
authoritative, temperature 1.0 / top_p 0.95 in both cells, no client
max_tokens. This pass reuses the first review's evidence (container-source
inspection, HF/API fetches, vLLM issues) plus targeted re-checks performed
today: live GPU/port state, the harness toggle/validation/argparse code paths,
the cookbook's temperature-0.2 example, and the newly cited NVIDIA Gym
recipes directory.

## Verdict

**The revised plan is approved as written.** Every F1–F13 finding is resolved,
correctly scoped out, or faithfully incorporated. The Marlin-first serve plan
matches NVIDIA's only consumer-Blackwell recipe and contains no unsupported
flag. The harness command block is verbatim-correct against the current
`mini-rl-env.py` — I verified each flag's argparse definition and traced the
`--openai-no-budget-thinking-toggle` path end to end, including the two ways
it could have gone wrong (legacy-endpoint matcher capture; factory-injected
budget field) — both are handled. Four residual notes (R1–R4) are advisory,
none blocking.

## F1–F13 disposition

- **F1 (budget-exhaustion tool-call corruption, vLLM #44676) — resolved by
  scope.** The bug requires `thinking_token_budget` in the request; the plan
  sends no budget field in any form (explicitly prohibits
  `thinking_token_budget`, `vllm_xargs.thinking_budget`, `reasoning_effort`),
  so the mechanism cannot fire. The stop condition "reasoning leaks into tool
  arguments" is retained as defense-in-depth. Correct.
- **F2 (DSpark/DFlash V2-runner rejects budgets) — resolved by scope,
  correctly reasoned.** With no budgets, the V2-runner rejection is moot; the
  plan says exactly this (Phase 5) and still requires both reasoning modes in
  every speculative smoke. See R1 for one residual verification.
- **F3 (`force_nonempty_content` not in the pinned chat template) —
  resolved.** The plan now prohibits sending it, with the correct dual
  rationale (template doesn't implement it; port-to-port isn't a coding
  agent).
- **F4 (temperature 0.2 unsourced/confounding) — resolved, and the plan's new
  attribution is accurate.** I re-fetched the raw cookbook: it does contain
  exactly one reasoning-off example at `temperature=0.2, max_tokens=256`,
  while every other example (reasoning on, streaming, tool calling) uses
  1.0/0.95. The plan's account — cookbook suggests 0.2 for a simple off
  example; model card and `generation_config.json` (1.0/0.95) are
  authoritative; 0.2 only in the off cell would confound — is verbatim
  faithful to the sources. Both cells at 1.0/0.95 is the right design.
- **F5 (max_tokens 4096 runaway exposure) — resolved by the no-cap decision.**
  Verified the harness actually implements "no cap": `--max-tokens` defaults
  to `None` and `llm_factory.py:350-352` only adds `max_tokens` to InputParams
  when it is not None — omitting the flag genuinely sends no cap. The plan
  correctly bans both `--max-tokens` and `--thinking-budget` in the command
  block. See R2 (the Gym-recipes justification) and R3 (operational
  consequence of uncapped turns).
- **F6 (backend provenance/risk) — resolved.** Marlin-first now leads, framed
  as NVIDIA's documented consumer-Blackwell path (correct: the DGX Spark
  recipe on the model card is `--moe-backend marlin` + `--kv-cache-dtype
  fp8`, with no linear-backend flag — the plan's "leave linear on
  checkpoint/platform selection" matches it). `flashinfer_b12x` is demoted to
  a later, separately labeled experiment cross-checked against Marlin, citing
  the open SM120 illegal-memory-access report — exactly the first review's
  recommendation. Expected-behavior note: on `auto`, FP4 linear layers on the
  5090 fall back to Marlin W4A16 with a "no native FP4" warning in the log
  (vLLM #47749) — that warning is normal, not a failure; the plan's
  "verify the effective dtype in the log" habit covers it.
- **F7 (`--reasoning-config` double-parsing bug #39103) — resolved.** The
  prohibition is retained with the correct rationale (vLLM derives the config
  from `--reasoning-parser nemotron_v3`).
- **F8 (TTFT/TTFAT/p95 naming) — resolved.** The plan now names `ttfb_ms`,
  `decision_ms`, and turn p50/p90, and explicitly notes the evaluator does
  not natively report p95.
- **F9 (budget-convention labeling) — resolved by scope, and now cleaner than
  the original.** Binary none/high exactly matches the Nemotron 3 Ultra
  precedent (the repo's only prior binary-Nemotron rows) and the harness
  enforces it: with the toggle, `--thinking` must be `none` or `high`
  (`mini-rl-env.py:1226-1230`) and `--thinking-budget` is rejected
  (`:1231-1235`). See R4 on artifact naming.
- **F10 (served name captured by legacy Nemotron branches) — resolved by
  embracing the existing branch instead of adding a new one.** Verified end
  to end today:
  - The toggle's validation requires a Nemotron-matching model name — served
    name `nemotron-3.5-lightning` matches `_is_nemotron_model` — and requires
    `--openai-base-url`. Both satisfied.
  - The one matcher that could have blocked it,
    `_is_nemotron_vllm_017_default_only_endpoint`, requires a host ending in
    `.modal.run` (`mini-rl-env.py:297-305`) — `127.0.0.1:8000` cannot match.
    Baseten matchers likewise cannot match a local URL.
  - Request shaping (`mini-rl-env.py:1549-1568`): sets
    `chat_template_kwargs.enable_thinking = (thinking != "none")` and —
    critically — **pops any `vllm_xargs.thinking_budget`** that
    `llm_factory._merge_openai_extra` injects at construction time for
    thinking-enabled custom-base-URL runs, removing `vllm_xargs` entirely if
    empty. So the final wire payload for both cells is exactly:
    top-level `chat_template_kwargs.{enable_thinking}`, temperature/top_p
    from `--openai-params-json`, no budget field, no max_tokens.
  - Regression coverage exists: `openai-no-budget-thinking-toggle` appears in
    `tests/test_regressions.py` (7 references) and five other test files, so
    Phase 1 step 4's "run existing tests, add only if the payload isn't
    asserted" is the right posture. Recommend the assertion explicitly check
    absence of `vllm_xargs` (not just of `thinking_budget`), matching the
    plan's "no finite budget or max-token field" wording.
- **F11 (memory estimate) — resolved.** The plan reproduces the verified
  numbers (20.08 GiB weights, ~28.66 GiB at 0.9 utilization, 6/52 attention
  layers → small FP8 KV at one sequence) and correctly reframes the OOM
  response as diagnose-utilization-first rather than reflexively halving
  context.
- **F12 (pins/provenance) — resolved.** Launch is by image digest (the digest
  matches the one recorded in the first review); byte totals are now stated
  correctly as safetensors-only (21,561,882,284) plus full 69-file tree
  (21,583,776,209); `--mamba-ssu-algorithm` is excluded with the correct
  README-vs-cookbook rationale; `--kv-cache-dtype fp8` is passed per the
  Spark recipe with log verification; license recorded as OpenMDW-1.1;
  snapshot path matches the verified local snapshot. See R2/R3 for the two
  new, minor unverified items.
- **F13 (judging pipeline gaps) — resolved.** `evaluate_runs.py` + LLM
  report-accuracy judge + `claude-sonnet-4-6` (the argparse default);
  `task_prompt_version` asserted per artifact; RUN_START/RUN_EXIT, no
  fail-fast; leaderboard update made an explicit separate step (an acceptable
  answer to the "add the build step or opt out" finding); precondition 5 now
  checks reasoning-history handling (the harness strips `reasoning_content`,
  which is what Nemotron wants, and the template's
  `truncate_history_thinking` defaults True — so this precondition should
  pass, and it's the right thing to assert).

## Serve-plan flag audit (Phase 2)

Every flag was previously verified to exist in the pinned container's
v0.27.1 source; re-checked against the revised list:
`--moe-backend marlin` (valid choice), `--kv-cache-dtype fp8` (valid;
checkpoint also declares FP8 KV — verify effective dtype in log as planned),
`--max-model-len 65536`, `--max-num-seqs 1`, `--max-num-batched-tokens
32768`, `--enable-prefix-caching`, `--async-scheduling`, `--mamba-backend
flashinfer`, `--mamba-cache-mode align` (required for prefix caching with
mamba — correctly paired), `--mamba-ssm-cache-dtype float16`,
`--enable-mamba-cache-stochastic-rounding`, `--mamba-cache-philox-rounds 5`,
`--reasoning-parser nemotron_v3`, `--tool-call-parser qwen3_coder`,
`--enable-auto-tool-choice`, `--served-model-name nemotron-3.5-lightning`.
**No unsupported or removed flag remains**; the two deliberately excluded
flags (`--mamba-ssu-algorithm`, explicit `--linear-backend`) are excluded for
documented, correct reasons. The Phase 1 note that CPU-only
`vllm serve --help` fails ("Failed to infer device type") is accurate.

## Harness command audit (Phase 4)

All ten flags in the conceptual command block exist with those exact names in
`mini-rl-env.py`'s argparse (`--provider`, `--model`, `--openai-base-url`,
`--openai-no-budget-thinking-toggle`, `--openai-params-json`,
`--task-variant`, `--thinking`, `--max-turns`, `--function-call-timeout-secs`,
`--log-json`). `--openai-params-json '{"temperature":1.0,"top_p":0.95}'` is
the documented mechanism for merging sampling into InputParams (help text at
`mini-rl-env.py:3634-3640`); `--max-turns 50` and
`--function-call-timeout-secs 20` are the existing defaults, so stating them
is harmless pinning. Omitting `--max-tokens` verifiably results in no cap on
the wire. Live state re-verified today: GPU idle at 1,010 MiB (desktop only),
no compute process, port 8000 free — consistent with the plan's claim that
the filler campaign completed and released the GPU without any process being
terminated.

## Residual advisory notes (non-blocking)

- **R1 — Phase 5 DSpark still forces vLLM's V2 model runner** regardless of
  budgets. Whether the V2 runner fully supports the NemotronH hybrid
  (mamba/MoE/attention) architecture was not established by either review
  pass. If it doesn't, the DSpark smoke will fail at launch with a hard error
  — harmless given Phase 5's smoke-first structure, but expect that outcome
  as a possibility rather than a surprise.
- **R2 — "NVIDIA's published agentic evaluation recipes drop the client
  output cap" is plausible but not verified at file level.** The cited Gym
  directory exists (`nemotron_recipes/lightning-3.5/` with `base/`,
  `instruct/`, `reproducibility.md`), and `reproducibility.md` confirms
  temperature-sampled agentic evals, but it defers request parameters to
  individual recipe files I did not exhaustively read. This claim is
  non-load-bearing — the no-cap decision stands independently on the user's
  directive and the documented 4096-runaway failure mode — but if the plan
  wants to keep the sentence, it should cite the specific recipe file, or
  soften to "NVIDIA's recipes do not prescribe a client cap."
- **R3 — operational consequence of no client cap:** a reasoning-on turn is
  now bounded only by the 65,536-token server context, so a pathological
  turn can generate for minutes and terminate via context length
  (`--function-call-timeout-secs` bounds tool execution, not generation).
  The plan's smoke gate and the "repeatedly reasons without producing an
  action" stop condition cover this qualitatively; recommend additionally
  recording per-turn `completion_tokens` and any `finish_reason=length`
  occurrences in the batch summary so runaway frequency is quantified, not
  just gated. Also note the image build commit `6e448d0…` in the pins is
  recorded metadata I did not independently verify (the digest, which is
  what actually pins the launch, was verified).
- **R4 — label consistency:** the plan calls the cells "off" and
  "on-unbounded" while the harness/leaderboard vocabulary will record
  `th=none` and `th=high` (as with Nemotron 3 Ultra's binary rows). Pick the
  run-stem/batch-note convention up front (e.g., stems carry `none`/`high`,
  batch notes explain "high = native unbounded, no client cap") so the
  artifacts don't mix taxonomies.

## Bottom line

No blocking findings. F1–F13 are all closed or correctly out of scope; the
serve command and harness controls are accurate against the pinned container
source and current `mini-rl-env.py`; the sources the revised plan newly cites
check out (including the cookbook's 0.2 example, which the plan represents
honestly). Proceed to Phase 1.
