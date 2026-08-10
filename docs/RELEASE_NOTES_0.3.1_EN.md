# VoiceCode v0.3.1 — Stability and Compatibility Fixes

Release date: **August 10, 2026**

VoiceCode v0.3.1 is a fix release: it resolves the recording freeze that could occur after a failed GPU transcription, and hardens robustness and smoothness across differently configured computers.

## Download

### Windows x64 Installer

`VoiceCode-v0.3.1-Windows-x64-Setup.exe`

- File size: `125,338,286` bytes
- SHA-256:

```text
F5C24EBE2D3B6A3A23E7776B17FE0774FB3C0AB22A49E0ED3B44F75396DC71FA
```

> **Important:** This build is not Authenticode code-signed yet, so Windows may show a SmartScreen or "Unknown publisher" prompt. If the installer is signed before release, the file size and SHA-256 will change; regenerate and replace the checksum above.

## Key fixes

- Fixed the recording/UI freeze after a failed or hung GPU transcription: transcriptions now run on a serial worker with a 120 s watchdog timeout, the model lock is never held across a native inference call, and a failed or timed-out model is discarded and reloaded (with CPU int8 fallback) automatically, so the app recovers without a restart.
- Closing the "processing" overlay now aborts the in-flight request and resets the UI, so the record button cannot stay stuck.
- Model warm-up is bounded (30 s) and no longer holds the model lock, so startup or model switching cannot freeze.
- Frontend status, stats, and partial-draft polling now use bounded request timeouts.
- CPU thread defaults are hardened (`WHISPER_CPU_THREADS` is capped to logical cores) and the first-run model recommendation is VRAM-aware (low-VRAM GPUs are recommended `base`).
- Includes all v0.3.0 features: faster-whisper 1.2.x, Japanese-optimized Kotoba Whisper v2.0, Distil Whisper Large v3.5, and localized hints on model-selection buttons.

## Validation

- Automated verification passed: 12 required files, embedded pip 26.2.1, 394 entries per language catalog, Minesweeper payload, silent uninstall.
- Manual smoke passed: launch, `/health` PID, version meta 0.3.1, all 9 models in `/models`, tiny model CPU int8 transcription HTTP 200.
- This build is unsigned; public release still requires timestamped code signing and a post-signing re-check.