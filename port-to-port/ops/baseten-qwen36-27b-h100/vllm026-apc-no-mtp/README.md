# vLLM 0.26 prefix-cache validation

This variant isolates automatic prefix caching from MTP speculative decoding:

- vLLM 0.26.0, which includes the merged Model Runner V2 hybrid-cache work;
- explicit Mamba/Gated DeltaNet `align` cache mode;
- prefix caching enabled;
- MTP disabled so this remains a control for the separately validated
  `vllm026-apc-mtp` configuration.

The deployment is for protocol and latency validation, not production. Keep
one request in flight and return it to `min_replica: 0` after testing.
