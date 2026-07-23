# Release Guide

This guide describes the repository release process. The package version is declared in both `pyproject.toml` and `src/voicecode/__init__.py` and must stay synchronized.

## 1. Prepare the release

1. Choose a semantic version and create a release branch.
2. Move completed `CHANGELOG.md` entries from **Unreleased** into a dated version section.
3. Update version strings, the sidebar version if still static, and compatibility notes.
4. Review dependency ranges and supported Python classifiers.
5. Confirm documentation for onboarding, extensions, APIs, packaging, and migration behavior.

## 2. Run quality gates

```powershell
python -m ruff format --check app.py main.py tests src/voicecode
python -m ruff check app.py main.py tests src/voicecode
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
```

Follow [PACKAGING.md](PACKAGING.md) to inspect static assets and install the wheel into a clean environment.

## 4. Manual smoke matrix

At minimum verify:

- first launch opens the guide and persists completion;
- required dependency installation reports progress and survives reload;
- an extension can be enabled, configured, and supplied with dependencies;
- English, Chinese, and Japanese catalogs load from JSON;
- CPU recording/transcription works;
- model download/load/cache deletion works;
- history search/export/delete works;
- a second process or unrelated service on the configured port fails clearly;
- mutating API calls reject an invalid local token;
- config/log/history files are writable outside package resources.

For GPU releases, repeat model load and inference on every advertised CUDA/CuDNN combination.

## 5. Tag and CI

Create an annotated `vX.Y.Z` tag only after all gates pass. The release workflow builds a wheel and source distribution, runs `twine check`, and uploads them as GitHub Actions artifacts. Publishing to PyPI or attaching signed desktop installers is a maintainer-controlled follow-up.

## 6. Rollback

Do not reuse a published version number. If an artifact is broken:

1. mark the release as affected;
2. document the issue in `CHANGELOG.md` and the release notes;
3. fix forward with a patch version;
4. preserve checksums and provenance for any withdrawn artifact.
