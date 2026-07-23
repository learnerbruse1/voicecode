# Hardware and Model Selection

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
