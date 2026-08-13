# Fable adversarial review of PLAN.md

Reviewed: 2026-08-11. Reviewer: Claude (Fable 5).
Method: three independent evidence passes — (1) the local harness/repo
(`mini-rl-env.py`, `llm_factory.py`, `evaluate_runs.py`, sweep scripts,
leaderboards), (2) live host state plus a CPU-only inspection of the actual
pulled `vllm/vllm-openai:v0.27.1` container source, and (3) online primary
sources (Hugging Face model/API endpoints, the raw NVIDIA cookbook notebook,
docs.vllm.ai v0.27.1, vllm-project GitHub issues/PRs). All fetched 2026-08-11.

## Verdict

The plan is fundamentally sound: the checkpoint pin, shard count and byte
total, parser names, quantization description, container tag, cookbook flags,
`thinking_token_budget` request shape, kernel-trial rationale, and the 32 GB
memory budget all check out against primary sources. The "prove the budget
works before relying on it" gate and the binary-fallback plan are exactly
right — and they will be needed, because the budget feature's interaction
surface has **three open vLLM bugs directly on this plan's critical path**
(tool-call corruption at budget exhaustion, `--reasoning-config`+`nemotron_v3`
breakage, and a hard incompatibility between DSpark/DFlash and
`thinking_token_budget`). Separately, two plan requirements are wrong as
written: `force_nonempty_content` does not exist in this checkpoint's chat
template (it would be a silent no-op enshrined in regression tests), and the
reasoning-off `temperature 0.2` has no support in the model card, the
checkpoint's `generation_config.json`, or any prior run in this repo — it
would introduce a second uncontrolled variable into the `none` cell.

Findings below, ranked. F1–F5 should change the plan before execution.

---

## F1 (blocking): `thinking_token_budget` corrupts `qwen3_coder` tool calls at budget exhaustion — open bug, exact stack in this plan

