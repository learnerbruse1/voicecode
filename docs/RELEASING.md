# Release Guide

This guide describes the repository release process. The package version has a single source in `src/voicecode/__init__.py`; setuptools reads it dynamically and the UI receives it through injected metadata.

## 1. Prepare the release

1. Choose a semantic version and create a release branch.
2. Move completed `CHANGELOG.md` entries from **Unreleased** into a dated version section.
3. Update version strings, the sidebar version if still static, and compatibility notes.
4. Review dependency ranges and supported Python classifiers.
5. Confirm documentation for onboarding, extensions, APIs, packaging, Minesweeper-only UI behavior, and migration behavior.

## 2. Run quality gates

```powershell
python -m ruff format --check app.py main.py tests src/voicecode packaging/windows tools
python -m ruff check app.py main.py tests src/voicecode packaging/windows tools
python -m mypy app.py main.py src/voicecode
python -X utf8 -m pytest -q
python -X utf8 -m py_compile app.py main.py src/voicecode/app.py src/voicecode/main.py src/voicecode/__init__.py src/voicecode/__main__.py src/voicecode/runtime.py
Get-ChildItem src/voicecode/static/js/*.js | ForEach-Object { node --check $_.FullName }
```

## 3. Build artifacts

```powershell
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
python -X utf8 tools/generate_icon.py
python -X utf8 packaging/windows/build_windows_installer.py
python -X utf8 packaging/windows/verify_windows_installer.py `
  --installer dist/windows/installer/VoiceCode-v0.2.0-Windows-x64-Setup.exe `
  --install-dir "$env:TEMP\VoiceCode-installer-smoke" `
  --version 0.2.0 `
  --skip-launch `
  --uninstall
```

Follow [PACKAGING.md](PACKAGING.md) to inspect static assets and install the wheel into a clean environment. Use a disposable path for the verifier because the installer has a stable AppId. For v0.2.0, compare the manual result with [RELEASE_VALIDATION_0.2.0.md](RELEASE_VALIDATION_0.2.0.md).

## 4. Manual smoke matrix

At minimum verify:

- first launch opens the guide and persists completion;
- required dependency installation reports progress and survives reload;
- an extension can be enabled, configured, and supplied with dependencies;
- English, Chinese, and Japanese catalogs load from JSON and round-trip `en -> zh -> ja -> en` without losing the selected state;
- the Minesweeper-only page renders Beginner, Intermediate, and Expert modes and no card-game view is present;
- CPU recording/transcription works;
- model download/load/cache deletion works;
- history search/export/delete works;
- a second VoiceCode launch focuses the existing instance and exits cleanly, while an unrelated service on the configured port fails clearly;
- mutating API calls reject an invalid local token;
- config/log/history files are writable outside package resources;
- a custom-path Windows install serves `/`, all JSON catalogs, the application icon, embedded pip, and a ready cached/downloaded model;
- repair install, silent uninstall, retained runtime data, and reinstall behave as documented;
- `Get-AuthenticodeSignature` reports a valid timestamped signature for the exact public artifact.

For GPU releases, repeat model load and inference on every advertised CUDA/CuDNN combination.

## 5. Tag and CI

Create an annotated `vX.Y.Z` tag only after all gates pass. The release workflow runs quality gates, builds wheel/sdist, performs a clean-environment wheel smoke test, builds the Windows x64 installer, silently installs and validates it, uninstalls it, and uploads the installer with `verification.json`. The Python artifact job creates checksums, a CycloneDX SBOM, and provenance attestations. Windows code signing and timestamping remain maintainer-controlled gates; rerun the installer smoke and generate the final checksum after signing because signing changes the file hash.

## 6. Rollback

Do not reuse a published version number. If an artifact is broken:

1. mark the release as affected;
2. document the issue in `CHANGELOG.md` and the release notes;
3. fix forward with a patch version;
4. preserve checksums and provenance for any withdrawn artifact.

## Runtime hardware smoke

Use the manual **Runtime Smoke** workflow for an actual CPU tiny-model download/inference test. Its optional NVIDIA job targets a labeled self-hosted GPU runner so CUDA claims are never inferred from mocked CI.
