# Gemma 4 26B A4B single-H100 deployment

This is the production-candidate Truss for the official BF16 instruction
checkpoint. It is isolated from the older Gemma 4 31B Modal service and from
the Qwen Baseten deployments.

The serving stack is pinned for reproducibility:

- official vLLM nightly built 2026-07-29, by immutable Docker image digest;
- upstream vLLM commit `272abd5f4869`, which fixes Gemma 4 MTP embedding
  sharing for target and assistant checkpoints with different hidden sizes;
- target checkpoint revision
  `4d7ae4984b7db7de8f8457170b3f1a419ee76d52`;
- matching MTP assistant revision
  `6e5aaaf4c42b98394530b8fda2e95cadd65c151c`;
- one speculative token, automatic prefix caching, and one active sequence;
- vLLM's native Gemma 4 reasoning and streamed tool-call parsers;
- the checkpoint's canonical July 2026 chat template;
- text-only profiling and a 32,768-token context limit.

The first attempt used stable vLLM 0.26.0. Its Gemma 4 MTP path retained the
assistant's 1,024-wide placeholder embeddings instead of replacing them with
the target's 2,816-wide embeddings, so the official 5,632-input projection
failed during graph compilation. Upstream commit `272abd5f4869` supplies the
missing Gemma-specific sharing override; using the later pinned official image
avoids carrying a local source patch.

Gemma 4 supports a binary reasoning control. Benchmark clients send
`chat_template_kwargs.enable_thinking=false|true`; enabled tool-call turns
also send `preserve_thinking=true` so reasoning preceding the call remains
available to the tool-result continuation. Recommended sampling is
temperature 1.0, top-p 0.95, and top-k 64.

MTP is not assumed to improve batch-one latency for this MoE model. It remains
enabled only after repeated streamed-text, single/multiple-tool, continuation,
reasoning-separation, usage-accounting, prefix-cache, and end-to-end benchmark
smokes pass.

No credentials or deployment identifiers belong in this directory.
