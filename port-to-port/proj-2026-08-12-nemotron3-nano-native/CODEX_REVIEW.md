# Codex adversarial review

## Verdict

The experiment is technically sound and should proceed after four plan-level
gates are made explicit. No evidence supports reusing the historical synthetic
`thinking_budget` sweep: the clean comparison is the checkpoint's native
`enable_thinking=true|false` control.

## Independently verified

- The local five-shard checkpoint is NVIDIA's official text-only NVFP4 release
  pinned at `ce1b118ae66ec705d02c241525192832eb045fd3`; shard and configuration
  hashes match the pinned upstream artifacts. It declares
  `NemotronHForCausalLM`, a 262,144-token maximum position length, FP8 KV cache,
  and FP32 Mamba state.
- NVIDIA's pinned SGLang cookbook uses the same Nano model with
  `--trust-remote-code --tool-call-parser qwen3_coder --reasoning-parser
  deepseek-r1 --tp 1 --attention-backend flashinfer`, and states that the
  NVFP4 checkpoint needs Blackwell and at least 20 GB of VRAM. The RTX 5090 is
  Blackwell with 32 GB.
- The pinned local SGLang image is content-addressed at
  `sha256:a04d9a1a7ffe371b05230aecab001d4ba2bfa0e5c137bc56409ecc4cbc3ac864`
  and labels itself commit `d59c1ddf70ee17fcc41c053ed38bd60bc6cc28cc`,
  but contains a dirty patched worktree. The image digest, plus a saved status
  and binary diff, is the serving-code identity; HEAD alone is not.
  Its code contains `NemotronHForCausalLM`, ModelOpt NVFP4, the `qwen3_coder`
  tool parser, the purpose-built `nemotron_3` reasoning parser, hybrid Mamba
  Radix-cache handling, and automatic conversion of the checkpoint's
  `kv_cache_quant_algo = FP8` to `fp8_e4m3`.
- SGLang defaults the temporal Mamba state to FP32 even though its helper reads
  `mamba_ssm_dtype` while the checkpoint spells the field
  `mamba_ssm_cache_dtype`. The intended FP32 state is therefore retained.
- NVIDIA recommends temperature 0.6/top-p 0.95 for tool calling, and greedy
  generation when reasoning is off. It recommends a high `max_tokens` ceiling
  (10,000 is the example) and exposes native reasoning-off through
  `enable_thinking=false`. A 10,000-token output ceiling is not a reasoning
  budget.
- The old Nano results came from the Modal B200 SGLang endpoint, not DGX Spark.
  Their latency growth tracks the imposed 128/512/2048-token reasoning budgets,
  so the rows are historically valid but answer a different question.

## Required before collection

1. **Resolve the Nano reasoning parser path.** The pinned NVIDIA notebook's
   older `deepseek-r1` choice breaks reasoning-off in this exact image: its
   detector unconditionally treats no-tag output as reasoning. The image's
   current Nano documentation and tests instead specify `nemotron_3`, whose
   `enable_thinking`-aware detector handles both modes and splits tool calls.
   Use `nemotron_3`; the model card's vLLM-only `nano_v3` name is not registered
   here. Permit the harness's existing `force_nonempty_content=true`, normally
   a no-op with this parser, but flag any case where it promotes a completion
   truncated inside reasoning into answer/tool content. Assert that neither
   cell sends `thinking_budget`.
2. **Make runtime resolution an acceptance gate.** A successful process launch
   alone is insufficient. Save the complete launch log and require evidence of
   the exact checkpoint path/revision, `NemotronHForCausalLM`, ModelOpt NVFP4,
   FP8/`fp8_e4m3` KV, FP32 Mamba state, FlashInfer attention, RadixAttention
   enabled, 65,536 context, and one running request. If 65,536 at memory fraction
   0.85 does not fit, record the failure and treat any reduced context or state
   dtype as a new configuration requiring both smoke cells again.
3. **Strengthen protocol/cache qualification.** For each mode, save direct
   streaming response JSON proving parsed `reasoning_content`, valid tool calls,
   nonempty final content, and correct reconstruction of assistant/tool history
   over more than one tool cycle. Save each `/flush_cache` response and exclude
   an attempt unless the flush completed while idle. Cache stays enabled within
   a conversation. This prevents cross-run prefix reuse without disabling the
   production caching path.
4. **Publish through the canonical data path.** Add the immutable judged
   batches to a prompt-pure leaderboard input/manifest and rebuild both natural
   leaderboard variants to scratch. Diff before copying; do not hand-edit rows
   or replace historical budgeted Nano results. Add the best native cell to the
   README chart/table only if its unrounded score and turn P50 satisfy the
   existing inclusion rule. Include the already judged Lightning rows through
   the same rebuild.

## Design clarifications and reporting

- Alternating one request at a time is correct. `r01`-`r25` are matched cohort
  identifiers and ordering, not randomized or independently seeded task worlds;
  describe them that way.
- Log `RUN_START` and `RUN_EXIT`; give every attempt its own JSON and console
  log. Judge every failed attempt that produced raw JSON and preserve exactly 25
  predeclared attempts per cell rather than replacing failures.
- Report turn P50/P90 as end-to-end model decision latency, which includes the
  generated reasoning and answer/tool-call completion. Also report reasoning
  and completion token distributions, output-limit stops, empty/malformed
  responses, and terminal classes so latency differences remain interpretable.
- Pin `--pipeline-idle-timeout-secs 900`, matching the local Lightning run, so
  an unusually long native reasoning turn is not confused with a model failure.
- Record the exact benchmark commit plus task prompt, system instruction, and
  rubric hashes before the first smoke. The pinned task prompt hash alone does
  not guard against a system-instruction change.

With those changes, no unresolved blocker remains before the GPU launch smoke.
