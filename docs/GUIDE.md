# VoiceCode User Guide — Features & Settings

VoiceCode is a local-first desktop speech-to-text app. It records microphone audio, transcribes it on your machine with `faster-whisper` / CTranslate2, and types the result into the active application with a push-to-talk hotkey. Nothing leaves your computer.

This guide explains every feature and what each setting does.

## Quick start

1. Install VoiceCode and launch it.
2. The first-run guide asks for the UI/transcription language, installs the required local runtime, checks the microphone, and lets you pick a model and hardware.
3. Choose a model (start with `base`, or `small` on a NVIDIA GPU).
4. Hold the hotkey (`Alt+Z` by default), speak, then release — the transcribed text is typed into the active window.

## Core features

### Dictation with a global hotkey

Press and hold the hotkey to record, release to stop, transcribe, and deliver the text. The hotkey is configurable (modifiers `alt`/`ctrl`/`shift` plus a letter or `space`).

### Live partial draft

While you hold the hotkey, the transcript panel shows a provisional draft updated every `partial_interval_ms` (default 600 ms). It is finalized when you release.

### Typing delivery

After transcription the text is delivered to the active application:

- `clipboard` (default on Windows): copies to the clipboard and pastes it; if paste fails it falls back to simulated keystrokes.
- `keystrokes`: always types with simulated keystrokes (works in most apps).

`typing_delay_ms` adds a small delay (default 150 ms) before typing so the target app is ready.

### Decode presets

Controls the decoding quality/speed trade-off:

| Preset | Effect |
| --- | --- |
| `fast` | beam size 1, temperature 0, no previous-text conditioning — fastest, slightly lower quality |
| `balanced` (default) | uses `beam_size` (default 5) and `condition_on_previous_text` |
| `high_quality` | beam size 8 with a temperature ladder — slowest, most accurate |
| `custom` | lets you set `beam_size` and `condition_on_previous_text` yourself |

### Text modes

Post-processing applied to the recognized text:

- `plain`: as recognized.
- `coding`: cleaned up for code/commands.
- `markdown`: formatted for Markdown documents.
- `prompt`: cleaned for prompt input.

### History

Transcriptions can be saved to a local history file (configurable `history_limit`, default 50, auto-trimmed). The History panel supports search, language filtering, single-entry deletion, and JSON/TXT/Markdown export.

### Models & model cache

The Models page lists every supported model with size, minimum/recommended VRAM, a localized hint, and cache state. You can download/load a model or delete a cached model. Complete snapshots are verified before loading; partial downloads resume. Models are not bundled — the first use downloads the selected model (the app falls back to `hf-mirror.com` if the official endpoint is unreachable).

### Extensions

Optional features enabled per-extension in Settings → Extensions:

| Extension | What it does |
| --- | --- |
| `audio_io` | Enables the upload/JSON transcription endpoint and its limits (`max_upload_mb`, `max_json_seconds`, `sample_rate`, allowed suffixes). |
| `exporters` | Output formats for `/transcribe`: `json`, `txt`, `srt`, `vtt`. |
| `hotwords` | A list of terms the recognizer is biased to recognize exactly. |
| `vad` | Voice activity detection engine (`faster_whisper`, `silero`, or `off`) and thresholds (`min_silence_duration_ms`, `speech_pad_ms`, `threshold`). |
| `zh_normalizer` | Optional OpenCC-based Chinese script conversion and spacing/punctuation normalization. |
| `quality` | Optional WER/CER metrics (requires `jiwer`). |
| `diarization` | Speaker diarization with pyannote (model, `token_env` e.g. `HF_TOKEN`, device, min/max speakers). |
| `punctuation` | NeMo punctuation restoration (English, `punctuation_en_bert`). |

