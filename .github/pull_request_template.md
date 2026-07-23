## Summary

-

## Validation

- [ ] Static root/package mirrors and i18n catalog parity are preserved when UI files change.
- [ ] Packaging/release docs and artifact checks are updated when package data or workflows change.

- [ ] `python -m ruff format --check app.py main.py tests src/voicecode`
- [ ] `python -m ruff check app.py main.py tests src/voicecode`
- [ ] `python -m mypy app.py main.py src/voicecode`
- [ ] `python -X utf8 -m pytest -q`
- [ ] Manual desktop smoke test, if UI/runtime behavior changed
- [ ] Installer build/install smoke test, if packaging/runtime paths changed

## Notes

Mention any release, migration, packaging, runtime-cache, or privacy impact here.
