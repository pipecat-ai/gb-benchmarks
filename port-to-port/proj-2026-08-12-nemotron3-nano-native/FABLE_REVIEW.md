# Fable adversarial review — PLAN.md (Nemotron 3 Nano native-thinking rerun)

Reviewed: `port-to-port/proj-2026-08-12-nemotron3-nano-native/PLAN.md` as of
2026-08-12. Every load-bearing assumption was independently verified against
(a) the local checkpoint and its pinning artifacts, (b) the pinned SGLang
image contents (`sha256:a04d9a1a…`, inspected inside the container), (c) the
pinned NVIDIA model card and cookbook (fetched at the pinned revision/commit),
(d) the current port-to-port harness source and the Lightning project it
claims to reuse, and (e) the leaderboard/publication tooling. This review was
written independently of `CODEX_REVIEW.md` (which appeared mid-review); where
we disagree with it, that is called out explicitly.

## Verdict

The core design — binary native `enable_thinking` comparison, no synthetic
budget, pinned digest, matched N=25, publish alongside Lightning — is sound
and the hardware/stack premise holds: **the pinned image does run NVFP4
NemotronH on the RTX 5090**. But the plan is not executable as written. It has
one configuration choice that would corrupt the reasoning-off cell (B1), one
instruction the current harness cannot satisfy (B2), and two steps that name
tooling which does not exist (B3, B4). Fix those four before the first smoke.

---

## Independently verified (plan claims that hold)

- **Checkpoint pin.** Local dir declares `NemotronHForCausalLM` /
  `model_type: nemotron_h`, `max_position_embeddings: 262144`, NVFP4 weights
  (`hf_quant_config.json`: `quant_algo: "NVFP4"`, group_size 16, modelopt
  0.29.0), FP8 KV (`kv_cache_quant_algo: "FP8"`), `mamba_ssm_cache_dtype:
  "float32"`. All five shards SHA-256-match the pinned revision
  `ce1b118a…` per
  `~/src/nemotron-3-nano-5090/artifacts/measurements/nvfp4_checkpoint_completeness_2026-04-29.json`
  (local vs remote hashes identical, 0 missing files), and the two
  remote-code `.py` files are pinned in `docs/hf_remote_code_manifest.json`.
- **NVFP4 on RTX 5090 works in this image.** This was the single biggest
  risk and it checks out. `is_blackwell_supported` accepts compute major 12
  (`srt/utils/common.py:274-280`; host GPU confirmed: RTX 5090, 32,607 MiB,
  compute cap 12.0). The auto-resolved dense FP4 GEMM backend on sm120 is
  `flashinfer_cutlass` (`fp4_utils.py:148-155`), and the bundled FlashInfer
  0.6.15.post1 ships a dedicated sm120 kernel
  (`cutlass_fp4_gemm_sm120`, `gemm_base.py:1559-1563`; `mm_fp4` is decorated
  as supporting capability 120/121). The FP4 MoE path likewise resolves to
  `flashinfer_cutlass` with an sm120 module
  (`fused_moe/core.py:310-311, 845-846`). `NemotronHForCausalLM` is
  registered (`srt/models/nemotron_h.py:1257`) and the modelopt override
  maps `NVFP4 → modelopt_fp4` and asserts `mlp_hidden_act == "relu2"`
  (satisfied by config.json). NVIDIA's cookbook confirms NVFP4 "requires
  Blackwell architecture" with ≥20 GB VRAM — consistent, and 5090 qualifies.
- **`--attention-backend flashinfer` is correct.** It is also the image's
  own sm120 default for this model (trtllm_mha is explicitly unsupported on
  SM120 per the image's override comment; the generic default falls back to
  flashinfer, `server_args.py:5701-5757`). Hybrid Mamba wiring wraps it in
  `HybridLinearAttnBackend` + `Mamba2AttnBackend` automatically
  (`attention_registry.py:308-487`).
- **FP8 KV is auto-detected; no flag needed.** With `--kv-cache-dtype auto`
  (default), `kv_cache_quant_algo == "FP8"` from `hf_quant_config.json`
  resolves the pool to `torch.float8_e4m3fn`
  (`srt/mem_cache/kv_cache_dtype.py:32-40`, `modelopt_quant.py:778-793`).
  The plan's "checkpoint's FP8 KV format" is achievable with zero flags.
  Note: the checkpoint contains **no per-layer `k_scale`/`v_scale` tensors**
  (verified against the safetensors index) — the launch-log gate should
  confirm the server accepts this without scale warnings.
