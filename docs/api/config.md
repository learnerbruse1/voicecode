# Configuration API

## `GET /config`

Returns persisted config merged with defaults.

## `POST /config`

Validates and applies a partial config update. Unknown top-level and extension keys are rejected.

## `POST /config/reset`

Restores default configuration, saves it, and returns the restored config. The UI then reloads the default model.

## Onboarding state

The config includes `onboarding.completed`, `onboarding.completed_version`, and `onboarding.skipped`. Normal clients should update these through the onboarding endpoints rather than posting arbitrary state.

## `GET /config/schema`

Returns `config_version` and core field constraints used by clients.

Inference and typing keys (`beam_size`, `condition_on_previous_text`, `decode_preset`, `partial_results`, `partial_interval_ms`, `typing_mode`, `typing_delay_ms`) are validated and exposed in the schema.

> v0.2.0 installed-artifact smoke revalidated this API area on July 24, 2026; contracts were unchanged. See [the final installer validation](../RELEASE_VALIDATION_0.2.0.md).
