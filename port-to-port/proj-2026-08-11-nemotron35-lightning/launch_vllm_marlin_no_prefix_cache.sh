#!/usr/bin/env bash

set -u -o pipefail

IMAGE="vllm/vllm-openai@sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967"
MODEL_CACHE="/home/khkramer/.cache/huggingface/hub/models--nvidia--NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4"
REVISION="e7fa1b0bdaf462c67c7f0bf638addacd89fd3054"
SNAPSHOT="${MODEL_CACHE}/snapshots/${REVISION}"
CONTAINER_SNAPSHOT="/models/nemotron35-cache/snapshots/${REVISION}"

echo "SERVER_IMAGE=${IMAGE}"
echo "SERVER_SNAPSHOT=${SNAPSHOT}"
echo "SERVER_PREFIX_CACHING=disabled"
echo "SERVER_START=$(date -Is)"

exec docker run --rm \
  --name nemotron35-lightning-vllm-noapc \
  --gpus all \
  --ipc=host \
  --network=host \
  --env HF_HUB_OFFLINE=1 \
  --env TRANSFORMERS_OFFLINE=1 \
  --volume "${MODEL_CACHE}:/models/nemotron35-cache:ro" \
  "${IMAGE}" \
  "${CONTAINER_SNAPSHOT}" \
  --served-model-name nemotron-3.5-lightning \
  --moe-backend marlin \
  --kv-cache-dtype fp8 \
  --max-num-seqs 1 \
  --max-model-len 65536 \
  --max-num-batched-tokens 32768 \
  --async-scheduling \
  --mamba-backend flashinfer \
  --mamba-ssm-cache-dtype float16 \
  --enable-mamba-cache-stochastic-rounding \
  --mamba-cache-philox-rounds 5 \
  --reasoning-parser nemotron_v3 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --host 127.0.0.1 \
  --port 8000
