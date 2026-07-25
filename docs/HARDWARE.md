# Hardware and Model Selection

The July 24, 2026 v0.2.0 installer pass confirmed that a cached `base` model reached `ready` and completed a JSON-sample transcription in the installed runtime. This is not a substitute for the full CPU/CUDA matrix or a physical microphone test; see [RELEASE_VALIDATION_0.2.0.md](RELEASE_VALIDATION_0.2.0.md).

VoiceCode uses faster-whisper and CTranslate2 for local transcription. Hardware support depends on the installed Python packages, NVIDIA driver, CUDA/CuDNN runtime, and CTranslate2 capabilities.

## Automatic hardware mode

When `device=auto`, VoiceCode:

1. Detects CUDA availability.
2. Checks model VRAM requirements.
3. Queries CTranslate2 supported compute types.
4. Uses CUDA with the best supported compute type when suitable.
5. Falls back to CPU `int8` when CUDA is unavailable, insufficient, or fails.

## Manual CUDA mode

When `device=cuda`, VoiceCode validates VRAM before loading the selected model. If VRAM is below the model minimum, loading is rejected with a clear error.

## Model/VRAM guidance

| Model | Minimum VRAM | Recommended VRAM | Notes |
| --- | ---: | ---: | --- |
| `tiny` | 1GB | 2GB | Fast tests and very low resource machines |
| `base` | 1GB | 2GB | Default CPU-friendly model |
| `small` | 2GB | 4GB | Good everyday balance |
| `medium` | 5GB | 6GB | Better accuracy, GPU preferred |
| `large-v3` | 10GB | 12GB | Maximum multilingual accuracy |
| `large-v3-turbo` | 6GB | 8GB | Latest speed/quality option |
| `distil-large-v3` | 6GB | 8GB | Fast large-style model |

## Diagnostics

Use:

- `GET /hardware`
- `GET /models`
- `GET /stats`
- `GET /diagnostics`

The UI also displays CPU/GPU/memory status on the Home page and top status bar.

## Known limitations

- VoiceCode cannot make an incompatible NVIDIA driver usable.
- NVML is optional; if missing, transcription may still work but detailed GPU telemetry may be unavailable.
- Actual memory use varies by driver, CUDA version, compute type, beam size, and audio length.

## First-start recommendations

The guide defaults to `base` with automatic hardware selection. Resolve required runtime packages before judging model readiness. The microphone step checks enumeration and can sample a short local signal; no audio is uploaded.

## Extension hardware

Silero VAD runs as preprocessing and can add PyTorch memory use. Pyannote and NeMo have independent `device` settings (`auto`, `cpu`, `cuda`) and lazy-load their models. Enabling multiple GPU extensions alongside a large Whisper model can exceed VRAM even when Whisper alone is compatible.

## GPU detection and model cache validation

Physical GPU telemetry is detected independently from CUDA inference support through NVML, `nvidia-smi`, and Windows CIM fallbacks. A model cache is loadable only when its configuration, tokenizer, vocabulary, and a plausibly complete `model.bin` are present. Verified cache snapshots are passed directly to faster-whisper.
