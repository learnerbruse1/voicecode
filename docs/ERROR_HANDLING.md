# Error Handling and Resilience

VoiceCode is a local desktop application, but it should behave like a production service: failures must be visible, diagnosable, and recoverable whenever possible.

## Error response shape

All API errors return JSON:

```json
{"error": "English error message", "request_id": "abc123def456"}
```

Every response also includes:

```http
X-VoiceCode-Request-ID: abc123def456
```

Use this request ID to correlate a UI popup with backend logs.

## Request logging

Each request logs:

- request ID
- method
- path
- status code
- duration in milliseconds
- content type
- remote address at debug level

Example:

```text
Request started: id=abc123 method=POST path=/record/stop remote=127.0.0.1 content_type=application/json
Request completed: id=abc123 method=POST path=/record/stop status=200 duration_ms=1284.7
```

## Global API error handlers

VoiceCode registers Flask handlers for:

- `HTTPException`: returns JSON instead of an HTML error page.
- unexpected `Exception`: logs the traceback and returns a safe `500` JSON response.

This keeps API consumers and the desktop UI consistent.

## Frontend error handling

The desktop UI displays modal popups for:

- non-2xx API responses
- network errors
- request timeouts
- unhandled JavaScript errors
- unhandled promise rejections
- unsupported model/hardware selections

The popup includes a close button and a copy-details button.

## Long-running operations

Operations that should not be interrupted visually block the UI with a progress overlay:

- Whisper model reload
- CPU/GPU switching
- transcription after recording stops
- restoring defaults and reloading the default model

The overlay dims the page and prevents accidental interaction.

## Model and GPU resilience

- Automatic device mode chooses CUDA when available and suitable, otherwise CPU.
- CTranslate2 supported compute types are queried at runtime.
- Manual CUDA selection performs VRAM validation before model loading.
- Auto mode falls back to CPU when CUDA VRAM is insufficient.
- CUDA load/inference failures fall back to CPU `int8` when safe.

## Upload/request limits

`MAX_CONTENT_LENGTH` is set from `VOICECODE_MAX_UPLOAD_MB` and defaults to 512 MB. The `audio_io` extension also validates uploaded audio extensions, upload size, and JSON sample duration.

## Maintainer checklist

When adding a new route or feature:

1. Validate all request inputs before side effects.
2. Return English errors through `_error` or a domain-specific wrapper.
3. Log enough context to reproduce the failure.
4. Include request ID in any user-facing troubleshooting guidance.
5. Add regression tests for malformed input and expected failure modes.

## Dependency and onboarding resilience

Dependency installation is asynchronous and reports bounded progress/log output. Tasks persist across UI reloads, interrupted tasks are marked failed after application restart, and running tasks can be cancelled. Installs enforce disk-space checks, timeout limits, thread/process locks, and process-tree termination. Uninstall requires explicit confirmation and refuses paths outside the isolated root.

Onboarding completion records user intent; it does not hide dependency, microphone, or model failures. Readiness warnings remain visible through status/dependency pages, and the guide can be rerun.

## Browser/API security errors

Invalid Host headers return `421`; foreign Origins on mutations and invalid API tokens return `403`. Security headers are applied to successful and error responses.

## Packaged startup failures

The desktop launcher treats an existing VoiceCode instance as a successful single-instance handoff. Unrelated port owners, missing packaged UI assets, and unavailable desktop backends remain explicit startup failures. Frozen entry points convert these failures into a clear Windows message and non-zero exit without printing a Python traceback. Installer prerequisite downloads occur before PyInstaller, use atomic temporary files, validate the embedded ZIP, retry transient failures, and preserve successful downloads across subsequent builds.

## User-facing recovery details

Error dialogs include the user message, technical details, suggested actions, and request ID. Copy Details uses the browser clipboard API, an in-page fallback, and a native Windows clipboard bridge in that order. Incomplete model caches use the `model_cache_incomplete` code rather than the generic load failure.
