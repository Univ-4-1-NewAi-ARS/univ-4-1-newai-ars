# GPT-SoVITS Server — Live Voice-Clone Verification

## Goal

Stand up a real GPT-SoVITS server and verify end-to-end cloned-voice synthesis
through the tts-service `gpt_sovits` provider.

## Install (host, macOS Apple Silicon)

- Miniconda + conda env `GPTSoVits` (python 3.10); conda restricted to `conda-forge`
  (sandbox blocks the `defaults` channel repodata).
- ffmpeg (brew), and via conda-forge: cmake/make/unzip/wget/pip (install.sh needs them).
- `bash install.sh --device CPU --source HF` → PyTorch 2.12 (CPU), all deps, pretrained
  models + G2PW + NLTK + OpenJTalk dict downloaded (~several GB).
- `GPT_SoVITS/configs/tts_infer.yaml` `custom` block set to `device: cpu, is_half: false`
  (macOS has no CUDA), version v2 (supports Korean `ko`).
- Reference: temporary Korean clip generated via espeak (`~/GPT-SoVITS/ref/ko_ref.wav`,
  22kHz, 5.9s) + matching transcript. Replace with a real voice clip for natural timbre.

## Run

`scripts/gpt_sovits_server.sh` → `python api_v2.py -a 0.0.0.0 -p 9880`. Models load
(BERT/HuBERT/VITS), uvicorn serves on 0.0.0.0:9880. Native on host like Ollama.

## Wiring

- `docker-compose.yml` `x-app-env` anchor now forwards `GPT_SOVITS_*` env to services
  (was the missing link — provider raised "ref not configured" until added).
- `.env` (not committed): `TTS_PROVIDER=gpt_sovits`, `TTS_FALLBACK_PROVIDER=local_espeak`,
  `GPT_SOVITS_BASE_URL=http://host.docker.internal:9880`, `GPT_SOVITS_REF_AUDIO_PATH/_REF_TEXT`.

## Verification

- Direct `POST :9880/tts` (Korean) → HTTP 200, 32kHz mono wav, ~20s (cold warmup).
- Through our tts-service `/synthesize` (provider=gpt_sovits) → `provider=gpt_sovits`,
  `fallback_used=false`, 32kHz wav written to /data/tts; server logged `POST /tts 200`.
- Steady-state latency ~1.7s/sentence after warmup; questions are cached by the tts-service.
- A/B audio (espeak vs gpt_sovits, same sentence) delivered to the user.

## Notes / follow-ups

- Reference voice is espeak-generated (placeholder) → swap a clean 3-10s Korean clip
  + transcript for a natural/specific voice.
- Server is host-native; not part of `scripts/services.sh`. Start it separately.

## Commit

chore: wire GPT-SoVITS host server (compose env + start script + docs)
