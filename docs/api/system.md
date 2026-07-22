# System API

## `GET /health`

Returns status and process ID.

## `GET /status`

Returns model load state and recorder state.

## `GET /stats`

Returns CPU, GPU, memory, process memory, active device, compute type, and model telemetry.

## `GET /hardware`

Returns CUDA availability, CUDA device count, active device profile, supported devices, and CTranslate2-supported compute types.

## `GET /diagnostics`

Returns privacy-safe diagnostic paths, platform, model state, hardware state, and extension status.

## `POST /log`

Receives frontend logs with optional `component`, `level`, and `msg` fields.