**Chinese output script** — the Language panel in Settings lets you choose how Chinese transcriptions are output: **No conversion**, **Simplified Chinese**, or **Traditional Chinese** (config key `extensions.zh_normalizer.script`). Choosing Simplified or Traditional automatically enables the OpenCC-based `zh_normalizer` extension; the first use may ask you to install the `opencc-python-reimplemented` dependency from the Dependencies screen.

Extensions that need extra packages (Silero VAD, pyannote, NeMo, OpenCC) install them into an isolated runtime directory from the Dependencies screen — no global Python changes.

### Security

- The HTTP API binds to `127.0.0.1` only and is protected by a per-process token, loopback Host/Origin validation, CSP, and mutation audit logs.
- Config, history, and logs are stored in per-user writable paths; models and optional packages stay under the installation/runtime directory.

### Offline use

Set `VOICECODE_OFFLINE=1` to forbid downloads and require a complete local model cache. Downloaded models are reusable offline.

### Other built-ins

- First-run onboarding (language, runtime, microphone, model, hardware).
- Diagnostics panel with a one-click ZIP export.
- English / Simplified Chinese / Japanese UI and transcription.
- A Minesweeper panel (Beginner/Intermediate/Expert).

## Settings reference

All settings live in `config.json` (Windows: `%APPDATA%\VoiceCode\config.json`; Unix: `$XDG_CONFIG_HOME/voicecode/config.json` or `~/.config/voicecode/config.json`). Most are also editable in Settings.

| Setting | Values | Default | What it does |
| --- | --- | --- | --- |
| `hotkey` | modifiers `alt`/`ctrl`/`shift`, key letter or `space` | `alt`+`z` | Global push-to-talk hotkey. |
| `model` | see Models below | `base` | Whisper model to load. |
| `device` | `auto`, `cpu`, `cuda` | `auto` | Inference device; `auto` picks CUDA when available, otherwise CPU. |
| `compute_type` | `auto`, `default`, `int8`, `int8_float16`, `int16`, `float16`, `float32` | `auto` | Precision/quantization; `auto` = `float16` on CUDA, `int8` on CPU. |
| `decode_preset` | `fast`, `balanced`, `high_quality`, `custom` | `balanced` | Decoding speed/quality preset. |
| `beam_size` | 1–10 | 5 | Beam width (used by `balanced`/`custom`). |
| `condition_on_previous_text` | boolean | `false` | Whether decoding conditions on previous segment text. |
| `partial_results` | boolean | `true` | Show a live draft while recording. |
| `partial_interval_ms` | 200–5000 | 600 | Live-draft update interval. |
| `vad_filter` | boolean | `true` | Enable silence filtering (VAD). |
| `language` | `auto`, `zh`, `en`, `ja` | `zh` | Transcription language; `auto` detects. |
| `ui_language` | `en`, `zh`, `ja` | `en` | Interface language. |
| `audio_device` | empty, index, or name | empty | Microphone; empty = system default. |
| `text_mode` | `plain`, `coding`, `markdown`, `prompt` | `plain` | Post-processing of the text. |
| `history_enabled` | boolean | `true` | Save transcriptions to history. |
| `history_limit` | integer | 50 | Maximum history entries (auto-trimmed). |
| `font_size` | CSS size | `1rem` | Transcript font size. |
| `theme` | `system`, `light`, `dark` | `system` | UI theme. |
| `append_mode` | `append`, `replace` | `append` | Whether new transcriptions append to or replace the transcript. |
| `typing_mode` | `clipboard`, `keystrokes` | `clipboard` | How text is delivered to the active app. |
| `typing_delay_ms` | 0–5000 | 150 | Delay before typing after transcription. |
| `on_top` | boolean | `false` | Keep the window always on top. |
| `onboarding` | object | not completed | First-run guide state. |

## Models

