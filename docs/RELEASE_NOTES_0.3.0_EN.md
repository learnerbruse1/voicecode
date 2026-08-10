# VoiceCode v0.3.0 — New Models and a faster-whisper Upgrade

Release date: **August 10, 2026**

VoiceCode v0.3.0 builds on the v0.2.0 installer release with an upgraded transcription engine, two additional high-quality open-source models, and localized hints on the model-selection buttons.

## Download

### Windows x64 Installer

`VoiceCode-v0.3.0-Windows-x64-Setup.exe`

- File size: `125,328,173` bytes
- SHA-256:

```text
0D385C1156D8719B82F48C79D6CFA7B8C48B393E26A7EFDE07099F20D2F7DC35
```

> **Important:** This build is not Authenticode code-signed yet, so Windows may show a SmartScreen or "Unknown publisher" prompt. If the installer is signed before release, the file size and SHA-256 will change; regenerate and replace the checksum above.

## Highlights

### Transcription engine

- Upgraded faster-whisper to 1.2.x (Silero VAD v6, built-in `distil-large-v3.5` alias, and more).

### New models

- Japanese-optimized `kotoba-tech/kotoba-whisper-v2.0-faster`: more accurate than `large-v3` on Japanese at about half the size.
- Fast `distil-whisper/distil-large-v3.5-ct2`: near-`large-v3` accuracy at roughly 6x speed.

### UI

- Model-selection buttons (Settings, first-run guide, and the Models page) now show localized hints in English, Simplified Chinese, and Japanese.

## Install and validation

- Reuses the v0.2.0 Windows x64 installer design: selectable destination directory, embedded Python/pip, and models plus optional dependencies kept under `<install-dir>\runtime`.
- Automated verification passed: 12 required files, embedded pip 26.2.1, 394 entries per language catalog, Minesweeper payload, silent uninstall.
- Manual smoke passed: app launch, `/health` PID check, `/models` returns all 9 models, tiny model downloaded and initialized to `ready` on CPU int8, transcription endpoint returned HTTP 200.
- This build is unsigned; public release still requires timestamped code signing and a post-signing re-check.