# Gemma 4 26B A4B single-H100 deployment

This Truss records the first deployment attempt with stable vLLM 0.26.0. Do
not use it for benchmark runs: startup exposed a Gemma 4 MTP embedding-sharing
bug fixed immediately after the stable release by upstream commit
`272abd5f4869`. The sibling `nightly-20260729-apc-mtp` recipe contains the
production candidate with that upstream fix.

The serving stack is pinned for reproducibility:

- vLLM 0.26.0 by immutable Docker image digest;
- target checkpoint revision
  `4d7ae4984b7db7de8f8457170b3f1a419ee76d52`;
- matching MTP assistant revision
  `6e5aaaf4c42b98394530b8fda2e95cadd65c151c`;
- one speculative token, automatic prefix caching, and one active sequence;
- vLLM's native Gemma 4 reasoning and streamed tool-call parsers;
- the checkpoint's canonical July 2026 chat template;
- text-only profiling and a 32,768-token context limit.

Gemma 4 supports a binary reasoning control. Benchmark clients must send
`chat_template_kwargs.enable_thinking=false|true`; enabled tool-call turns
also send `preserve_thinking=true` so the reasoning preceding the call is
available to the tool-result continuation. Recommended sampling is
temperature 1.0, top-p 0.95, and top-k 64.

MTP is not assumed to improve batch-one latency for this MoE model. It remains
enabled only after repeated streamed-text, single/multiple-tool, continuation,
reasoning-separation, usage-accounting, prefix-cache, and end-to-end benchmark
smokes pass.

No credentials or deployment identifiers belong in this directory.
