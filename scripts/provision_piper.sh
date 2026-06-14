#!/bin/sh
set -eu

# Provision a local Piper TTS voice model into models/piper/.
#
# Official rhasspy/piper-voices does NOT ship a Korean voice, so the default
# below points at the community KSS Korean model. Override the env vars to
# provision a different voice without editing this script.
#
# Usage:
#   scripts/provision_piper.sh
#   PIPER_VOICE_REPO=rhasspy/piper-voices PIPER_MODEL_FILE=en/en_US/... scripts/provision_piper.sh

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

PIPER_VOICE_REPO="${PIPER_VOICE_REPO:-neurlang/piper-onnx-kss-korean}"
PIPER_MODEL_FILE="${PIPER_MODEL_FILE:-piper-kss-korean.onnx}"
PIPER_CONFIG_FILE="${PIPER_CONFIG_FILE:-piper-kss-korean.onnx.json}"
DEST_DIR="${PIPER_DEST_DIR:-models/piper}"
HF_BASE="${HF_BASE:-https://huggingface.co}"

base_name="$(basename "$PIPER_MODEL_FILE")"
config_name="$(basename "$PIPER_CONFIG_FILE")"
model_url="$HF_BASE/$PIPER_VOICE_REPO/resolve/main/$PIPER_MODEL_FILE"
config_url="$HF_BASE/$PIPER_VOICE_REPO/resolve/main/$PIPER_CONFIG_FILE"

mkdir -p "$DEST_DIR"

if command -v curl >/dev/null 2>&1; then
  fetch() { curl -fL --retry 3 -o "$2" "$1"; }
elif command -v wget >/dev/null 2>&1; then
  fetch() { wget -O "$2" "$1"; }
else
  echo "Need curl or wget to download Piper model." >&2
  exit 1
fi

echo "Provisioning Piper voice from $PIPER_VOICE_REPO"
echo "  model:  $model_url"
fetch "$model_url" "$DEST_DIR/$base_name"
echo "  config: $config_url"
fetch "$config_url" "$DEST_DIR/$config_name"

echo "Done. Set PIPER_MODEL_PATH=/models/piper/$base_name and TTS_PROVIDER=local_piper to use it."
