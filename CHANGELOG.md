# Changelog

## Unreleased

- Reworked VoiceCode as a cleaner open-source Python project without one-click setup/installer scripts or generated installer artifacts.
- Added configurable Whisper inference controls for model, device, compute type, beam size, and VAD.
- Added CUDA auto-detection, environment overrides, and safe CPU `int8` fallback for NVIDIA GPU load/inference failures.
- Added `large-v3` and `distil-large-v3` model options.
- Added `POST /transcribe` for local integrations and batch/test transcription without the recorder.
- Added `GET /hardware` and expanded diagnostics/model metadata for CPU/GPU compatibility troubleshooting.
- Removed the hard-coded Hugging Face mirror default; users can still set `HF_ENDPOINT` themselves.
- Updated README, API, architecture, development, FAQ, contributing, and agent guidance for the new project shape.

## 0.1.0

- Initial local desktop speech-to-text app with Flask/Waitress, pywebview UI, global hotkey, sounddevice recording, and faster-whisper transcription.
- Added local config, transcript history, diagnostics, status, audio devices, and smoke tests.
