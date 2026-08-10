# Transcription API

## `POST /record/start`

Starts microphone recording. Optional JSON fields: `language`, `audio_device`.

## `POST /record/stop`

Stops recording, transcribes buffered audio, post-processes text, writes history when enabled, and returns text.

## `POST /record/cancel`

Cancels active recording/transcription and suppresses stale output.

## `POST /transcribe`

Transcribes uploaded files or JSON float samples without using the recorder.

JSON example:

```json
{"audio": [0.0, 0.1, -0.1], "language": "en", "output_format": "json"}
```

`output_format` supports `json`, `txt`, `srt`, and `vtt` when exporters are enabled.

## Transcription watchdog

Transcriptions run on a single serial worker and are bounded by a 120-second watchdog (`VOICECODE_TRANSCRIBE_TIMEOUT`). If a native inference call hangs or fails, VoiceCode discards the model and reloads it on CPU int8, so the next request makes progress instead of freezing the app; GPU failures fall back to CPU automatically. `POST /record/stop` and `POST /transcribe` return `503` with a clear message when a timeout occurs.

> v0.2.0 installed-artifact smoke revalidated this API area on July 24, 2026; contracts were unchanged. See [the final installer validation](../RELEASE_VALIDATION_0.2.0.md).
