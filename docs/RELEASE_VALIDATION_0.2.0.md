# VoiceCode v0.2.0 Windows Installer Final Validation

**Validation date:** July 24, 2026; Minesweeper-only installer refresh: July 25, 2026
**Result:** Functional validation passed; code signing remains required before public distribution.

## Artifact

| Field | Value |
| --- | --- |
| File | `VoiceCode-v0.2.0-Windows-x64-Setup.exe` |
| Size | 125,972,931 bytes |
| SHA-256 | `53C2EDC3166F60EA97D550C059CCFD4DC76687D279D46D7C9E1348718DC50DE0` |
| Product version | `0.2.0` |
| Signature at validation time | Not signed |

The hash above identifies the locally validated artifact. Rebuilding or signing the installer changes the hash, so release automation must generate and publish a fresh checksum for the final signed file.

## Build environment

- Windows 11 x64 (`10.0.26200`)
- CPython 3.12.9 x64
- PyInstaller 6.21.0
- Inno Setup 6.7.3
- Installer source: `packaging/windows/`

The first clean build exposed a 90-second embedded-Python download timeout after PyInstaller completed. The build pipeline was corrected to download prerequisites before the expensive bundle build, retain them under `build/windows/downloads`, validate the ZIP, write through an atomic `.part` file, and retry failed downloads. A clean rebuild then completed successfully in about five minutes using the cached prerequisites.

## Automated and manual checks

| Check | Result |
| --- | --- |
| PyInstaller one-folder bundle | Passed; refreshed bundle has 4,567 files and 462,101,946 uncompressed bytes |
| Required executable, license, multilingual READMEs, static UI, and icon | Passed |
| Minesweeper-only packaged UI | Passed; `games.js`, board markup, and styles present; removed card-game markers absent |
| Embedded CPython and pip | Passed; Python 3.12 and pip 26.1.2 |
| English, Chinese, and Japanese catalogs | Passed; refreshed installer has 371 entries per catalog |
| Silent custom-path install/repair | Passed |
| Installed `/health` PID matches `VoiceCode.exe` | Passed |
| Local server binding | Passed; only `127.0.0.1:7788` |
| UI root, icon, catalogs, status, models, dependencies, history, diagnostics, and audio-device APIs | Passed |
| Browser UI render | Passed; title, navigation, version 0.2.0, icon, Home view, and first-start guide rendered correctly |
| Cached `base` model | Passed; reached `ready`, 100%, 147,883,848 downloaded bytes |
| JSON sample transcription | Passed; HTTP 200 using the installed model runtime |
| Repeat launch | Passed; second process exited with code 0 and the original PID remained active |
| Repair install | Passed; cached model hash unchanged |
| Silent uninstall | Passed; installed executable/uninstaller removed |
| User-downloaded model preservation | Passed; model remained with unchanged SHA-256 |
| Reinstall after uninstall | Passed; model was reused and returned to `ready` |
| Automated verifier | Passed on July 25 with a disposable custom path, embedded pip, Minesweeper-only payload check, silent uninstall, and JSON report |
| Configured-model startup regression | Passed; installed app started `small` rather than hard-coded `base` |
| Partial cache reporting | Passed; incomplete `small` cache reported `partial=true`, `cached=false` |
| Download progress UI | Passed; bytes, approximate total, percent, speed, elapsed/stalled time, source, and cache path rendered in Chinese |
| Structured timeout popup | Passed; localized summary, previous active model, sanitized technical detail, retry suggestions, source, and cache path rendered |

The July 25 refresh rebuilt the same v0.2.0 version after removing card-game content. The automated verifier installed to `.tmp_installer_validation/ci-fix-final-20260725`, confirmed 12 required payload files, verified Minesweeper-only assets and 371-key catalog parity, ran embedded pip, and completed silent uninstall. The broader interactive/model checks in this record remain from the July 24 pass.

The physical microphone capture path was not automated in this pass. The installed `/audio/devices` endpoint returned successfully, and the release checklist still requires a human microphone recording check on the target release machine.

## Repository quality gates

- Ruff format check: passed for application, tests, packaging, and tools.
- Ruff lint: passed.
- mypy: passed for 34 source files.
- Static mirror and JavaScript syntax checks: passed.
- Workflow YAML parsing and Markdown UTF-8/control/local-link checks: passed.
- Full pytest run: 129 passed, 1 skipped.
- Coverage gate: 75.49% (`--cov-fail-under=75`).
- Wheel build: `voicecode-0.2.0-py3-none-any.whl`, required UI/catalog/icon package data present.

## Reproduce the verification

Build:

```powershell
python -X utf8 tools/generate_icon.py
python -X utf8 packaging/windows/build_windows_installer.py
```

Run the repeatable installer smoke test on a disposable Windows machine or clean CI runner:

```powershell
python -X utf8 packaging/windows/verify_windows_installer.py `
  --installer dist/windows/installer/VoiceCode-v0.2.0-Windows-x64-Setup.exe `
  --install-dir "$env:TEMP\VoiceCode-installer-smoke" `
  --version 0.2.0 `
  --skip-launch `
  --uninstall `
  --report dist/windows/installer/verification.json
```

Omit `--skip-launch` on an interactive Windows desktop to verify the installed executable, `/health`, `/status`, icon, and language catalogs. Do not run the uninstall option against a non-disposable installation.

## Release gate

Functional installer validation is complete. Before publishing:

1. sign the installer with the maintainer-controlled Windows code-signing certificate;
2. timestamp the signature;
3. rerun `Get-AuthenticodeSignature` and the installer smoke test on the signed artifact;
4. generate the final SHA-256 checksum and release provenance for that exact signed file;
5. complete one physical microphone recording/transcription check.
