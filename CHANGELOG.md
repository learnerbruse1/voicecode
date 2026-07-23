# Changelog

## Unreleased

- Added a persisted first-start guide for language, required dependencies, microphone, model, and hardware setup.
- Made the Extensions page operable with validated enable/config controls and one-click isolated dependency installation.
- Added install-all-required dependency tasks and config-aware extension readiness.
- Moved UI catalogs to packaged external JSON files with asynchronous loading and parity tests.
- Split Flask routes into management, history, and system Blueprints.
- Split dependency management into catalog, environment, installer, types, and compatibility facade modules.
- Added packaging and release guides; release CI now builds and validates wheels and source distributions.
- Updated architecture diagrams, API references, configuration, troubleshooting, module, hardware, FAQ, and multilingual README documentation on July 23, 2026.

## 0.1.0

- Initial local desktop speech-to-text app with Flask/Waitress, pywebview UI, global hotkey, sounddevice recording, and faster-whisper transcription.
- Added local config, transcript history, diagnostics, status, audio devices, and smoke tests.
