# Baseten Qwen3.6 27B single-H100 benchmark deployment

This directory contains sequential benchmark configurations for the official
`Qwen/Qwen3.6-27B` BF16 checkpoint. They adapt Baseten's four-H100 latency
preset to the benchmark's actual workload:

- one H100 with tensor parallelism disabled;
- 65,536-token maximum context;
- one concurrent sequence and one concurrent request;
- text-only serving;
- streamed OpenAI-compatible chat completions;
- Qwen reasoning and automatic tool-call parsers;
- MTP speculative decoding.

The root `config.yaml` preserves the original vLLM 0.20 no-cache control.
For further runs, use `vllm026-apc-mtp/config.yaml`: repeated long-prefix
protocol probes and a complete benchmark episode verified that vLLM 0.26's
`align`-mode hybrid prefix cache is correct with MTP for this workload. See
`prefix-cache-investigation-20260727.md` for the evidence and upstream fix
review. `vllm026-apc-no-mtp/config.yaml` remains the non-speculative control.

No credential or deployment identifier belongs in this directory. The model
repository is public, so its pinned weights do not require a Hugging Face
secret.
