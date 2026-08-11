# Qwen3.6-35B-A3B FP8 single-H100 deployment

This Truss recipe applies the validated Qwen3.6-27B serving contract to the
official Qwen3.6-35B-A3B FP8 checkpoint:

- immutable Hugging Face revision
  `95a723d08a9490559dae23d0cff1d9466213d989`;
- vLLM 0.26.0 on one H100, tensor parallelism 1 and one request at a time;
- official FP8 weights with BF16 activations;
- 65,536-token text-only context;
- automatic hybrid prefix caching in `align` mode;
- the checkpoint's one MTP layer with two speculative tokens;
- Qwen3 reasoning parsing and Qwen3-coder automatic tool parsing.

The pinned repository occupies 37,476,648,812 bytes. Its text configuration is
a 40-layer `qwen3_5_moe_text` hybrid with a four-layer full-attention interval,
linear-convolution state, 256 experts (8 active), and one MTP layer. Those
properties support the inherited `--mamba-cache-mode align` and MTP flags, but
server startup logs and repeated 29K-prefix protocol probes remain the
authoritative runtime gate.

Keep `min_replica=0`, `max_replica=1`, target concurrency 1, autoscaling window
60 seconds, and scale-down delay 120 seconds. Temporarily set the minimum to one
only during an intentional sequential campaign, then verify zero active
replicas.
