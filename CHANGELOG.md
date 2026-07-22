# Changelog

## Unreleased

- Added UTF-8 console setup for Windows and PowerShell.
- Standardized logs and error messages to English.
- Added user-config directory support and package launcher wrappers.
- Added smoke tests for config, recording, and transcription flows.
- Added desktop diagnostics, transcript history, model metadata, microphone discovery, text post-processing modes, and Japanese UI/transcription options.
- Hardened startup port/PID checks for repeated launches and unrelated services on the configured port.
- Hardened model reload, recording cancel/start edge cases, and invalid config-file fallback behavior.
- Added PyInstaller one-folder and Inno Setup installer packaging under `packaging/installer/`.
- Added packaged runtime/cache path setup so future Hugging Face / faster-whisper downloads stay under the selected install directory.
- Updated English, Simplified Chinese, and Japanese documentation for installer and runtime-cache behavior.
- Hardened API JSON parsing so malformed JSON, JSON `null`, and non-object payloads return `400` without side effects.
- Hardened config validation for `history_limit` booleans and hotkey modifier/key edge cases.
- Completed final release-candidate checks: `ruff`, `mypy`, `pytest` (`35 passed`), `py_compile`, wheel build, installer build, and custom install/uninstall smoke test.
