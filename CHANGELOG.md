# Changelog

## Unreleased

- Added real lazy adapters for Silero VAD preprocessing, pyannote speaker diarization, and NeMo punctuation restoration, with operational/experimental/error extension states.
- Hardened isolated dependency tasks with package-index-first catalog installs, disk checks, cross-process locking, persistence, cancellation, timeouts, process-tree termination, restart notices, and safer manifest handling.
- Added loopback Host/Origin validation, CSP, anti-framing/content-sniffing headers, and mutation audit logs.
- Added config schema version 2 with legacy migration and a schema endpoint.
- Split model cache, model runtime, transcription services, and recording routes into focused modules.
- Added adaptive hidden-window polling, cached model-size/NVML work, measured model download progress, dialog focus trapping, onboarding resume/recommendations, and diagnostic ZIP export.
- Moved frontend bootstrap infrastructure to ES Modules and added a deterministic static mirror synchronization tool.
- Added browser E2E CI, manual CPU/NVIDIA runtime smoke workflows, clean-wheel verification, checksums, SBOM generation, and build provenance attestation.
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
