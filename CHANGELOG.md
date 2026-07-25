# Changelog

## Unreleased

## 0.2.0 - 2026-07-24

- Added a standard Windows x64 installer with selectable install directory, embedded Python/pip, runtime-local dependencies, models, and caches.
- Completed the v0.2.0 installer validation matrix on July 24, 2026, including custom-path repair install, single-instance startup, multilingual UI/assets, embedded pip, cached-model transcription, uninstall, retained-model reuse, and reinstall.
- Added a repeatable installer smoke tool and release-CI install/payload/pip/uninstall gate.
- Hardened embedded-Python bootstrap downloads with pre-build caching, ZIP validation, atomic temporary files, longer timeouts, and bounded retries.
- Added a new VoiceCode application icon for the executable, installer, shortcuts, and web UI.
- Fixed packaged builds missing frontend static assets, which caused the installed desktop window to display an HTTP 404 page.
- Added Windows single-instance handling so repeat launches focus the existing app instead of producing a port-conflict traceback.
- Added automatic reuse of legacy Whisper caches and reachable Hugging Face endpoint selection when the default endpoint is unavailable.
- Fixed startup always downloading `base` instead of the configured model, deferred first model download until onboarding selection, distinguished partial caches from complete models, and added detailed download progress plus structured network/disk/permission failure guidance.
- Disabled Hugging Face Xet downloads by default for the packaged runtime and added explicit metadata/download timeouts so regional CAS/Xet read failures terminate with actionable UI feedback instead of appearing permanently stuck.
- Restored all corrupted Chinese and Japanese UI strings and added UTF-8 catalog regression checks.
- Fixed first-start language state so switching from Chinese or Japanese back to English persists immediately.
- Fixed Models-page rendering and authenticated frontend logging, and replaced corrupted UI progress separators.
- Prevented missing-dependency warnings from overlapping first-start onboarding and made nested dialog focus/inert state stack-safe.
- Made configuration patching and history mutations atomic under concurrent requests.
- Enforced object-only JSON validation consistently, preserved HTTP 413 responses, and expanded browser/concurrency/package regression coverage with a 75% CI coverage gate.
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

## Unreleased - desktop stability and UI consistency

- Validate Whisper cache snapshots by required files and minimum model size; incomplete downloads remain marked partial and resume instead of being shown as loadable.
- Load complete faster-whisper snapshots directly from disk and retain CUDA-to-CPU fallback.
- Add robust Windows clipboard copying for error details.
- Recover a stale, windowless VoiceCode process that still owns the local port.
- Keep the top bar to compact CPU/GPU/memory summaries and move detailed hardware cards to Settings.
- Unify model cards and hardware summary colors with the application theme.
- Remove emoji-dependent status glyphs that could render as question marks on Windows.
- Add Expert Minesweeper (16 x 30, 99 mines) and complete English, Chinese, and Japanese strings.
