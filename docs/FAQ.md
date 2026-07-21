# FAQ

## Why does the browser preview say the site cannot be reached?

The local web UI is served by VoiceCode on `127.0.0.1:7788`. Start the app with `run.ps1`, `run.bat`, `python main.py`, or `python -m voicecode`. If the server cannot start, VoiceCode shows a startup error dialog.

## How can I preview the UI without loading a Whisper model?

Set:

```powershell
$env:VOICECODE_SKIP_MODEL_LOAD = "1"
python -m voicecode
```

The UI will open and `/status` will report that model loading was skipped. Recording/transcription will remain disabled until model loading is enabled again.

## What should I do if model download fails?

Check network access, try a different mirror, or manually prepare a compatible faster-whisper model. The Model/Diagnostics panels expose the current model state and error details.

## What should I do if the microphone does not work?

Open the Microphone selector in settings, choose a different input device, then try recording again. Also check Windows microphone privacy settings and whether another app is holding the device.

## Where are settings stored?

Windows default: `%APPDATA%\VoiceCode\config.json`. Override with `VOICECODE_CONFIG_FILE`.

## Where are logs stored?

Windows default: `%APPDATA%\VoiceCode\logs\voicecode.log`. Override with `VOICECODE_LOG_FILE`.

## Does VoiceCode upload audio?

No. Audio is sent only to the local service at `127.0.0.1` and processed locally by Whisper.

## Which UI and transcription languages are supported?

The UI supports English, Simplified Chinese, and Japanese. Transcription language options are auto detect, Chinese, English, and Japanese. Logs and technical error details remain English for release diagnostics.

## How do text modes work?

Text modes apply lightweight post-processing after transcription:

- `Plain`: trimmed raw text
- `Coding`: simple spoken-token replacements such as `open parenthesis` -> `(`
- `Markdown`: simple heading/list prefixes
- `Prompt`: trims and appends final punctuation when missing

## How is transcript history handled?

History is stored locally next to the config file in `history.jsonl` and can be disabled in settings. It is never uploaded by VoiceCode.
