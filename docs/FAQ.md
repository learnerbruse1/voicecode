# FAQ

## Why does the browser preview say the site cannot be reached?

The local web UI is served by VoiceCode on `127.0.0.1:7788`. Start the app with `run.ps1`, `run.bat`, `python main.py`, `python -m voicecode`, or the installed `VoiceCode.exe`. If the server cannot start, VoiceCode shows a startup error dialog.

## Why does VoiceCode report that the port is already used?

VoiceCode only accepts a `/health` response from the current process PID. If another VoiceCode instance is already running, close it or use a different `PORT`. If another local service is using the same port and does not identify itself as VoiceCode, stop that service or change `PORT`.


## Why did my API request return `JSON payload must be an object`?

VoiceCode accepts empty request bodies for endpoints that have defaults, but non-empty JSON request bodies must be valid JSON objects. `null`, arrays, strings, malformed JSON, and other non-object payloads are rejected to avoid accidental side effects such as starting recording or reloading a model.

## How can I preview the UI without loading a Whisper model?

Set:

```powershell
$env:VOICECODE_SKIP_MODEL_LOAD = "1"
python -m voicecode
```

The UI will open and `/status` will report that model loading was skipped. Recording/transcription will remain disabled until model loading is enabled again.

## What should I do if model download fails?

Check network access, try a different mirror, or manually prepare a compatible faster-whisper model. The Model/Diagnostics panels expose the current model state and error details.

For packaged Windows installs, model downloads and cache files are intended to stay under:

```text
<install-dir>\runtime\cache
<install-dir>\runtime\models
```

Make sure the selected install directory is writable by the current user.

## Where are downloaded models and runtime caches stored?

In development runs, VoiceCode normally uses the standard Hugging Face cache locations unless you set `VOICECODE_RUNTIME_DIR` or lower-level Hugging Face cache variables.

In packaged PyInstaller/installer builds, the launcher defaults to:

```text
<install-dir>\runtime
```

and configures Hugging Face / transformer caches below that folder.

## What should I do if the microphone does not work?

Open the Microphone selector in settings, choose a different input device, then try recording again. Also check Windows microphone privacy settings and whether another app is holding the device.

## Where are settings stored?

Windows default: `%APPDATA%\VoiceCode\config.json`. Override with `VOICECODE_CONFIG_FILE`.

Settings are intentionally kept in a user-writable config directory rather than inside the installed package directory.

## Where are logs stored?

Windows default: `%APPDATA%\VoiceCode\logs\voicecode.log`. Override with `VOICECODE_LOG_FILE`.

## Where is transcript history stored?

History is stored locally next to the config file in `history.jsonl` and can be disabled in settings. Override with `VOICECODE_HISTORY_FILE`.

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

## Can I install VoiceCode to a custom folder?

Yes. The Windows installer shows the directory selection page and defaults to:

```text
%LOCALAPPDATA%\Programs\VoiceCode
```

Choose a user-writable path so VoiceCode can create its packaged `runtime` cache directories.

## Can I move the installed folder later?

The one-folder app is designed to keep dependencies and runtime caches together, but a standard installer also creates Start Menu shortcuts and uninstall registry entries. If you want a portable-style move, rebuild or distribute `packaging\installer\dist\VoiceCode\` directly, or reinstall to the new path.
