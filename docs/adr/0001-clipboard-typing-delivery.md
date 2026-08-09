# Clipboard paste as the default typing delivery

Typing delivery previously simulated keystrokes with pynput, which is slow for long dictation and unreliable for some input. We now default to writing the transcription to the Windows clipboard, sending Ctrl+V to the active application, and restoring the previous clipboard contents; simulated keystrokes remain available via the `typing_mode` config and act as the fallback when clipboard paste is unavailable.

Status: accepted

## Considered options

- **Simulated keystrokes** (previous default): no clipboard side effects, but slow for paragraphs and can garble non-ASCII input.
- **Clipboard paste** (chosen): near-instant, but briefly replaces the clipboard and fails in applications that block paste.

## Consequences

- `typing_mode` selects `clipboard` (default) or `keystrokes`; `typing_delay_ms` tunes the pre-delivery delay (default 150).
- The previous clipboard **text** contents are restored ~120 ms after the paste so the target application's paste handler is not raced; when no text was captured, the clipboard is cleared instead. Non-text clipboard contents (images, file lists) are not preserved.
- Non-Windows platforms automatically fall back to simulated keystrokes.
- Deliveries are serialized so rapid successive dictations cannot race each other's clipboard restore.
- A target application that silently ignores Ctrl+V cannot be detected; in that case the transcription is not delivered and no fallback triggers, because there is no reliable signal to detect the ignore.
