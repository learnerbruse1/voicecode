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
