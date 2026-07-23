# Configuration API

## `GET /config`

Returns persisted config merged with defaults.

## `POST /config`

Validates and applies a partial config update. Unknown top-level and extension keys are rejected.

## `POST /config/reset`

Restores default configuration, saves it, and returns the restored config. The UI then reloads the default model.

## Onboarding state

The config includes `onboarding.completed`, `onboarding.completed_version`, and `onboarding.skipped`. Normal clients should update these through the onboarding endpoints rather than posting arbitrary state.
