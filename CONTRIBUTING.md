# Contributing

Thanks for helping improve VoiceCode.

## Before you submit changes

- Run `python -m ruff check app.py main.py tests`
- Run `python -m mypy app.py main.py`
- Run `python -m pytest`
- Keep user-visible logs and error messages in English.
- Do not commit generated caches such as `__pycache__`, `.pytest_cache`, or `htmlcov`.

## Code style

- Prefer small, focused changes.
- Keep platform-specific behavior behind safe fallbacks.
- Add or update tests for bug fixes.
