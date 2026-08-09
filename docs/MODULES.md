# Modules

VoiceCode keeps `voicecode.app` as the core local API/model orchestration entry point while focused route and service modules own independent responsibilities.

## Rules for adding features

1. Keep the core path simple: record audio, transcribe locally, return text.
2. Put route groups in a Blueprint module and pass explicit context callbacks for mutable state.
3. Put dependency metadata, filesystem/status logic, and background execution in separate modules.
4. Validate config in `voicecode.settings` before side effects.
5. Keep default dependencies small; put heavyweight integrations behind optional extras or isolated installs.
6. Every visible label needs matching keys in all external JSON catalogs.
7. Update both static asset trees and extend synchronization/package-data tests.
8. Add API tests for malformed/non-object JSON and no-side-effect failure behavior.

## Backend modules

| Module | Public responsibility |
| --- | --- |
| `voicecode.app` | Flask setup, security/error policy, shared model/service state, shell routes, blueprint registration |
| `voicecode.config_api` | health, status, config get/post/reset/schema, and client-log routes |
| `voicecode.model_api` | model list, cache download/delete, and reload routes |
| `voicecode.model_runtime` | model state/profile locks and executor ownership |
| `voicecode.model_cache` | safe model cache discovery, cached size calculation, deletion |
| `voicecode.transcription_service` | extension-aware VAD, normalization, punctuation, diarization finalization, decode-preset mapping |
| `voicecode.recording_api` | record and direct transcription routes |
| `voicecode.management_api` | onboarding, extension update/install, dependency listing/install/task/uninstall |
| `voicecode.history_api` | history filters, exports, entry deletion, clear route |
| `voicecode.system_api` | hardware, audio device/test, diagnostics, stats routes |
| `voicecode.settings` | defaults, validation, nested merge, config/log/history paths, decode-preset constants |
| `voicecode.audio` | `Recorder`, device normalization/enumeration, level test |
| `voicecode.history` | append/read/filter/delete/clear JSONL persistence, append-time trimming to `history_limit` |
| `voicecode.text_processing` | plain, coding, Markdown, and prompt post-processing |
| `voicecode.runtime` | packaged runtime/cache path setup |
| `voicecode.dependency_types` | dependency spec/task data classes |
| `voicecode.dependency_catalog` | immutable catalog and feature mapping |
| `voicecode.dependency_environment` | isolated path, import status, manifests, safe uninstall |
| `voicecode.dependency_installer` | background pip task execution and retention |
| `voicecode.dependencies` | compatibility facade over split dependency modules |
| `voicecode.main` | desktop startup, PID health check, pywebview, hotkey and clipboard/keystroke typing delivery |
| `voicecode.extensions.base` | extension protocol and status shape |
| `voicecode.extensions.registry` | discovery, effective config, config schema, required dependency mapping |

## Frontend modules

| Asset | Responsibility |
| --- | --- |
| `static/js/app.js` | ES Module bootstrap, navigation, window controls, adaptive polling |
| `static/js/accessibility.js` | reusable focus trapping and focus restoration for dialogs |
| `static/js/i18n.js` | asynchronous external catalog loader |
| `static/i18n/*.json` | complete English/Chinese/Japanese translation catalogs |
| `static/js/dom.js` | DOM references, translation application, shared state/helpers |
| `static/js/api.js` | token-aware JSON requests, timeouts, normalized errors |
| `static/js/config.js` | load/save config and audio device list |
| `static/js/onboarding.js` | first-start steps, readiness, dependency progress, completion/reset |
| `static/js/extensions.js` | schema-driven extension forms, save, one-click dependencies |
| `static/js/dependencies.js` | dependency cards, install/uninstall/task progress, install-all-required |
| `static/js/models.js` | model list, load/download, cache deletion |
| `static/js/settings.js` | settings events, model/hardware changes, decode-preset and partial-preview controls, microphone test |
| `static/js/recorder.js` | recording, partial-preview polling, and transcription interaction |
| `static/js/history.js` | history search/filter/export/copy/delete and diagnostics |
| `static/js/status.js` | model and process status summaries with change-diff DOM updates |
| `static/js/games.js` | Minesweeper-only board generation, timer, flags, and localized state |
| `static/css/app.css` | desktop layout, language-specific sizing, onboarding/extensions UI |

## Extension modules

| Extension | Current behavior |
| --- | --- |
| `audio_io` | validates upload suffix/size and JSON sample arrays |
| `exporters` | JSON/TXT/SRT/VTT response formatting |
| `hotwords` | adds configured phrases to transcription prompts |
| `vad` | configures built-in faster-whisper VAD or optional Silero selection |
| `zh_normalizer` | spacing, punctuation, optional simplified/traditional conversion |
| `quality` | optional WER/CER helper through `jiwer` |
| `diarization` | dependency/config boundary for pyannote adapter work |
| `punctuation` | dependency/config boundary for NeMo restoration work |

`vad`, `diarization`, and `punctuation` now have real lazy adapters. Silero preprocesses speech, pyannote labels timestamped segments, and NeMo restores punctuation for configured languages. They remain opt-in because dependencies and models are large.

## Adding a new extension

1. Add an extension class under `voicecode/extensions/` with defaults and availability checks.
2. Register it in `extensions/registry.py`.
3. Add validation in `settings.validate_extensions_patch`.
4. If packages are needed, add `DependencySpec` entries and feature IDs in `dependency_catalog.py`.
5. Add config choices/required-dependency rules in the registry.
6. Add translation keys to all three JSON catalogs.
7. Add API/behavior tests and update API/module docs.

## v0.2.0 packaging modules

- `voicecode.runtime` configures install-local caches, locates the embedded pip interpreter, and migrates compatible legacy faster-whisper caches.
- `packaging/windows/build_windows_installer.py` downloads/caches validated embedded-Python prerequisites with retries, builds the PyInstaller one-folder application, validates frontend assets, embeds Python/pip, and invokes Inno Setup.
- `packaging/windows/verify_windows_installer.py` silently installs a generated setup executable, checks payload/catalog/icon/runtime/pip integrity, optionally verifies installed HTTP endpoints, writes a JSON report, and can uninstall disposable test installations.
- `tools/generate_icon.py` deterministically generates the SVG, PNG, and multi-size ICO application assets.