| Model | Size | Min/Rec VRAM | Recommendation |
| --- | --- | --- | --- |
| `tiny` | ~75 MB | 1 / 2 GB | Fastest; quick tests and very old hardware. |
| `base` | ~150 MB | 1 / 2 GB | CPU default for everyday dictation. |
| `small` | ~500 MB | 2 / 4 GB | Balanced for most laptops and entry GPUs. |
| `medium` | ~1.5 GB | 5 / 6 GB | High accuracy; needs 6GB+ VRAM or a strong CPU. |
| `large-v3` | ~3 GB | 10 / 12 GB | Best multilingual accuracy. |
| `large-v3-turbo` | ~3 GB | 6 / 8 GB | Newest official Whisper; fast with similar accuracy. |
| `distil-large-v3` | ~1.5 GB | 6 / 8 GB | Fast distilled large model. |
| `distil-whisper/distil-large-v3.5-ct2` | ~1.5 GB | 6 / 8 GB | Fast distilled v3.5, near large-v3 accuracy, strong on English. |
| `kotoba-tech/kotoba-whisper-v2.0-faster` | ~1.5 GB | 6 / 8 GB | Japanese-optimized; beats large-v3 on Japanese at half the size. |

Speed/quality tips:

- English on a 6GB+ GPU: `distil-whisper/distil-large-v3.5-ct2` or `large-v3-turbo`.
- Japanese: `kotoba-tech/kotoba-whisper-v2.0-faster` (choose `Japanese` as the transcription language).
- CPU-only: `base`/`tiny` with preset `fast` and device `cpu`.
- Turning off `partial_results` and using preset `fast` are the two biggest speed levers.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `WHISPER_MODEL` | Startup model (default `base`). |
| `WHISPER_DEVICE` | Preferred device (`auto`, `cpu`, `cuda`). |
| `WHISPER_COMPUTE_TYPE` | Preferred compute type (`auto`, `int8`, `float16`, ...). |
| `WHISPER_CPU_THREADS` | CPU worker threads (capped to logical cores). |
| `VOICECODE_CONFIG_FILE` | Override config file path (test/release overrides). |
| `VOICECODE_STATIC_DIR` | Override static UI directory. |
| `VOICECODE_RUNTIME_DIR` | Override runtime directory (models/deps/caches). |
| `VOICECODE_MODEL_DIR` | Override model download/cache root. |
| `VOICECODE_OFFLINE` | `1` = load cached models only. |
| `VOICECODE_SKIP_MODEL_LOAD` | `1` = start UI/API without loading a model. |
| `VOICECODE_SKIP_WARMUP` | `1` = skip the post-load model warm-up. |
| `VOICECODE_TRANSCRIBE_TIMEOUT` | Transcription watchdog timeout in seconds (default 120). |
| `VOICECODE_API_TOKEN` / `VOICECODE_DISABLE_API_TOKEN` | Override or disable the local API token. |
| `PORT` | HTTP port (default 7788). |
| `HF_ENDPOINT` | Explicit Hugging Face endpoint. |
| `HF_HUB_ETAG_TIMEOUT` / `HF_HUB_DOWNLOAD_TIMEOUT` | Hugging Face metadata/download timeouts. |
| `HF_HUB_DISABLE_XET` | Disable Xet/CAS transfers (packaged default: disabled). |
| `VOICECODE_DEP_DIR` | Isolated dependency install directory. |
| `VOICECODE_LOG_LEVEL` | Logging level (default `INFO`). |

## Performance

- GPU (NVIDIA, 6GB+): `float16`; use `large-v3-turbo`/`distil-large-v3.5` or `kotoba` per language.
- GPU with low VRAM: `small`/`base`; if the app detects insufficient VRAM it falls back to CPU int8 automatically.
- CPU: `int8`; adjust `WHISPER_CPU_THREADS`; prefer `base`/`tiny` and preset `fast`.
- If GPU transcription hangs or fails, VoiceCode automatically reloads the model on CPU int8 (watchdog timeout, default 120 s via `VOICECODE_TRANSCRIBE_TIMEOUT`).

## See also

- [API reference](API.md)
- [Configuration](CONFIGURATION.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Windows installer](WINDOWS_INSTALLER.md)