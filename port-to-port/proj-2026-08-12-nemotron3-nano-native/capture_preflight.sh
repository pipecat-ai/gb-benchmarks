#!/usr/bin/env bash

set -u -o pipefail

PROJECT_DIR="/home/khkramer/src/gb-benchmarks/port-to-port/proj-2026-08-12-nemotron3-nano-native"
REPO_DIR="/home/khkramer/src/gb-benchmarks"
MODEL_DIR="/home/khkramer/src/nemotron-3-nano-5090/artifacts/checkpoints/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4"
IMAGE="lmsysorg/sglang@sha256:a04d9a1a7ffe371b05230aecab001d4ba2bfa0e5c137bc56409ecc4cbc3ac864"
STAMP="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT_DIR="${PROJECT_DIR}/preflight-${STAMP}"

mkdir -p "$OUT_DIR"

git -C "$REPO_DIR" rev-parse HEAD > "${OUT_DIR}/benchmark-commit.txt"
git -C "$REPO_DIR" status --short > "${OUT_DIR}/benchmark-status.txt"
nvidia-smi -q > "${OUT_DIR}/nvidia-smi-q.txt"
nvidia-smi --query-compute-apps=pid,used_memory,name --format=csv,noheader \
  > "${OUT_DIR}/gpu-processes.txt"
sha256sum \
  "${MODEL_DIR}"/model-0000*-of-00005.safetensors \
  "${MODEL_DIR}"/config.json \
  "${MODEL_DIR}"/generation_config.json \
  "${MODEL_DIR}"/hf_quant_config.json \
  "${MODEL_DIR}"/tokenizer_config.json \
  "${MODEL_DIR}"/chat_template.jinja \
  > "${OUT_DIR}/checkpoint-sha256.txt"
docker image inspect "$IMAGE" > "${OUT_DIR}/image-inspect.json"
docker run --rm --entrypoint git "$IMAGE" -C /sgl-workspace/sglang status --short \
  > "${OUT_DIR}/image-git-status.txt"
docker run --rm --entrypoint git "$IMAGE" -C /sgl-workspace/sglang diff --binary HEAD \
  > "${OUT_DIR}/image-git-diff.patch"
sha256sum "${OUT_DIR}/image-git-diff.patch" > "${OUT_DIR}/image-git-diff.sha256"

echo "PREFLIGHT_DIR=${OUT_DIR}"
