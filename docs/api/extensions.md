# Extensions, Dependencies, and Onboarding API

## `GET /onboarding`

Returns first-start completion and readiness for required runtime packages, microphone devices, and the configured model.

## `POST /onboarding/complete`

Accepts `{ "config": {...}, "skipped": false }`, validates the onboarding-safe preferences, and persists completion.

## `POST /onboarding/reset`

Marks onboarding incomplete without resetting unrelated settings.

## `GET /extensions`

Returns extension status, effective config, a UI-oriented config schema, optional dependency status, and config-aware missing dependency IDs.

## `POST /extensions/<extension_id>`

Validates and saves one extension configuration. Unknown extension IDs and fields are rejected without side effects.

## `POST /extensions/<extension_id>/install`

Starts isolated dependency tasks for the extension. Poll the returned task IDs.

## `GET /dependencies`

Returns the dependency catalog, isolated install directory, missing packages, and the subset requiring user action.

## `POST /dependencies/install-required`

Starts all missing core runtime dependency installs.

## `POST /dependencies/<dependency_id>/install`

Starts one persistent, cancellable, time-limited background install into the isolated dependency directory. Only catalog-defined package-index specs are accepted; API clients cannot submit arbitrary package specifications.

## `GET /dependencies/tasks/<task_id>`

Returns status, percentage, message, error, and recent pip output.

## `POST /dependencies/<dependency_id>/uninstall`

Requires `{ "confirm": true }`. Only manifest-owned paths below the isolated dependency directory may be removed.

Current extension IDs: `audio_io`, `exporters`, `hotwords`, `vad`, `zh_normalizer`, `quality`, `diarization`, and `punctuation`.

## `GET /dependencies/tasks`

Lists recent persisted tasks.

## `POST /dependencies/tasks/<task_id>/cancel`

Cancels a queued/running install and terminates its pip process tree.
