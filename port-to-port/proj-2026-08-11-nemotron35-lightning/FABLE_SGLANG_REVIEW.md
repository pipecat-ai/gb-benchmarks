# Fable review of SGLANG_PLAN.md

Reviewed: 2026-08-11. Reviewer: Claude (Fable 5).
Method: downloaded the SGLang cookbook notebook verbatim at the pinned commit
(`bf199a92e07b66e1215f48deb630bbe9a6758bd3`) and quoted from its raw cells;
queried Docker Hub's API for both image-tag spellings; inspected the
already-pulled dev image's SGLang source CPU-only (`docker run --rm
--entrypoint bash`, no GPU); grepped the pinned checkpoint snapshot's chat
template; compared against upstream `sgl-project/sglang` main; and verified
harness controls against current `mini-rl-env.py`. Prior reviews' evidence
(FABLE_REVIEW.md, FABLE_REVIEW_R2.md) reused where still valid.

## Verdict

The plan is cookbook-faithful in every serve flag, runtime flag, parser name,
request shape, and speculative-decoding fact I checked — with **one blocking
finding: the plan pins the wrong Docker tag.** The cookbook's tag is
`dev-nemotron3-5-lightning`; the plan (and the image already pulled locally)
uses the misspelled `dev-nemotron3-5-lighting`, which is a *different, older
build* whose `nemotron_3` reasoning parser expects thinking tokens this
checkpoint never emits. Served as planned, reasoning parsing would fail
systematically and `force_nonempty_content` would then paper over it by
dumping raw text as content. Fix the tag before first launch (S1). Everything
else is confirmed or advisory.

A second, happy correction: the first review's vLLM-context finding that
`force_nonempty_content` is a template no-op does **not** carry over to
SGLang — here it is a real, engine-implemented control (S4). The plan is
right to send it.

## S1 (blocking): wrong image tag — misspelled, older build with an incompatible reasoning parser

Three independent facts, all verified today:

1. **The cookbook's tag is `lmsysorg/sglang:dev-nemotron3-5-lightning`.**
   The raw notebook at the pinned commit contains that exact string 3 times
   (docker pull cell, docker run cell, configuration table) and the
   misspelled variant zero times. The plan's line "Pull NVIDIA's cookbook
   image tag `dev-nemotron3-5-lighting`" is factually wrong — that is not
   the cookbook's tag.
2. **Both tags exist on Docker Hub and are different builds.** Misspelled
   `dev-nemotron3-5-lighting`: last updated 2026-08-11T03:16Z, amd64 digest
   `sha256:9538f2cd…`. Correct `dev-nemotron3-5-lightning`: last updated
   2026-08-11T11:48Z (~8.5 h newer), amd64 digest `sha256:cfced3bc…`. The
   image pulled locally 19 h ago is the misspelled one (manifest
   `sha256:33a20324…`, sglang version `0.0.0.dev1+gd59c1ddf7`).
3. **The misspelled image's parser cannot parse this checkpoint's output.**
   Its `Nemotron3Detector`
   (`/sgl-workspace/sglang/python/sglang/srt/parser/reasoning_parser.py`)
   hardcodes `<|START_THINKING|>` / `<|END_THINKING|>` /
   `<|START_TEXT|>` / `<|START_ACTION|>`. The pinned checkpoint's
   `chat_template.jinja` contains **none** of those markers — it uses
   `<think>`/`</think>` (11 occurrences), `<|im_start|>` turns, and
   `<tool_call>` blocks (17 occurrences, matching `qwen3_coder`). Upstream
   `sgl-project/sglang` main's `Nemotron3Detector` is `<think>`-based
   ("Uses the same reasoning format as DeepSeek-R1") — i.e., the current
   parser matches the checkpoint; the pulled image predates it.

Consequence if launched as planned: the detector never finds its end token,
classifies the entire generation (including the literal `</think>` and the
tool-call XML) as reasoning, and `force_nonempty_content` then re-emits that
raw text as content — plausibly passing shallow probes while corrupting
every reasoning/tool measurement. Admission gate 3 should catch it, but only
after a full model load.

Required change: pull `lmsysorg/sglang:dev-nemotron3-5-lightning`, pin *its*
resolved digest in the launch script and logs, and before first launch repeat
the ten-second source check inside the container:
`grep -n "think_start_token" …/srt/parser/reasoning_parser.py` in the
`Nemotron3Detector` region must show `<think>`, not `<|START_THINKING|>`.
Record the image's sglang dev version string alongside the digest.

## S2 (confirmed): cookbook fidelity of the base launch

Verified verbatim against the pinned notebook:
- Serve command: `sglang serve --model-path nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4
  --host 127.0.0.1 --port 8000 --served-model-name nemotron-3.5-lightning
  --mamba-ssm-dtype float16 --mem-fraction-static 0.85
  --cuda-graph-max-bs-decode 16 --reasoning-parser nemotron_3
  --tool-call-parser qwen3_coder` — the plan's six bullets match exactly,
  nothing invented, nothing omitted except `--model-path` (see S10).
- Docker runtime: `--cap-add SYS_NICE --ipc=host --network=host
  --shm-size=16g --ulimit memlock=-1 --ulimit stack=67108864
  -e SAFETENSORS_FAST_GPU=1` + HF-cache mount — the plan's "SYS_NICE, host
  IPC/network, 16 GiB shm, unlimited memlock, 64 MiB stack,
  SAFETENSORS_FAST_GPU=1" is exact (67108864 B = 64 MiB).
- Parser naming: the notebook itself warns the names are backend-specific
  (SGLang `nemotron_3`, vLLM `nemotron_v3`, TRT-LLM `nemotron-v3`) — the
  plan's `nemotron_3` is correct for SGLang, and both `nemotron_3` and
  `qwen3_coder` are registered in the image
  (`reasoning_parser.py:1649`, `function_call_parser.py:85`). The `sglang
  serve` CLI subcommand exists (`cli/main.py`).
- Validation hardware: one H100 80 GB — the plan's framing (no published
  5090 command; adaptations must be explicit) is accurate. The notebook's
  config table notes the MoE runner is "marlin (auto-selected on H100)"; on
  SM120 auto-selection may resolve differently, so the plan's
  don't-force-and-verify-the-log stance is the right call.

## S3 (confirmed): the two added flags are valid — and `--context-length` is mandatory, not just comparability

Both exist in the image's `server_args.py`: `context_length` (line ~576) and
`max_running_requests` (line ~774). Critically, `--context-length` defaults
to **None → the model's config.json value, which is 1,048,576** for this
checkpoint. Without the flag, SGLang would size KV/mamba pools for 1M
context on a 32 GB card. So `--context-length 65536` is not merely "matching
the vLLM comparison" — it is required for the machine to work at all. The
plan could state this stronger. `--max-running-requests 1` is valid and
consistent with the sequential-benchmark convention.

## S4 (confirmed, with a caveat): `force_nonempty_content` is real on SGLang — engine-side, not template-side

- The plan's cookbook citation is verbatim-accurate: "When using tool
  calling with reasoning enabled, you must pass `"force_nonempty_content":
  true` inside `chat_template_kwargs`. Without it, the server may not
  correctly parse both the reasoning trace and the tool call output
  together" (tool-calling cell). The notebook also sends it in its
  reasoning-**off** example (`{"enable_thinking": False,
  "force_nonempty_content": True}`), so the plan's both-modes policy matches
  NVIDIA's own usage, not just its stated requirement.
- Mechanism: unlike vLLM (where the first review found it inert because the
  chat template doesn't implement it), SGLang implements it **in the
  reasoning parser**: `serving_chat` reads
  `chat_template_kwargs.get("force_nonempty_content") is True` and passes it
  into every detector (`reasoning_parser.py:1700-1701`); the base detector's
  `_maybe_apply_force_nonempty_content` re-emits reasoning text as
  `normal_text` when parsed content would be empty. It works regardless of
  the checkpoint's Jinja. The apparent conflict with FABLE_REVIEW.md F3 is
  resolved: F3 was about vLLM/template rendering; this is SGLang engine
  behavior.
- Caveat for judging: by design this converts "model produced no answer"
  into "reasoning presented as the answer." Applied identically in both
  cells it is fair, but the analysis should watch for content that is
  obviously raw reasoning (rambly, self-referential) and count it as a
  quality failure, not silently accept it. Admission gate 3 (parsed
  reasoning AND final content) is also the gate that catches S1's
  wrong-parser build — keep it strict, including asserting no literal
  `</think>` or `<tool_call>` text appears inside `content`.
- Harness implementation detail: `force_nonempty_content` exists nowhere in
  the harness today. No new mode is needed: inject it via
  `--openai-params-json '{"temperature":1.0,"top_p":0.95,"extra":{"extra_body":{"chat_template_kwargs":{"force_nonempty_content":true}}}}'` —
  the Nemotron toggle branch dict-copies any existing
  `chat_template_kwargs` and only adds `enable_thinking`
  (`mini-rl-env.py:1551-1556`), so the injected key survives in both cells.
  Add one regression asserting the merged wire payload contains both keys
  and no budget/max-token field.

## S5 (confirmed): no max_tokens, no budget field

- SGLang's ChatCompletionRequest has `max_tokens` as Optional/deprecated
  (protocol.py:758) and falls back to a context-derived `default_max_tokens`
  when neither it nor `max_completion_tokens` is sent — omitting the cap
  yields generation bounded only by the 65,536-token context, which is the
  plan's intent. The cookbook's own note ("Reasoning tokens count toward
  `max_tokens`. If `content` comes back empty … raise `max_tokens`")
  supports the no-cap decision.
- The two-pass `ThinkingBudgetClient` is exactly as the plan describes:
  first chat call capped at `max_tokens=reasoning_budget`, re-render via
  tokenizer `apply_chat_template(..., continue_final_message=True)`, resume
  through `/v1/completions`. Not using it is correct for a binary native
  comparison. (Minor cookbook inconsistency, irrelevant here: the budget
  section's prose describes a newline-seeking `reasoning_budget + 500`
  termination that the client code doesn't implement.)
- Do not send `reasoning_effort` either — SGLang actively pops it from
  `chat_template_kwargs` (`serving_chat.py:909`); the plan already omits it.

## S6 (realistic but tight): memory on 32 GB

SGLang defines `mem_fraction_static` as (weights + KV pool) / GPU capacity
(`server_args.py:4653`). At 0.85 × 31.84 GiB = 27.06 GiB static, minus
20.08 GiB weights → ~7.0 GiB for KV + mamba pools at 65,536 context — ample,
since only 6/52 layers are attention. The squeeze is the dynamic side:
15% ≈ 4.78 GiB for activations and decode CUDA graphs, minus ~1 GiB already
held by desktop processes → ~3.8 GiB, versus ~12 GiB free on the cookbook's
H100. A first-launch OOM is plausible; the plan's one-lever-at-a-time
response is right. Two sharpenings: (a) `--cuda-graph-max-bs-decode 16`
captures decode graphs for batch sizes that can never occur at
`--max-running-requests 1` — dropping it to 1 is the cheapest legitimate
5090 adaptation and NVIDIA's own MTP note frames 16 as a memory cap, not a
floor; (b) I confirmed the auto-discount `mem_fraction_static *= 0.85` in
`server_args.py` applies only to the AMD `aiter` backend, so there is no
hidden double-discount on this host.

## S7 (confirmed): admission gates and harness controls

Gates 1–7 map onto the observed failure modes, including the soak
requirement motivated by the three vLLM engine deaths appearing only after
accumulated context. Harness controls all exist as named: `--max-turns 50`
and `--function-call-timeout-secs 20` are the defaults, `--log-json` is the
standard artifact path, and the "explicit 900-second pipeline idle timeout"
corresponds to real machinery (`--pipeline-idle-timeout-secs`, and a 900 s
default request timeout with idle-timeout resolution at
`mini-rl-env.py:1060-1092`; `run_repeat_clean_config.sh` already
pattern-matches "Idle timeout detected"). Health-gating between runs matches
the existing worker scripts in this project directory.

## S8 (confirmed): judging pipeline

`evaluate_runs.py` with `--report-accuracy-judge llm` and default judge
model `claude-sonnet-4-6` remains the repo convention (verified in the first
review; unchanged). Reporting completion-token distributions and
`finish_reason=length` separately per mode implements FABLE_REVIEW_R2's R3
recommendation — good.

## S9 (confirmed): speculative-decoding facts

Verbatim from the notebook: MTP rides SGLang's EAGLE path with
`--speculative-num-steps 5 --speculative-eagle-topk 1
--speculative-num-draft-tokens 6`, draft path = the target checkpoint
itself, and the note that `--cuda-graph-max-bs-decode 16` must be kept to
avoid OOM on long requests; DFlash uses `--speculative-algorithm DFLASH
--speculative-dflash-block-size 4`; DSpark uses block size 3. The plan's
one-line summary ("MTP (5 steps, 6 draft tokens), DFlash block size 4,
DSpark block size 3") is accurate, and deferring all of it out of the
canonical comparison is right.

## S10 (minor): pass the snapshot path explicitly, not the model ID

The plan pins revision `e7fa1b0…` but the base-launch section names no
`--model-path`. The cookbook's command uses the bare model ID; inside the
container (host network, HF cache mounted) that resolves against the Hub,
and this cache's `refs/` is empty because the download used `--revision` —
so SGLang/huggingface_hub would materialize **HEAD**, which has moved again
(currently `f9b0c83`, README/plot churn only). Weights would be identical
via blob dedup, but the run would technically violate the plan's own
revision pin. Launch with
`--model-path /root/.cache/huggingface/hub/models--nvidia--NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4/snapshots/e7fa1b0bdaf462c67c7f0bf638addacd89fd3054`
(container-side path of the mounted cache) to make the pin binding.

## Summary of required changes

1. **S1: replace the image pin** with the cookbook's
   `lmsysorg/sglang:dev-nemotron3-5-lightning`, pin its digest, and verify
   the image's `Nemotron3Detector` is `<think>`-based before first launch.
2. **S10: pass `--model-path` as the explicit pinned snapshot path.**
3. Advisory: state that `--context-length 65536` is load-bearing (default is
   the model's 1M config value); treat `--cuda-graph-max-bs-decode 1` as the
   first memory lever; assert in gate 3/4 that `content` contains no literal
   `</think>`/`<tool_call>` text; have the analysis flag reasoning-shaped
   content that `force_nonempty_content` may have promoted.

Everything else in SGLANG_PLAN.md is verified correct against the pinned
cookbook, the image source, the checkpoint snapshot, and the harness.

## Sources

- Cookbook (verbatim, downloaded): raw.githubusercontent.com/NVIDIA-NeMo/Nemotron/bf199a92e07b66e1215f48deb630bbe9a6758bd3/usage-cookbook/Nemotron-3.5-Lightning/sglang_cookbook.ipynb
- Docker Hub API: hub.docker.com/v2/repositories/lmsysorg/sglang/tags/dev-nemotron3-5-lighting and …/dev-nemotron3-5-lightning
- Local image source (CPU-only inspection of `lmsysorg/sglang:dev-nemotron3-5-lighting`):
  `srt/parser/reasoning_parser.py`, `srt/function_call/function_call_parser.py`,
  `srt/entrypoints/openai/{serving_chat,protocol}.py`, `srt/server_args.py`,
  `cli/{main,serve}.py`
- Upstream parser: raw.githubusercontent.com/sgl-project/sglang/main/python/sglang/srt/parser/reasoning_parser.py
- Local: pinned snapshot `chat_template.jinja` (marker census); pull log
  `runs/sglang-dev-nemotron3-5-lighting-pull.log`; `mini-rl-env.py` /
  `run_repeat_clean_config.sh` (harness controls); prior evidence in
  FABLE_REVIEW.md and FABLE_REVIEW_R2.md.