- **FP32 Mamba state is the effective default — but via a different
  mechanism than the plan implies.** SGLang reads `config.mamba_ssm_dtype`;
  the checkpoint spells the field `mamba_ssm_cache_dtype`, so the config
  value is silently ignored and SGLang's own default (`float32`) applies
  (`server_args.py:2496-2503`, `srt/configs/mamba_utils.py:48-105`). Net
  result matches the plan's intent. Caveats: the conv state defaults to
  bfloat16 (only the SSM temporal state is FP32), and Lightning deliberately
  ran `--mamba-ssm-dtype float16` — so "same stack as Lightning" does not
  extend to this knob. The smoke should assert the resolved dtype from the
  launch log rather than trusting the default chain.
- **Native thinking toggle is real and correctly plumbed.**
  `chat_template.jinja:12` defines `enable_thinking` (default **true**);
  thinking-on prefills `<|im_start|>assistant\n<think>\n`, thinking-off
  prefills `<think></think>` (template lines 198-204). The server accepts
  per-request `chat_template_kwargs` (`protocol.py:831`), and the harness
  transmits `enable_thinking` for Nemotron models via
  `--openai-no-budget-thinking-toggle` (`mini-rl-env.py:1551-1574`), which
  also **rejects any `--thinking-budget` and strips
  `vllm_xargs.thinking_budget`** (`mini-rl-env.py:1233-1237, 1564-1571`) —
  so plan step 2's "no thinking_budget transmitted" is enforceable and
  checkable in the logged `inference_inputs`. Nothing named
  `max_thinking_tokens` exists anywhere in harness or image.
- **Sampling and max_tokens claims are quote-accurate.** Model card:
  "`temperature=0.6` and `top_p=0.95` are recommended for tool calling"
  (the plan correctly labels this as the tool-calling recommendation);
  cookbook reasoning-off example uses `temperature=0`; card: "We recommend
  setting a high value (e.g., 10,000) for `max_tokens`". Per-cell sampling
  is deliverable via `--openai-params-json`, and `--max-tokens`
  (mini-rl-env.py:3686-3691 → llm_factory.py:350-353) is a plain
  per-completion output cap for `--provider openai` — it is not, and cannot
  become, a reasoning budget. The card's `reasoning_budget` mechanism is a
  client-side two-pass wrapper the harness does not implement; correctly out
  of scope.
- **`qwen3_coder` tool parser is correct.** Registered in the image
  (`function_call_parser.py:63-98`); `Qwen3CoderDetector` expects exactly
  the `<tool_call><function=NAME><parameter=KEY>…` XML that
  `chat_template.jinja` instructs the model to emit (template line 92).
  Both NVIDIA sources and the image's own Nemotron-3-Nano docs
  (`docs/cookbook/autoregressive/NVIDIA/Nemotron3-Nano.mdx:147`) prescribe it.
- **Harness flags exist with the stated semantics.** `--max-turns` (default
  50), `--function-call-timeout-secs` (default 20), `--log-json`
  (`mini_rl_run.v3`), `--round-id` free-form strings; N=25 with `r01`–`r25`
  matches Lightning and GPT-5.6 precedent. Failed-runs-stay-judged is
  codified repo policy (`AGENTS.md:10`) and Lightning's judged aggregates
  include `max_turns_exhausted` runs.
