#!/usr/bin/env bash

set -u -o pipefail

IMAGE="lmsysorg/sglang@sha256:a04d9a1a7ffe371b05230aecab001d4ba2bfa0e5c137bc56409ecc4cbc3ac864"
MODEL_DIR="/home/khkramer/src/nemotron-3-nano-5090/artifacts/checkpoints/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4"
CONTAINER_MODEL_DIR="/models/nemotron-3-nano-nvfp4"

echo "SERVER_IMAGE=${IMAGE}"
echo "SERVER_MODEL_DIR=${MODEL_DIR}"
echo "SERVER_SERVED_MODEL=nemotron-3-nano-30b-nvfp4"
echo "SERVER_CONTEXT_LENGTH=262144"
echo "SERVER_MEM_FRACTION_STATIC=0.85"
echo "SERVER_KV_CACHE_DTYPE=auto_expected_fp8_e4m3"
echo "SERVER_MAMBA_SSM_DTYPE=float32"
echo "SERVER_START=$(date -Is)"

exec docker run --rm \
  --name nemotron3-nano-sglang \
  --gpus all \
  --cap-add SYS_NICE \
  --ipc=host \
  --network=host \
  --shm-size=16g \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  --env HF_HUB_OFFLINE=1 \
  --env TRANSFORMERS_OFFLINE=1 \
  --env SAFETENSORS_FAST_GPU=1 \
  --volume "${MODEL_DIR}:${CONTAINER_MODEL_DIR}:ro" \
  "${IMAGE}" \
  sglang serve \
  --model-path "${CONTAINER_MODEL_DIR}" \
  --served-model-name nemotron-3-nano-30b-nvfp4 \
  --trust-remote-code \
  --tp 1 \
  --context-length 262144 \
  --max-running-requests 1 \
  --mamba-ssm-dtype float32 \
  --mem-fraction-static 0.85 \
  --kv-cache-dtype auto \
  --attention-backend flashinfer \
  --reasoning-parser nemotron_3 \
  --tool-call-parser qwen3_coder \
  --host 127.0.0.1 \
  --port 8000
