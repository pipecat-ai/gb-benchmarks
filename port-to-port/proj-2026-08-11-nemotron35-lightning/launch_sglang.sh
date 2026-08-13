#!/usr/bin/env bash

set -u -o pipefail

IMAGE="lmsysorg/sglang@sha256:a04d9a1a7ffe371b05230aecab001d4ba2bfa0e5c137bc56409ecc4cbc3ac864"
MODEL_CACHE="/home/khkramer/.cache/huggingface/hub/models--nvidia--NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4"
REVISION="e7fa1b0bdaf462c67c7f0bf638addacd89fd3054"
SNAPSHOT="${MODEL_CACHE}/snapshots/${REVISION}"
CONTAINER_SNAPSHOT="/models/nemotron35-cache/snapshots/${REVISION}"

echo "SERVER_IMAGE=${IMAGE}"
echo "SERVER_SNAPSHOT=${SNAPSHOT}"
echo "SERVER_SGLANG_COMMIT=d59c1ddf70ee17fcc41c053ed38bd60bc6cc28cc"
echo "SERVER_MEM_FRACTION_STATIC=0.85"
echo "SERVER_CUDA_GRAPH_MAX_BS_DECODE=16"
echo "SERVER_START=$(date -Is)"

exec docker run --rm \
  --name nemotron35-lightning-sglang \
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
  --volume "${MODEL_CACHE}:/models/nemotron35-cache:ro" \
  "${IMAGE}" \
  sglang serve \
  --model-path "${CONTAINER_SNAPSHOT}" \
  --served-model-name nemotron-3.5-lightning \
  --context-length 65536 \
  --max-running-requests 1 \
  --mamba-ssm-dtype float16 \
  --mem-fraction-static 0.85 \
  --cuda-graph-max-bs-decode 16 \
  --reasoning-parser nemotron_3 \
  --tool-call-parser qwen3_coder \
  --host 127.0.0.1 \
  --port 8000