- **Judging and publication constants.** Judge "Claude Sonnet 4.6" =
  `claude-sonnet-4-6`, the default in `evaluate_runs.py` (~line 2186) and
  the only judge in all 142 existing `aggregate.json` files. Rubric
  `port_to_port_primary_v1` (`evaluate_runs.py:35`) and prompt hash
  `68d2c77b…` (SHA-256 of the natural v1 task prompt; stamped in
  `leaderboard-natural.md:4-5`) both verified. The "full natural
  leaderboard" is `leaderboards/leaderboard-natural.md` (canonical per
  `leaderboards/README.md:3-9`); the four historical budgeted Nano rows
  (tb=0/128/512/2048, Modal B200) are present at lines 79-94; the two
  Lightning cells are judged
  (`runs/eval-nemotron-3.5-lightning-natural-{none,high-unbounded}-sglang-20260811T223912Z/`)
  and confirmed **not** yet published — exactly as the plan states. The
  README admission rule is verified as prose in top-level `README.md:21`:
  "score at least 80 and have a per-turn P50 time of less than 4 seconds"
  (per-turn P50, matching the plan's reading). Publishing on/off as two rows
  has direct precedent (nemotron-3-ultra th=high and th=none rows).
- **Latency definitions match the tooling.** "Pooled turn P50/P90" =
  `decision_ms` per assistant turn (LLM response wall time, excluding
  tool/env time; mini-rl-env.py:2257), pooled across all turns of all runs;
  "total-time P50" is produced by the same aggregation. The plan's step-6
  names map onto real outputs — except the three metrics in B4 below.

---

## Blockers

### B1 — `--reasoning-parser deepseek-r1` corrupts the thinking-off cell; use `nemotron_3`

The plan follows the pinned cookbook (`deepseek-r1`), but in this exact
image `DeepSeekR1Detector` hardcodes `force_reasoning=True` — all output is
"assumed to be reasoning until `</think>`" (`srt/parser/reasoning_parser.py:296-306`).
With `enable_thinking=false`, the empty `<think></think>` pair lives in the
*prompt* and the generated stream contains **no** think tags, so the entire
answer — including tool-call XML — is routed into `reasoning_content` and
`content` comes back empty. The only reason this "works" at all is the
`force_nonempty_content` re-emission hack (see B2), which dumps the
misclassified text back into `content` at end-of-parse. That is a fragile
two-wrongs-make-a-right chain, and it is exactly the failure mode the
Lightning review warned "plausibly passes shallow probes while corrupting
every reasoning/tool measurement."

The correct parser ships in this image and is purpose-built for this model:
`Nemotron3Detector` (`reasoning_parser.py:753-778`) uses
`<think>`/`</think>`, `tool_start_token="<tool_call>"`, and
`reasoning_default="enable_thinking"` — `serving_chat.py:2311-2316` treats
generation as in-reasoning when `chat_template_kwargs.enable_thinking` is
true (matching the prefilled-open-`<think>` on-cell) and as normal content
when false (matching the tag-free off-cell). The image's **own** Nemotron 3
Nano docs prescribe it: `docs/cookbook/autoregressive/NVIDIA/Nemotron3-Nano.mdx:107`
"`--reasoning-parser nemotron_3` should be appended… toggled by setting
enable_thinking to False." The pinned model card's SGLang command says
`--reasoning-parser nano_v3` — that name **does not exist** in this image's
registry (`server_args.py:8387-8395`); `nemotron_3` is this build's
implementation of the same thing. So NVIDIA's two documents disagree with
each other, the cookbook's choice is wrong for the off cell, and the model
card's choice is a name this image doesn't have.

Required change: the plan's instruction "Do not copy Lightning's
`nemotron_3` parser" is backwards — that prohibition confuses "don't blindly
copy Lightning" with "avoid this parser." Nano's chat template emits exactly
the format `Nemotron3Detector` parses. Use `--reasoning-parser nemotron_3`,
and have the step-2 smoke assert, per cell: on → nonempty
`reasoning_content` + nonempty `content`/tool_calls; off → empty
`reasoning_content` + all text in `content`, with no `</think>` or
`<tool_call>` literals leaking into `content`.

(Disagreement with CODEX_REVIEW.md noted: it recommends keeping
`deepseek-r1` and qualifying `force_nonempty_content` as the off-cell
workaround. That is survivable but strictly worse — it makes every off-cell
`content` the product of a parser-failure fallback, and it also mislabels
the on-cell/off-cell `reasoning_content` semantics asymmetrically. The
native-format parser exists; use it.)

### B2 — The plan forbids `force_nonempty_content`, but the harness hardcodes it

`PLAN.md` line 45-46: "Do not copy Lightning's … `force_nonempty_content=true`
request option into Nano." There is no harness path that obeys this: the
**only** branch that transmits `enable_thinking` for Nemotron models
(`--openai-no-budget-thinking-toggle`, `mini-rl-env.py:1551-1574`)
unconditionally sets `chat_template_kwargs["force_nonempty_content"] = True`
(line 1561, with a comment saying to keep it on for both binary cells).
Verified directly in the current working tree. As written, the plan is
unimplementable without a harness edit it never schedules.

Resolve jointly with B1. Two coherent options:

1. **(Recommended)** Switch to `nemotron_3` (B1) and keep the harness as-is.
   With a correct parser, `_maybe_apply_force_nonempty_content` (engine-side,
   `reasoning_parser.py:~1700`) only fires when parsed content is genuinely
   empty (e.g., a turn that spent its whole completion inside reasoning), and
   the smoke/analysis should flag any turn where it promoted reasoning-shaped
   text into content. Amend PLAN.md to permit it, and state why.
2. Edit the harness to make `force_nonempty_content` opt-in per model, then
   keep the plan's prohibition. This adds a harness change + regression-test
   surface for no measurement benefit, and with `deepseek-r1` it would
   outright break the off cell (B1).

Either way the current PLAN text and the current harness cannot both be true;
pick one and write it down before the smoke.

### B3 — Cache-flush orchestration and verification do not exist

Plan step 4 makes flush verification an *inclusion criterion* ("Confirm the
flush succeeded before every included run"), but no flush tooling exists
anywhere in the tree — the only `/flush_cache` mention in the repo is in this
project's own review file. Lightning never flushed (its batch script gates on
`curl /health` only). The endpoint itself is fine — `GET|POST /flush_cache`
(`http_server.py:946-961`), returns 200 "Cache flushed." when idle and HTTP
400 when requests are running/waiting, so success is programmatically
checkable — but the collection script that calls it between conversations,
checks the 200, saves the response body, and refuses to start the run
otherwise has to be written. The plan should name that script as a
deliverable and define the failure behavior (retry-until-idle vs abort).

Also note the semantics: a 400 means the flush *did not happen* (it is
refused while busy, not queued) — "confirm the flush succeeded" must check
status code, not just call the endpoint.

### B4 — Step 6 promises metrics no tooling produces

`evaluate_runs.py`/`build_primary_leaderboard.py` produce score, completion
rate, terminal classes, pooled turn P50/P90, and total-time P50 — but **not**:
completion-token or reasoning-token *distributions* (raw per-turn usage
including `reasoning_tokens` is captured in run JSON at
mini-rl-env.py:859-874, but nothing consumes it), **truncation events** (no
`finish_reason == "length"` tracking exists anywhere — particularly important
here because `max_tokens=10000` caps think+answer jointly, so on-cell
truncations are a real risk), and **empty-content events**
(`empty_response_count` is written into run summaries at
mini-rl-env.py:3325-3328 but never read by any evaluator). These three need a
small new analysis script; the plan should schedule it explicitly or drop the
claims. The truncation counter is not optional: without it, an on-cell run
that silently hits the 10k ceiling mid-reasoning is indistinguishable from a
model failure, and `force_nonempty_content` (B2) can convert exactly such a
truncation into a plausible-looking answer.

---

## Required changes (non-blocking, fix in PLAN.md before execution)

1. **Image provenance is misstated.** The image's git HEAD is indeed
   `d59c1ddf7`, but the working tree inside the image is **dirty**: 14
   modified files + 4 untracked, ~652 inserted lines — and those patches are
   precisely what enable this benchmark (removal of the "NemotronH does not
   support triton" assert in `server_args.py:~5549`, SM120-aware
   `_nemotron_h_overrides` with the comment "TRT-LLM MHA prefill is not
   supported on SM120/121", the triton-backend mamba2 fix, `W4A16_NVFP4`
   support in `modelopt_quant.py`). The parenthetical
   "(`d59c1ddf70ee…`)" in PLAN.md reads as if the commit identifies the
   code; it does not. Keep the digest as the sole identity, note the dirty
   state, and capture `git -C /sgl-workspace/sglang diff` into the preflight
   evidence bundle. Corollary: the sm120+NVFP4+NemotronH path is freshly
   enabled dev code, which raises the value of the step-3 full-smoke gate.
2. **"Follow the Nano cookbook's model-specific controls" mislabels three
   flags.** `--max-running-requests 1`, `--context-length 65536`, and
   `--mem-fraction-static 0.85` appear in **neither** the pinned model card
   nor the pinned cookbook (neither NVIDIA SGLang command sets any context
   length at all; the model's native max is 262,144). They are this
   benchmark's own choices — legitimate ones (Lightning parity, single 32 GB
   GPU) — but the plan must attribute them to itself, or a reader will
   "verify against the cookbook" and find nothing.
3. **Pin `--pipeline-idle-timeout-secs 900`.** Lightning set it explicitly
   (`run_binary_batch_sglang.sh`); the plan omits it. An unbounded native
   reasoning turn on the on cell is exactly the case a short idle timeout
   would misclassify as a failure. List it with the other collection flags.
4. **Define the leaderboard row labels concretely.**
   `leaderboard-natural.md` has no hardware/stack/mode columns — everything
   is a parenthesized tag string on the model cell (`th=`, `tb=`, `mt=`,
   `base=`), and the old Nano rows are distinguishable only by
   `base=daily--nemotron-nano-b200-sglang-serve.modal.run`. "Label the new
   rows as local RTX 5090 NVFP4/native binary reasoning" has no mechanism in
   that file; the precedent (muse-glimmer) puts "Local RTX 5090" in the
   top-level README's curated table and prose. Specify the exact tag string
   now (e.g. `th=high|none, mt=10000, base=127.0.0.1:8000`) and put the
   RTX 5090/NVFP4/SGLang description in README prose. Also publish via
   `build_primary_leaderboard.py` rebuild (it enforces prompt-hash purity,
   lines 205-214), not hand-edited rows.
5. **Alternating cadence needs a new script — and say what "matched" means.**
   Lightning ran 25 `none` then 25 `high` sequentially; no alternating
   collection script exists. Writing one is fine (alternation is a good
   guard against thermal/clock drift on a local GPU), but it is new tooling.
   Separately, `r01`–`r25` are pairing labels only: `SyntheticWorld` is
   unseeded and the world is byte-identical every run (mini-rl-env.py:3458;
   no RNG in synthetic_world.py). "Matched round IDs" should be described as
   cohort bookkeeping, not scenario matching, or a reader will assume
   per-round seeded variation that does not exist.
6. **Document the two comparability deltas against the co-published
   Lightning rows.** (a) Lightning ran both cells at temperature 1.0/top_p
   0.95 with **no** `max_tokens` cap (`"max_tokens": null` in its run
   configs); Nano will run 0.6/0.95 + greedy with a 10k cap. (b) Lightning
   never flushed the radix cache; Nano flushes between conversations, which
   raises first-turn prefill latency relative to Lightning's regime. Both
   are defensible choices, but the leaderboard will show these four rows
   side-by-side; the deltas belong in the run notes. While documenting (a),
   also note the card's sampling tension: 0.6/0.95 is NVIDIA's
   *tool-calling* recommendation (correctly cited by the plan), but the same
   card recommends 1.0/1.0 for *reasoning tasks* — for a tool-heavy
   benchmark the plan's choice is right, but it is a choice, not the only
   NVIDIA-sanctioned one.

## Non-blocking improvements

- **Launch-log acceptance gate (extend step 1).** Beyond what the plan
  lists, assert from the server log: resolved quantization `modelopt_fp4`,
  FP4 GEMM/MoE backends = `flashinfer_cutlass` (not marlin), KV pool dtype
  `float8_e4m3fn` with no missing-scale warnings (checkpoint has no
  k_scale/v_scale tensors), Mamba SSM state dtype float32 / conv state
  bfloat16, resolved `--mamba-radix-cache-strategy` (auto-resolved for mamba
  models, `overrides.py:1609-1617`), and speculative algorithm None
  (default; verified `server_args.py:2047-2051`).
- **EOS sanity.** config.json says `eos_token_id: 2` (`</s>`) while
  tokenizer/generation_config use `<|im_end|>` (id 11; generation_config
  lists `[2, 11]`). SGLang reads the tokenizer/generation configs so this
  should be benign, but one smoke assertion that off-cell greedy generation
  actually stops (rather than running to the 10k cap) is cheap insurance.
- **`--trust-remote-code` is harmless but not load-bearing.** SGLang serves
  this model through its native `nemotron_h` implementation keyed off
  `model_type`; Lightning omitted the flag. Keeping it matches NVIDIA's
  command; just don't describe it as required-by-SGLang.
- **served-model-name must match the harness gate.** The
  `--openai-no-budget-thinking-toggle` branch requires the model name to
  start with `nemotron`/`nvidia/nemotron` and `--thinking` ∈ {none, high}
  (mini-rl-env.py:256-258, 1212-1238). Name the served model (e.g.
  `nemotron-3-nano-30b-nvfp4`) and the cell→flag mapping (on = `--thinking
  high`, off = `--thinking none`) in the plan so the collection script can't
  drift.
- **Memory headroom is plausible but unproven.** 19.3 GB weights + 0.85 of
  32.6 GB static fraction + tiny FP8 KV (6 attention layers, 2 KV heads) +
  FP32 mamba pools should fit 65,536 context at batch 1, but this exact
  combination has never been launched; the plan's fallback language
  ("any fallback is a new serving configuration") is the right posture —
  keep it.
- **Git housekeeping at publication time.** `leaderboards/README.md` and
  `leaderboard-literal.md` are currently untracked; the publication step
  should commit the canonical leaderboard files together with the new run
  artifacts so the published state is reproducible.
- **Score-≥80 gate reality check.** The historical budgeted Nano rows top
  out at 45/100 and Lightning's best local cell scored 31. The README
  admission clause will almost certainly not trigger; the plan handles this
  correctly with "only if", so no change needed — just don't pre-draft
  README copy that assumes admission.

## Bottom line

Proceed after amending the plan: swap `deepseek-r1` → `nemotron_3` (B1),
reconcile the `force_nonempty_content` prohibition with the harness reality
(B2), add the flush-orchestration script and its success-check semantics as a
deliverable (B3), and either build or drop the three unproduced report
metrics — building at least the truncation counter (B4). The remaining items
are wording, provenance, and labeling fixes that cost minutes now and save an
argument at publication time.
