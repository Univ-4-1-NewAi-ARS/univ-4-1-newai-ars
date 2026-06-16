#!/bin/sh
# Start the GPT-SoVITS api_v2 server on the HOST (native, like Ollama — not Docker).
# The Dockerized tts-service reaches it via host.docker.internal:9880.
#
# Prereqs (one-time, see docs/06_provider_strategy.md):
#   - GPT-SoVITS cloned to $GPTSOVITS_DIR (default: ~/GPT-SoVITS)
#   - conda env created and `bash install.sh --device CPU --source HF` run
#   - GPT_SoVITS/configs/tts_infer.yaml `custom` block set to device: cpu, is_half: false (macOS)
#   - a Korean reference clip + transcript (set GPT_SOVITS_REF_AUDIO_PATH / _REF_TEXT in .env)
set -eu

GPTSOVITS_DIR="${GPTSOVITS_DIR:-$HOME/GPT-SoVITS}"
CONDA_SH="${CONDA_SH:-$HOME/miniconda3/etc/profile.d/conda.sh}"
ENV_NAME="${GPTSOVITS_ENV:-GPTSoVits}"
PORT="${GPT_SOVITS_PORT:-9880}"

cd "$GPTSOVITS_DIR"
# shellcheck disable=SC1090
. "$CONDA_SH"
conda activate "$ENV_NAME"
echo "Starting GPT-SoVITS api_v2 on 0.0.0.0:$PORT (CPU). First synth warms up (~20s), then ~1-2s."
exec python api_v2.py -a 0.0.0.0 -p "$PORT" -c GPT_SoVITS/configs/tts_infer.yaml