vLLM issue [#44676](https://github.com/vllm-project/vllm/issues/44676) (open,
affects 0.22.0+, no merged fix as of today): when the thinking budget is
exhausted **while the model is inside a tool call**, `ThinkingBudgetStateHolder`
does not treat `<tool_call>` as an implicit reasoning end, so forced
`reasoning_end` tokens are injected mid-JSON, corrupting the arguments
(~0.5% of production tool calls in the reporter's data). The issue explicitly
involves the `qwen3_coder` parser this plan uses.

Why the plan's current preconditions won't catch it: precondition 4 (budget
probes at 128/512) and precondition 5 (streaming tool call round-trip) test
budget enforcement and tool calling **separately**. The failure mode only
fires when exhaustion lands mid-tool-call. At a 0.5%-per-call rate, a
4-cell × 25-run × up-to-50-turn sweep can expect a handful of corrupted calls
— enough to pollute completion-rate comparisons across effort cells (lower
budgets exhaust more often, so corruption rate would correlate with the
independent variable).

Required changes:
- Add an explicit adversarial precondition: a tool-heavy prompt with a small
  budget (e.g. 64–128) run repeatedly (≥20 attempts) to force exhaustion
  during tool-call emission; inspect raw streamed output for `</think>` /
  reasoning-end fragments inside `arguments`.
- During the sweep, log and count per-cell malformed-tool-call turns and
  check whether the count anti-correlates with budget size before comparing
  cells. The existing stop condition ("tool-call JSON is corrupted") is right
  but should be triggered on this specific signature, not just wholesale
  failure.

## F2 (blocking): Phase 5 DSpark and DFlash are incompatible with `thinking_token_budget` in v0.27.1; only built-in MTP is compatible

Verified in the pulled container's source (`config/vllm.py`):
`use_v2_model_runner` is **forced on** when `speculative_config.method ==
"dspark"`, and also for DFlash drafts that mix sliding/full attention layers.
The V1 input processor (`v1/engine/input_processor.py:111-126`) **rejects any
request carrying `thinking_token_budget` on the V2 runner** ("not yet
supported by the V2 model runner"). Forcing `VLLM_USE_V2_MODEL_RUNNER=0` is
not a workaround: dspark is implemented only by the V2 GPU model runner.

So Phase 5 steps 2 and 3 as written (DSpark/DFlash "confirm budget enforcement
again") cannot work — every budgeted request will raise a validation error.
DSpark/DFlash can only ever serve the binary `none`/`unbounded` cells.

For built-in MTP: `NemotronHForCausalLM` is not in
`DEFAULT_V2_MODEL_RUNNER_ARCHITECTURES` and the hybrid model defaults to the
V1 runner, where `v1/sample/thinking_budget_state.py` is explicitly
spec-decode-aware (tracks `num_spec_tokens`, applies forcing to the bonus
token). So MTP + budget is an engineered path in 0.27.1 — but note issue
[#39573](https://github.com/vllm-project/vllm/issues/39573) ("thinking token
budget not enforced with MTP speculative decoding") was still **open** at
fetch time; a third-party blog claims it was later fixed, but that is not a
primary source. The plan's "confirm budget enforcement again under each
speculative mode" is exactly the right control for MTP — keep it, and expect
hard request-level errors (not silent non-enforcement) for DSpark/DFlash.

Required change: rewrite Phase 5 to state that budgeted cells can only be
tested under base decoding and built-in MTP; DSpark/DFlash comparisons run
binary-only. Do not set `VLLM_USE_V2_MODEL_RUNNER` at all.

## F3 (blocking): `force_nonempty_content` does not exist in this checkpoint's chat template — the plan mandates a silent no-op

The downloaded snapshot's `chat_template.jinja` (revision `e7fa1b0`, 9,867
bytes) contains **no reference to `force_nonempty_content`** (verified by
grep; also absent from `tokenizer_config.json`). Jinja silently ignores
unknown kwargs, so `chat_template_kwargs.force_nonempty_content=true` on
every agentic request would do nothing — and the plan's Phase 1 step 4
regression tests would permanently enshrine a dead parameter as "required."

The confusion is understandable: the HF model card *does* mention it ("For
coding agents, add `extra_body={"chat_template_kwargs":
{"force_nonempty_content": True}}`"), and Nemotron 3 Ultra's NIM docs
required it alongside `enable_thinking` when `tools` are present. But the
card and this checkpoint's template currently disagree — the template
implements only `enable_thinking` (default **True**, line 12) and
`truncate_history_thinking` (default True). A prior repo investigation
reached the same conclusion for Baseten and explicitly recommended keeping it
out (`proj-2026-06-30-0924/step1-diagnostic-findings.md:20`).

Required change: drop the requirement, or demote it to a Phase 1 probe —
render the template with and without the kwarg and diff the output. If NVIDIA
later ships a template revision that implements it, that's a new checkpoint
pin, not a flag flip. Meanwhile, add the check the template *does* support:
verify that with `enable_thinking=false` + `tools`, the model still emits
well-formed tool calls (Nemotron 3 Ultra documentation implied tools required
thinking on; whether Lightning's `none` cell can do agentic tool calling at
all is an untested assumption the smoke matrix should settle — the plan's
Phase 3 smoke at `none` covers this, good).

## F4 (high): reasoning-off `temperature 0.2` has no basis in any source and confounds the sweep

Three independent checks all came back negative:
- Model card: "Recommended Sampling: Temperature 1.0, Top_P 0.95" — given
  **uniformly**, with no separate reasoning-off profile.
- Checkpoint `generation_config.json`: `temperature=1.0, top_p=0.95`.
- This repo: no sweep script, harness branch, doc, or leaderboard row has
  ever used 0.2 for a reasoning-off cell (prior reasoning-off runs used 0.6,
  1.0, or provider defaults; Baseten Gemma4 deliberately used 1.0/0.95 for
  *both* on and off).

As written, the `none` cell would differ from the budgeted cells in **two**
variables (thinking and temperature), so any `none`-vs-`low` delta is
unattributable. Recommended: temperature 1.0 / top_p 0.95 for all four cells,
matching the card, the checkpoint default, and the repo's cleanest precedent.
If 0.2 came from some other NVIDIA guidance, cite it in the plan; otherwise
this is an invented constant.

## F5 (high): `--max-tokens 4096` is the repo convention but is a known failure mechanism for unbounded reasoning — the fallback baseline is exposed

The flag exists and 4096 matches prior local sweeps verbatim
(`setup_qwen35_4b_27b_none_batch.sh:46-47`), so the budgeted cells are fine:
a ≤2048 thinking budget structurally leaves ≥2048 tokens for content.

But the 2026-06-29 Baseten analysis found the exact failure this invites:
with reasoning on and no budget, models consumed the entire 4096 as reasoning
and got truncated before emitting a tool call (~61 failed turns; conclusion
was "do not cap at 4096 for these models," re-run at 8192). The plan's own
contingency — "run only the accurately labeled binary `none` versus
`unbounded` baseline" — is precisely an unbounded-reasoning configuration at
max_tokens 4096. If that branch triggers, it inherits the runaway-truncation
mechanism and its completion rate will measure truncation, not reasoning.

Recommended: keep 4096 for the four budgeted cells (cross-row comparability),
but pre-decide and write down that an unbounded cell runs at 8192 (or higher)
with the max_tokens recorded in the label/run metadata, as
`run_baseten_sweep.sh`'s 4-field config format already supports. Also track
per-turn `completion_tokens == max_tokens` truncation counts in every cell.

## F6 (high): backend trial order is defensible, but the plan overstates the `flashinfer_b12x` provenance and understates its risk

Confirmed facts:
- `--linear-backend` / `--moe-backend` exist in v0.27.1 with `flashinfer_b12x`,
  `marlin`, and `humming` among the valid choices (verified in both
  docs.vllm.ai/en/v0.27.1 and the container's `config/kernel.py`).
- `flashinfer_b12x` is the vLLM-native SM120/121 NVFP4 path (PR
  [#40082](https://github.com/vllm-project/vllm/pull/40082), merged
  2026-05-20; container docstring: "FlashInfer CuteDSL fused MoE for SM12x").
- It is **intentionally excluded from `auto` selection**
  (`fused_moe/oracle/nvfp4.py:176` — explicit opt-in required), which
  validates the plan's explicit-flag approach; on `auto`, an RTX 5090 falls
  back to Marlin W4A16 with a "no native FP4" warning (issue
  [#47749](https://github.com/vllm-project/vllm/issues/47749)).

Corrections and risks:
- "vLLM documents these as the native NVFP4 SM120+ paths" is fair, but note
  that **no NVIDIA recipe uses `flashinfer_b12x`**. NVIDIA's own
  consumer-Blackwell recipe (DGX Spark GB10, on the model card) is
  `--moe-backend marlin` + `--kv-cache-dtype fp8` + DSpark; the H100 cookbook
  recipe is `humming`. There is no NVIDIA RTX 5090 command anywhere — the
  5090 is only listed as supported hardware. So step 2's marlin fallback is
  not merely "compatible," it is the closest thing to an NVIDIA-endorsed
  config for this class of GPU; expect to land there without treating it as
  a failure.
- Open issue [#50189](https://github.com/vllm-project/vllm/issues/50189)
  (2026-07-28): Xid 31 MMU fault / illegal memory access with forced
  `flashinfer_b12x` under chunked prefill on SM120 with
  `--max-num-batched-tokens 32768`, FP8 KV, and prefix caching — nearly this
  plan's config. That report used 16-way concurrency; `--max-num-seqs 1`
  greatly reduces exposure but doesn't prove immunity. The plan's stop
  condition already names illegal-memory-access errors — good; if b12x is
  kept, also compare a short fixed replay against marlin output for
  numerical sanity before trusting a full sweep on it. Related SM120
  volatility: [#47365](https://github.com/vllm-project/vllm/issues/47365)
  (b12x garbage output under TP/PP — N/A single-GPU but shows path churn),
  [#35065](https://github.com/vllm-project/vllm/issues/35065).

## F7 (medium): thinking-budget request shape and serve-time requirements — plan is correct, with two sharp edges

Confirmed in the container source and v0.27.1 docs, answering the plan's
Question 1 precisely:
- `thinking_token_budget` is a **top-level Chat Completions request field**
  (`entrypoints/openai/chat_completion/protocol.py:257`), i.e. sent via the
  OpenAI SDK as `extra_body={"thinking_token_budget": N}` landing at the top
  level of the JSON body. The plan's rejection of `vllm_xargs.thinking_budget`
  (the harness's existing generic path, `mini-rl-env.py:1629-1642` /
  `llm_factory.py:134-146`) is correct — the wrong shape is **silently
  ignored** (community report:
  discuss.vllm.ai/t/thinking-token-budget-silently-ignored-.../2533).
- No explicit `--reasoning-config` is needed: `arg_utils.
  _set_default_reasoning_config_args` auto-builds the ReasoningConfig from
  `--reasoning-parser nemotron_v3`. **Do not pass `--reasoning-config`
  explicitly** — open issue
  [#39103](https://github.com/vllm-project/vllm/issues/39103): explicit
  `--reasoning-config` + `nemotron_v3` double-parses, leaving content always
  null and thinking unbounded.
- Caveat the plan should carry: the v0.27.1 docs' supported-parsers table for
  thinking budget does **not** list `nemotron_v3` (prose says "Qwen3,
  DeepSeek, and Nemotron3 support a thinking budget"; the table omits it).
  Budget-with-nemotron_v3 is therefore effectively undocumented; the plan's
  Phase 3 precondition 4 (materially different bounded reasoning-token counts
  at 128 vs 512) is the correct empirical gate. Keep it non-negotiable.
- Budget semantics: non-negative int, `-1` = unlimited; requests raise if no
  reasoning parser/config is active on the server.

## F8 (medium): metric names and percentiles don't match the pipeline that will produce them

"TTFT" and "TTFAT" appear nowhere in the repo. The harness measures Pipecat
**TTFB** per turn (`ttfb_ms`, `mini-rl-env.py:890-907, 2402-2404`;
`pipecat .../base_llm.py:390,448`) and per-turn `decision_ms`
(`mini-rl-env.py:2248-2251`), and `evaluate_runs.py` aggregates **p50/p90**
(`turn_p50_ms`/`turn_p90_ms`, `evaluate_runs.py:2055-2090`) — not p95. The
leaderboard columns are "Turn P50 (ms) | Turn P90 (ms)". The plan's
underlying claim — that using the same OpenAI/Pipecat service keeps latency
semantics identical to other OpenAI-compatible rows — is confirmed; just
rename the deliverables to ttfb/decision p50/p90, or scope new p95/TTFAT
computation as explicit new work.

## F9 (medium): "existing Nemotron budget convention" is true for Super/Nano, false for Ultra

The proposed none/128/512/2048 mapping exactly matches the harness-wide
`THINKING_BUDGET_MAP = {"minimal": 0, "low": 128, "medium": 512,
"high": 2048}` (`mini-rl-env.py:175`) and the Nemotron 3 **Super-120B /
Nano-30B** leaderboard rows (`leaderboard-natural.md:67-90`, `tb=128/512/2048`).
Nemotron 3 **Ultra** on Baseten was binary none/high with no budget
(`leaderboard-natural.md:39,65`; Baseten endpoints reject `--thinking-budget`).
Cite Super/Nano, not "Nemotron," and the claim is solid.

On Question 5: keep none/128/512/2048 as the canonical four cells — it is the
defensible, precedent-matching choice, and relabeling the 2048 cell
"unbounded" would break comparability with the Super/Nano rows. If an
unbounded cell is wanted (recommended, since Ultra's `high` is effectively
unbounded and it anchors the budget curve), add it as a fifth, distinctly
labeled cell (e.g. `xhigh`/`unbounded`, `thinking_token_budget` omitted or
`-1`) rather than renaming `high` — and see F5 for its max_tokens.

## F10 (medium): the served model name will be captured by the harness's existing Nemotron branches — Phase 1 step 4 must handle dispatch order

`_is_nemotron_model` matches any model name starting `nemotron`/
`nvidia/nemotron` (`mini-rl-env.py:256-258`), so served name
`nemotron-3.5-lightning` will hit the existing Nemotron validation and
request-shaping branches (`mini-rl-env.py:1216-1236, 1272-1286, 1549-1568`)
**before** any generic fallback — including the
`--openai-no-budget-thinking-toggle` branch that strips
`vllm_xargs.thinking_budget` and sets `chat_template_kwargs.enable_thinking`.
The new Lightning mode isn't just additive; it must be ordered/guarded so the
legacy Nemotron branches don't hijack or half-apply. Regression tests should
assert (a) the exact wire payload for all four cells (top-level
`thinking_token_budget`, `chat_template_kwargs.enable_thinking`, no stray
`vllm_xargs`), and (b) that the legacy branches do not fire for the Lightning
served name. Note there is no mode registry — modes are if/elif chains in
three places (`llm_factory.py:323-345`, `_validate_generation_controls`,
`_apply_benchmark_thinking_mode`), all three of which need the branch.

## F11 (low): memory estimate is realistic — Question 3 answered yes, with numbers

Weights: 21,561,882,284 B = 20.08 GiB. Total VRAM 32,607 MiB = 31.84 GiB;
~1 GiB stays held by desktop/graphics processes even after `llama-server`
(PID 3472320, 21,152 MiB, confirmed live) exits — so "near-idle," not zero,
is the right Phase 2 expectation, and `nvidia-smi` will still list graphics
processes (the plan's "no compute process" criterion is correctly worded).
At the default `gpu_memory_utilization=0.9` the budget is 28.66 GiB, leaving
~8.6 GiB after weights for everything else. KV cache is nearly free here:
only 6 of 52 layers are attention (config: 23 mamba + 23 moe + 6 attention),
FP8 KV → order 0.7–1 GiB at 65,536 context even with generous head
assumptions. Mamba SSM/conv cache at `--max-num-seqs 1` is small, and the
plan's float16 SSM cache (config default is float32) halves it, matching the
cookbook. Chunked-prefill activations at 32,768 batched tokens plus CUDA
graphs fit comfortably in the remainder. 65,536 context / seqs=1 / FP8 KV /
FP16 SSM is a safe starting point; the stop-condition fallback to 32,768
context is unlikely to ever be the binding lever (context barely moves memory
here — `gpu_memory_utilization` and batched tokens are the real knobs).
Two nits: `lm_head` is also NVFP4-quantized (plan's quant summary omits it),
and attention q/k/v/o projections are unquantized BF16 — neither changes the
conclusion.

## F12 (low): pins, provenance, and source-disagreement notes

- Revision `e7fa1b0bdaf462c67c7f0bf638addacd89fd3054` exists and its snapshot
  is fully downloaded (52/52 shards, exact byte total 21,561,882,284,
  `DOWNLOAD_EXIT=0` at 10:50 local; the earlier ~9-minute shard-7 xet retry
  stall resolved itself). But the byte figure is the **safetensors-only**
  sum; the full file tree is 21,583,776,209 B across 69 files (tokenizer.json
  ~17 MB etc.). The plan's Phase 1 step 1 verification should count against
  the right total. All structural files (config, index, tokenizer, chat
  template, `hf_quant_config.json`) are present locally.
- `e7fa1b0` is **not HEAD** (HEAD `1de6d84`, README-only); both are
  README-only commits, so pinned weights == HEAD weights. However the repo is
  churning: MTP tensors were **replaced ~6 hours before review** ("Delete
  BOOSTED_MTP_REPLACEMENT.json" / "Upload 7 files"), 8 commits in 24 h. The
  pin post-dates the MTP replacement (good), but re-verify the pin against
  HEAD before Phase 5 MTP tests, and treat any further weight commit as the
  plan's existing digest-mismatch stop condition.
- Notable: the commit `e7fa1b0` itself **deleted `--mamba-ssu-algorithm
  horizontal` from the README's vLLM command**, while the cookbook notebook
  still carries that flag — NVIDIA's two deployment sources currently
  disagree. The plan's Phase 3 flag list correctly omits it; make that
  explicit ("do not pass `--mamba-ssu-algorithm`") since the cookbook is the
  plan's primary reference.
- Container: `vllm/vllm-openai:v0.27.1` is now pulled; digest
  `sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967`,
  vLLM reports 0.27.1, Python 3.12. The image behind this version tag was
  **created ~8 hours ago** — version tags evidently get rebuilt — so launch
  by digest (`vllm/vllm-openai@sha256:0a51ea5b…`), not by tag, to make the
  recorded pin actually binding.
- KV-cache flag: the cookbook passes **no** `--kv-cache-dtype`; the DGX Spark
  recipe passes `--kv-cache-dtype fp8`. The checkpoint itself declares FP8 KV
  (`kv_cache_scheme` in config.json, `kv_cache_quant_algo: "FP8"` in
  `hf_quant_config.json`), so vLLM should apply it from the checkpoint.
  Whichever way the launch command goes, verify the effective KV dtype from
  the server log rather than assuming the flag did it.
- License: the model ships **OpenMDW-1.1** (LICENSE committed 4 days ago; HF
  metadata `license: other`), not the NVIDIA Open Model License. Commercial
  use permitted per the card. Record OpenMDW-1.1 in the batch metadata
  (relevant to plan Question 6).
- Cookbook cross-check: image tag, `--served-model-name
  nemotron-3.5-lightning`, `nemotron_v3`, `qwen3_coder`,
  `--enable-auto-tool-choice`, `--max-model-len 65536`,
  `--max-num-batched-tokens 32768`, prefix caching, async scheduling,
  `--mamba-backend flashinfer`, `--mamba-ssm-cache-dtype float16` +
  stochastic rounding + 5 Philox rounds + `--mamba-cache-mode align` all
  match the cookbook verbatim (cookbook default `--max-num-seqs 256`; plan's
  1 is a deliberate benchmark divergence — fine, but record it). Cookbook
  validation hardware is one H100 80 GB (SM90) — the plan's "reference, not
  default on SM120" stance is confirmed correct. Prefix caching with mamba
  requires cache mode `align` (container `config/cache.py`) — the plan pairs
  them correctly. Spec decoding in the cookbook uses
  `--speculative_config.num_speculative_tokens 3` (plan's "3" matches) and
  MTP drops max-num-seqs to 128 (irrelevant at seqs=1). The ThinkingBudgetClient
  two-request pattern with `/v1/completions` for the second leg is confirmed
  verbatim — the plan's reason for rejecting it (latency semantics + tool-call
  reparsing) is valid.
- Draft models: DFlash ≈ 1.177 GB and DSpark ≈ 1.349 GB (HF `usedStorage`),
  matching the plan's ~1.18/~1.35 GB; DSpark "recommended for DGX Spark, as
  well as low-concurrency data centre deployments" — plan claim confirmed.
  Neither is in the local HF cache yet, consistent with Phase 5 deferral.
  Note both draft repos were updated hours ago (same churn wave).
- Container registries confirm everything Phase 1 step 3 wants to check:
  `NemotronHForCausalLM` (model registry), `modelopt` + `modelopt_mixed`
  (quant registry), `nemotron_v3` (reasoning registry), `qwen3_coder` (tool
  registry, alias of `qwen3_xml`), `nemotron_h_mtp`/`dflash`/`dspark`
  (speculative methods). One trap: `vllm serve --help` **fails in a CPU-only
  container** ("Failed to infer device type"), so Phase 1 step 3 should
  inspect flags via source grep or run `--help` only after the GPU is free.

## F13 (low): logging/judging pipeline claims check out; two small gaps

Confirmed as current convention: `--log-json` + tee'd console per run;
`--max-turns 50` (default), `--function-call-timeout-secs 20` (default),
`--max-tokens` (openai provider only — fine here); `RUN_START`/`RUN_EXIT`
markers (`run_repeat_clean_config.sh:56,59` and every recent sweep script);
25 sequential repetitions with UTC-timestamped stems; failed-run retention;
natural prompt is `DEFAULT_TASK_VARIANT` at version v1 with
`task_prompt_version` recorded in run JSON (satisfies the "prompt revision
changes mid-batch" stop condition — assert this field, not vibes);
`evaluate_runs.py --report-accuracy-judge llm` with default judge model
exactly `claude-sonnet-4-6` (its argparse default, and what every recent
batch used; judge runs at temperature 0). Gaps: (a) the plan stops at
evaluation — the established pipeline continues to
`build_primary_leaderboard.py --runs-glob '<dir>/*/*-r[0-9][0-9].json'
--enriched-jsonl … --leaderboard-prompt-id natural` (glob restricted so
`eval/` artifacts are skipped); add it or state the batch intentionally stays
off-leaderboard. (b) Multi-turn reasoning-content handling: the harness/
Pipecat path strips `reasoning_content` from history, which is what Nemotron
wants, and the chat template's `truncate_history_thinking` (default True)
handles the template side — worth one precondition assertion (precondition 6
nearly covers it; make the reasoning-stripping explicit in what it checks).

## Answers to the plan's questions for Fable

1. **Yes.** `thinking_token_budget` is a top-level Chat Completions field in
   v0.27.1 (protocol.py:257), sent via `extra_body`. No explicit
   `--reasoning-config` is needed — `--reasoning-parser nemotron_v3`
   auto-builds it — and passing one explicitly **breaks** nemotron_v3
   (#39103). But support for nemotron_v3 is absent from the docs'
   supported-parser table, and budget exhaustion mid-tool-call corrupts
   qwen3_coder arguments (#44676): keep the empirical gate, add the
   forced-exhaustion tool-call probe (F1, F7).
2. **Trial order is right; expectations need adjusting.** `flashinfer_b12x`
   is the vLLM-native SM120 NVFP4 path and requires explicit opt-in (`auto`
   will never select it — it falls back to Marlin W4A16). But no NVIDIA
   recipe uses it, NVIDIA's consumer-Blackwell recipe is marlin, and b12x has
   an open SM120 illegal-memory-access issue under a config resembling this
   one (#50189). Try b12x first, but treat marlin as the expected
   production-grade landing spot, not a degraded fallback, and cross-check
   b12x numerics against marlin on a short replay before sweeping on it (F6).
3. **Yes, comfortably.** 20.08 GiB weights against a 28.66 GiB
   0.9-utilization budget; only 6 attention layers so FP8 KV at 65k context
   is under ~1 GiB; FP16 SSM cache at seqs=1 is small; ~8.6 GiB headroom
   covers activations/CUDA graphs. Budget ~1 GiB for lingering desktop
   allocations. The 32,768-context retry is unlikely to ever be the fix for
   an OOM here (F11).
4. **Yes — two known interactions.** (a) qwen3_coder: #44676, reasoning-end
   tokens injected mid-tool-call at budget exhaustion — add the targeted test
   (F1). (b) Speculative decoding: budget works with built-in MTP on the V1
   runner (verify enforcement anyway; #39573 history), but DSpark and
   mixed-attention DFlash force the V2 runner, which **rejects**
   `thinking_token_budget` outright — Phase 5 must scope those to binary
   cells (F2).
5. **Keep none/128/512/2048** — it exactly matches the Nemotron 3 Super/Nano
   precedent and the harness `THINKING_BUDGET_MAP`. Don't relabel high as
   unbounded; if an unbounded anchor is wanted, add it as a distinct fifth
   cell with its own max_tokens decision (F5, F9).
6. Missing details: license is **OpenMDW-1.1** (not NVIDIA Open Model
   License); launch by image **digest**, not the mutable v0.27.1 tag;
   explicitly exclude `--mamba-ssu-algorithm` (NVIDIA just removed it from
   the README while the cookbook still has it); record effective KV-cache
   dtype from the server log; the 21,561,882,284 figure is safetensors-only
   (full tree 21,583,776,209 B); fix TTFT/TTFAT→ttfb/decision p50/p90 naming;
   `force_nonempty_content` is not implemented by this checkpoint's template;
   reasoning-off temperature 0.2 is unsourced — use 1.0/0.95 everywhere; the
   served name will trip the harness's legacy Nemotron branches (dispatch
   must be guarded); add the `build_primary_leaderboard.py` step or an
   explicit opt-out (F3, F4, F8, F10, F12, F13).

## Primary sources consulted

- HF model repo + API: huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
  (model card, commits/main, commit e7fa1b0, tree API with sizes); DFlash and
  DSpark draft repos.
- NVIDIA cookbook (raw notebook): raw.githubusercontent.com/NVIDIA-NeMo/Nemotron/main/usage-cookbook/Nemotron-3.5-Lightning/vllm_cookbook.ipynb
- vLLM docs: docs.vllm.ai/en/v0.27.1/features/reasoning_outputs/ and
  /en/v0.27.1/configuration/engine_args/; parser API pages.
- vLLM GitHub: issues #44676, #39573, #39103, #50189, #47365, #47749,
  #35065, #39581, #37362; PR #40082.
- Local: the pulled `vllm/vllm-openai:v0.27.1` container source (CPU-only
  inspection — protocol.py, input_processor.py, thinking_budget_state.py,
  config/vllm.py, config/kernel.py, oracle/nvfp4.py, parser/quant/model
  registries); the downloaded snapshot at revision e7fa1b0 (config.json,
  hf_quant_config.json, chat_template.jinja, shard census); repo harness
  (`mini-rl-env.py`, `llm_factory.py`, `evaluate_runs.py`, sweep scripts,
  leaderboards, prior project docs); live host state (nvidia-smi, tmux,
  docker, ports, disk).
