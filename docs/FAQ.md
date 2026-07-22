# FAQ

## Does VoiceCode require an internet connection?

Only for the first download of a selected Whisper model. After the model is cached, VoiceCode can run offline. Set `VOICECODE_OFFLINE=1` to prevent downloads and require cached models.

## Which model should I choose?

- `tiny`: fastest, lowest accuracy.
- `base`: good CPU default.
- `small`: better accuracy while still practical on CPU.
- `medium`: higher accuracy; GPU recommended for interactive use.
- `large-v3`: best multilingual accuracy; GPU strongly recommended.
- `distil-large-v3`: faster distilled large model; GPU recommended.

## How does GPU support work?

VoiceCode uses `faster-whisper`, which uses CTranslate2. If CTranslate2 detects CUDA, `device=auto` chooses `cuda/float16`. If CUDA initialization or inference fails, VoiceCode falls back to `cpu/int8`.

## Can I force CPU mode?

Yes:

```powershell
$env:WHISPER_DEVICE = "cpu"
$env:WHISPER_COMPUTE_TYPE = "int8"
python -m voicecode
```

You can also choose CPU from the UI.

## Why remove installer scripts?

This repository is maintained as a clean open-source Python project. Generated installer artifacts and one-click local setup scripts often become stale, hide errors, and make cross-platform support harder. Use virtual environments, `pip install -e .`, and CI-tested commands instead.

## Where are settings stored?

- Windows: `%APPDATA%\VoiceCode\config.json`
- Linux/macOS: `$XDG_CONFIG_HOME/voicecode/config.json` or `~/.config/voicecode/config.json`

Logs and history are stored next to the config file unless overridden.

## Is audio sent to a cloud service?

No. VoiceCode transcribes locally with the selected Whisper model. Model downloads can contact the model host unless the model is already cached or `VOICECODE_OFFLINE=1` is set.

## Can I use VoiceCode from another local tool?

Yes. Use `POST /transcribe` with a multipart `file` upload or JSON float samples. See [API.md](API.md).
