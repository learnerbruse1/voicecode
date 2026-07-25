# VoiceCode v0.2.0 ? Windows Installer, Multilingual UI, and Reliability Improvements

Release date: **July 25, 2026**

VoiceCode v0.2.0 is a major usability and distribution update. It introduces a complete Windows x64 installer, improves model downloads and cache management, adds a guided first-run experience, strengthens extension dependency management and local security, and provides complete English, Simplified Chinese, and Japanese interfaces.

## Download

### Windows x64 Installer

`VoiceCode-v0.2.0-Windows-x64-Setup.exe`

- File size: `125,972,931` bytes
- SHA-256:

```text
53C2EDC3166F60EA97D550C059CCFD4DC76687D279D46D7C9E1348718DC50DE0
```

> **Important:** This installer is not currently Authenticode-signed. Windows may display a SmartScreen or Unknown Publisher warning. If the installer is signed before publication, its file size and SHA-256 checksum will change. Recalculate and replace the values above after signing.

## Highlights

### Windows Installer

- Added a standard Windows x64 installer with a selectable installation directory.
- Bundles VoiceCode's core dependencies and an isolated Python/pip runtime, so users do not need to install Python separately.
- Uses a per-user installation by default and does not require administrator privileges.
- Stores models, optional dependencies, and download caches under `<installation-directory>\runtime`.
- Supports custom-path installation, repair installation, reinstalling, and reuse of existing model caches.
- Added a new application icon for the executable, installer, shortcuts, and web UI.
- Fixed missing packaged frontend assets that previously caused installed builds to display an HTTP 404 page.

### Model Downloads and Runtime

- First launch no longer forces a download of the `base` model; VoiceCode waits for the user to select a model during onboarding.
- Startup now respects the configured model.
- Clearly distinguishes complete caches, partial downloads, and models that have not been downloaded.
- Displays downloaded bytes, estimated size, percentage, speed, elapsed time, and stalled state during model downloads.
- Provides structured guidance for network timeouts, insufficient disk space, permission errors, and damaged model caches.
- Reuses compatible faster-whisper and Hugging Face model caches when available.
- Disables Hugging Face Xet downloads by default to avoid regional CAS/Xet timeout issues and can select a reachable fallback endpoint.
- Automatically detects NVIDIA CUDA and safely falls back to CPU int8 when CUDA initialization or inference fails.

### First-Run and Desktop Experience

- Added a resumable first-run guide for interface language, runtime dependencies, microphone selection, model choice, and hardware settings.
- Added complete English, Simplified Chinese, and Japanese interfaces.
- Fixed corrupted Chinese/Japanese text and language-selection persistence issues.
- Improved model management, hardware summaries, download progress, dialog focus handling, and blocking overlays for long-running operations.
- Repeated Windows launches now focus the existing VoiceCode window instead of producing a local port-conflict error.
- Added searchable and filterable transcription history with copy, delete, and export actions.
- Added diagnostic export support for easier troubleshooting and issue reports.

### Extensions and Dependency Management

- Extension cards now support enable, disable, and validated configuration updates.
- Added one-click installation for required dependencies with progress, status, and log output.
- Dependency tasks support persistence, cancellation, timeouts, disk-space checks, and process-tree termination.
- Optional packages are installed into an isolated directory without modifying the system Python environment.
- Added lazy adapters for Silero VAD, pyannote speaker diarization, and NeMo punctuation restoration.

### Local Security and Reliability

- The local server binds only to `127.0.0.1`.
- Mutating requests are protected by a per-process local API token.
- Added Host/Origin validation, Content Security Policy, anti-framing protection, and content-type security headers.
- Configuration and transcription-history mutations are atomic under concurrent requests.
- Non-empty JSON request bodies must be valid JSON objects; rejected requests do not trigger side effects.
- Desktop startup verifies that `/health` returns the current process PID, preventing connections to unrelated or stale local services.

### Built-in Minesweeper

- Includes classic Minesweeper with Beginner, Intermediate, and Expert difficulty levels.
- Expert mode uses a `16 ? 30` board with 99 mines.
- Supports a safe first click, flagging, chord opening, timing, and win/loss states.
- Minesweeper is fully localized in English, Simplified Chinese, and Japanese.
- Card-game content is not included in this release.

## Installation

1. Download `VoiceCode-v0.2.0-Windows-x64-Setup.exe`.
2. Optionally verify the installer using the SHA-256 checksum above.
3. Run the installer and select an installation directory.
4. Launch VoiceCode and complete the first-run guide for language, microphone, model, and hardware selection.
5. The selected Whisper model must be downloaded on first use. After it is cached, local transcription can work offline.

PowerShell checksum command:

```powershell
Get-FileHash .\VoiceCode-v0.2.0-Windows-x64-Setup.exe -Algorithm SHA256
```

## Upgrading from an Earlier Version

- Run the v0.2.0 installer directly to install or repair the existing application.
- Legacy configuration is migrated automatically; no manual configuration changes are required.
- Existing downloaded models can be reused.
- Configuration, logs, and transcription history remain in the current user's configuration directory.
- The uninstaller removes files managed by Setup, but models, optional dependencies, and caches downloaded later may remain under `<installation-directory>\runtime` for reuse after reinstalling.
- To remove all retained data, manually delete the remaining installation directory after uninstalling VoiceCode.

## Validation

This release completed the following checks:

- Windows x64 installer build passed.
- Silent installation to a custom directory and silent uninstall passed.
- Embedded Python 3.12 and pip execution passed.
- English, Simplified Chinese, and Japanese catalogs were verified with 371 entries each.
- The packaged Minesweeper page, `games.js`, and related styles were verified.
- Removed card-game asset markers were confirmed absent from the installer.
- Local API, model cache, sample transcription, single-instance behavior, and reinstall/cache-reuse checks passed.
- Ruff, mypy, pytest, JavaScript syntax, and static asset synchronization checks passed.
- Full test result: 129 passed and 1 skipped; the coverage gate passed.

## Known Notes

- The current Windows installer is unsigned and may trigger a Windows SmartScreen warning.
- Whisper models are not bundled with the installer. The first model download requires internet access and sufficient disk space.
- NVIDIA GPU mode requires a CUDA/CuDNN runtime compatible with CTranslate2. Use Auto or CPU mode if the GPU runtime is unavailable.
- Microphone access, audio devices, and global hotkeys can be affected by Windows permissions or security software.
- macOS and Linux users should currently run VoiceCode from the Python source package.

## Acknowledgements

Thank you to everyone who tested VoiceCode, reported issues, and contributed improvements. When reporting a problem, please include the VoiceCode version, operating system, selected device, model name, and a diagnostic export whenever possible.
