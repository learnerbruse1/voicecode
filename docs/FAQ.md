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
- `distil-whisper/distil-large-v3.5-ct2`: fast distilled large-v3.5; near-`large-v3` accuracy at about 6x speed; strong for English; GPU recommended.
- `kotoba-tech/kotoba-whisper-v2.0-faster`: Japanese-optimized Whisper; more accurate than `large-v3` on Japanese at about half the size; GPU recommended.

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

## Does VoiceCode include games?

VoiceCode includes only a client-side Minesweeper page with Beginner, Intermediate, and Expert modes. Card-game content is not included in the source UI or Windows installer. Minesweeper has no backend API and does not persist board state.

## Is there a Windows installer?

Yes. VoiceCode v0.2.0 provides a maintained Windows x64 installer with a selectable destination directory. It includes core dependencies plus an embedded Python/pip runtime. Models, optional packages, and download caches are stored below `<install-dir>\runtime`. Installer sources are in `packaging/windows/`; generated Setup executables remain ignored release artifacts under `dist/windows/`.

## Where are settings stored?

- Windows: `%APPDATA%\VoiceCode\config.json`
- Linux/macOS: `$XDG_CONFIG_HOME/voicecode/config.json` or `~/.config/voicecode/config.json`

Logs and history are stored next to the config file unless overridden.

## Is audio sent to a cloud service?

No. VoiceCode transcribes locally with the selected Whisper model. Model downloads can contact the model host unless the model is already cached or `VOICECODE_OFFLINE=1` is set.

## Can I use VoiceCode from another local tool?

Yes. Use `POST /transcribe` with a multipart `file` upload or JSON float samples. See [API.md](API.md).

## What happens on first launch?

VoiceCode opens a local setup guide for language, required runtime packages, microphone selection/test, and model/hardware preferences. You can skip and return later from **About**.

## Can extensions install their own packages?

Yes. The Extensions page uses the dependency catalog to install optional packages into an isolated directory. In packaged mode it writes only to the writable `<install-dir>\runtime\dependencies` directory; source/wheel runs use their configured isolated directory. Some heavyweight extensions expose configuration/dependency boundaries before their full inference adapter is enabled by default.

## Where do translations live?

English, Chinese, and Japanese catalogs are JSON files under `static/i18n/` and the packaged `src/voicecode/static/i18n/` mirror.

## Are extension installs cancellable?

Yes. Tasks are persisted, expose progress/logs, have a configurable timeout, can be cancelled, and terminate the pip process tree. Some binary dependencies require restarting VoiceCode after completion.

## Are diarization and punctuation still placeholders?

No. Silero VAD, pyannote diarization, and NeMo punctuation have real lazy adapters. They remain disabled by default because packages and model downloads are large; pyannote can also require gated-model credentials.

## What is included in a diagnostic export?

System diagnostics, a redacted config, recent dependency tasks, and a recent redacted application-log tail when available. Transcript history, API tokens, token values, and the configured hotkey key are not included.

## What remains after uninstalling the Windows app?

The Inno Setup uninstaller removes the executable and files that were part of the installer payload. Models, optional dependencies, and caches downloaded later by VoiceCode can remain under `<install-dir>\runtime` so a reinstall can reuse them. To remove everything, uninstall VoiceCode and then manually delete the remaining installation directory.

## Has the v0.2.0 installer been validated?

Yes. Full functional validation completed on July 24, 2026, including custom-path install/repair, embedded pip, English/Chinese/Japanese assets, installed-app HTTP/UI checks, single-instance behavior, cached `base` model loading, sample transcription, uninstall, retained-model verification, and reinstall. The Minesweeper-only payload was rebuilt and revalidated on July 25, 2026 with card-game markers absent. See [RELEASE_VALIDATION_0.2.0.md](RELEASE_VALIDATION_0.2.0.md). The locally tested artifact was unsigned; public release still requires timestamped code signing and one physical microphone check.
