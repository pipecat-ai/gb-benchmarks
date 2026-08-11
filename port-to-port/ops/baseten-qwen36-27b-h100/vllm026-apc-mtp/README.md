# vLLM 0.26 prefix-cache plus MTP validation

This variant tests whether the vLLM 0.26 hybrid-cache correctness fixes make
the original benchmark configuration safe:

- explicit Mamba/Gated DeltaNet `align` prefix-cache mode;
- MTP speculative decoding with two speculative tokens;
- streamed Qwen reasoning and tool parsing.

The protocol probe must pass repeatedly before any benchmark episode is run.
If it reproduces duplicate, malformed, or leaked tool calls, do not use this
configuration and do not apply the remaining draft upstream patches without a
separate correctness review.

On 2026-07-27, five 29K-token shared-prefix suites passed all 20 streaming and
tool-call checks with an 86.4% measured cache-hit rate. The subsequent
end-to-end `thinking=high` episode completed in 32 turns and received an
official score of 92/100. See the parent investigation note for details.

A later three-episode-per-mode comparison confirmed the result. `thinking=high`
scored 92 with 100% completion, 1.43-second turn P50, and no narration-only
turns. `thinking=none` scored 72 with 66.7% completion and a 0.99-second turn
P50, but spent 56 of 148 turns narrating without a tool call. Use
`thinking=high` for benchmark work; see the parent investigation note for the
full table and excluded infrastructure-stall details.
