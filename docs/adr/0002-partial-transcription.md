# Periodic full re-transcription for live partial results

While recording, VoiceCode shows a provisional transcription preview ("partial result") in its panel, produced by periodically re-transcribing the accumulated audio buffer every `partial_interval_ms` (default 600 ms). The preview is panel-only and never delivered to the target application; when recording stops, the complete utterance is transcribed once more and that final transcription is delivered and stored in history. The UI polls the local `/status` endpoint to receive the preview.

Status: accepted

## Considered options

- **Periodic full re-transcription** (chosen): simple and stable; CPU cost grows with utterance length, acceptable for short dictation; controlled by `partial_results` and `partial_interval_ms`.
- **Incremental chunk stitching**: transcribes only audio added since the last preview — faster, but chunk boundaries split words and merging is error-prone.
- **SSE/WebSocket push**: lower latency, but adds transport complexity for a preview that already has hundreds of milliseconds of inherent latency.

## Consequences

- A daemon worker transcribes a snapshot of the recording buffer at most once per `partial_interval_ms`; work is never queued, and snapshots shorter than 0.5 s are skipped.
- Drafts are never delivered to the target application nor written to history; only the final transcription is.
- `partial_results` (default on) and `partial_interval_ms` (200–5000) are user-configurable.
