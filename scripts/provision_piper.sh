#!/bin/sh
set -eu

# Provision a local Piper TTS voice model into models/piper/.
#
# NOTE on Korean: official rhasspy/piper-voices has no Korean voice. The
# community KSS model (neurlang/piper-onnx-kss-korean) uses phoneme_type
# "pygoruut" which is NOT supported by the piper-tts pip package (only
# espeak/text/pinyin are). For Korean TTS use TTS_PROVIDER=local_espeak until
# a piper model with phoneme_type "espeak" or "text" is available.
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

# Validate phoneme_type compatibility with the piper-tts pip package.
# Supported: espeak, text, pinyin. Unsupported: pygoruut and others.
config_path="$DEST_DIR/$config_name"
if command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1; then
  _py=$(command -v python3 2>/dev/null || command -v python)
  phoneme_type=$("$_py" -c "
import json, sys
try:
    d = json.load(open('$config_path'))
    print(d.get('phoneme_type', 'espeak'))
except Exception as e:
    print('unknown', file=sys.stderr)
    print('espeak')
" 2>/dev/null)
  case "$phoneme_type" in
    espeak|text|pinyin)
      echo "phoneme_type: $phoneme_type — compatible with piper-tts pip package."
      ;;
    *)
      echo ""
      echo "WARNING: phoneme_type '$phoneme_type' is NOT supported by piper-tts (pip)."
      echo "  The model was downloaded but will fail at synthesis time."
      echo "  Options:"
      echo "    - Use TTS_PROVIDER=local_espeak (Korean espeak-ng voice works now)"
      echo "    - Find a piper model with phoneme_type 'espeak' for your target language"
      echo "    - Use a compiled piper binary that bundles '$phoneme_type' support"
      echo ""
      ;;
  esac
fi

echo "Done. Set PIPER_MODEL_PATH=/models/piper/$base_name in .env to use this model."
