# Roadmap and Extension Ideas

VoiceCode should remain a speech-to-text app first. New features should be optional, local-first where practical, and easy to disable or remove.

## Module boundaries

Current module split:

| Module | Purpose | Replaceable? |
| --- | --- | --- |
| `voicecode.app` | Flask route wiring, model lifecycle orchestration, desktop API surface | Partially |
| `voicecode.settings` | Config schema, validation, config/log/history paths | Yes |
| `voicecode.audio` | Microphone device normalization and recorder | Yes |
| `voicecode.history` | Transcript history JSONL persistence | Yes |
| `voicecode.text_processing` | Plain/coding/Markdown/prompt post-processing | Yes |
| `voicecode.main` | Desktop window, server readiness, global hotkey typing | Yes |
| `voicecode.runtime` | Runtime/cache directory setup | Yes |

Recommended future rule: add new behavior behind a small module and call it from `voicecode.app` instead of expanding `app.py` directly.

## Feature candidates

### 1. Better VAD and endpointing

Goal: reduce silence, accidental hotkey captures, and latency.

Candidate projects:

- [Silero VAD](https://github.com/snakers4/silero-vad)
- Built-in `faster-whisper` VAD remains the default for minimal dependencies.

Suggested design:

- Add `voicecode.vad` with a common `trim_speech(audio) -> audio` interface.
- Config flag: `vad_engine`: `faster_whisper`, `silero`, `off`.
- Keep `faster_whisper` as default; make Silero optional.

### 2. Word-level timestamps and subtitle export

Goal: support reviewing recordings, SRT/VTT export, and editor integrations.

Candidate projects:

- [WhisperX](https://github.com/m-bain/whisperX)
- `faster-whisper` word timestamp support for lighter-weight use cases.

Suggested design:

- Add `voicecode.exporters` with `to_srt`, `to_vtt`, and `to_json`.
- Extend `/transcribe` with `timestamps=true`.
- Keep normal dictation response simple by default.

### 3. Speaker diarization for meetings

Goal: separate speakers in longer recordings while preserving the app's STT focus.

Candidate project:

- [pyannote.audio](https://github.com/pyannote/pyannote-audio)

Suggested design:

- Keep diarization optional because models and licenses may require extra setup.
- Add `voicecode.diarization` with `assign_speakers(segments)`.
- Expose only through file upload/batch transcription, not push-to-talk mode.

### 4. Audio file decoding and preprocessing

Goal: make `/transcribe` robust for WAV/MP3/M4A/FLAC and noisy recordings.

Candidate projects:

- [python-soundfile](https://github.com/bastibe/python-soundfile)
- `numpy` for normalization/resampling-friendly arrays.

Suggested design:

- Add `voicecode.audio_io` for file loading, normalization, max-duration checks, and sample-rate conversion.
- Keep faster-whisper/PyAV path input as the default path to avoid unnecessary dependencies.

### 5. Quality measurement and regression fixtures

Goal: measure transcription quality before changing models or post-processing.

Candidate project:

- [jiwer](https://github.com/jitsi/jiwer)

Suggested design:

- Add optional test fixtures with tiny, redistributable audio clips.
- Add `tests/test_transcription_quality.py` behind an environment flag so CI stays lightweight.
- Track WER/CER for English and Chinese samples.

### 6. Chinese text normalization

Goal: improve Chinese dictation output for punctuation, simplified/traditional conversion, and spacing.

Candidate project:

- [OpenCC](https://github.com/BYVoid/OpenCC)

Suggested design:

- Add `voicecode.normalizers.zh`.
- Config: `chinese_script`: `none`, `simplified`, `traditional`.
- Keep default as `none` to avoid surprising users.

### 7. Punctuation and capitalization restoration

Goal: improve readability for models/languages that produce weak punctuation.

Candidate project:

- [NVIDIA NeMo](https://github.com/NVIDIA/NeMo)

Suggested design:

- Treat as optional post-processing, not core STT.
- Add provider interface: `restore_punctuation(text, language)`.
- Avoid loading large NLP models during app startup.

### 8. Plugin-style feature switches

Goal: make future additions removable.

Suggested design:

- Create a small internal registry, for example `voicecode.features`.
- Each feature declares:
  - config keys
  - optional dependencies
  - routes, if any
  - startup hooks, if any
- Default install should stay lightweight.

## Current implementation status

Completed foundation work includes a persisted first-start guide, operable schema-driven extension settings, isolated one-click dependency tasks, external JSON i18n catalogs, split Flask route modules, and split dependency services. Silero preprocessing, pyannote diarization, and NeMo punctuation adapters are implemented with lazy model loading and explicit experimental/runtime states.

Implemented extension framework and switchable modules:

- `audio_io`: enabled by default, validates JSON samples and uploaded audio files.
- `exporters`: enabled by default, exports JSON/TXT/SRT/VTT.
- `hotwords`: enabled by default, augments Whisper prompts with project terms.
- `vad`: enabled by default, configures faster-whisper VAD.
- `zh_normalizer`: disabled by default, normalizes Chinese spacing/punctuation and lazily uses OpenCC for script conversion.
- `quality`: disabled by default, optional WER/CER helper shell using jiwer.
- `diarization`: disabled by default, real pyannote pipeline with environment-referenced credentials and overlap-based segment labeling.
- `punctuation`: disabled by default, real lazy NeMo punctuation/capitalization inference for configured languages.

## Near-term implementation order

1. Add focused tests for each extension module beyond smoke-route coverage.
2. Add a small frontend extension settings panel.
3. Add `voicecode.audio_io` duration probing when an optional decoder is installed.
4. Add higher-quality SRT/VTT output with word timestamps when available.
5. Improve Silero timestamp remapping so compacted-audio segment times can be projected back to original media time.
6. Add optional real-audio WER/CER fixtures behind an environment flag.
7. Add richer diarization exports and speaker-aware subtitle formatting.

## Non-goals

- Do not turn VoiceCode into a general meeting recorder before dictation is excellent.
- Do not require cloud APIs for core functionality.
- Do not make GPU-only features mandatory.
- Do not add heavyweight optional dependencies to the default install.

## Completed in v0.2.0

- Maintained Windows x64 installer with selectable destination and install-local runtime data.
- Branded executable/installer/web icon assets.
- Single-instance desktop startup and packaged frontend validation.
- UTF-8 Chinese/Japanese catalog repair with `en -> zh -> ja -> en` browser coverage.
- Legacy model-cache migration and reachable Hugging Face endpoint selection.
- Repeatable Windows installer verification with silent install/payload/pip/uninstall CI coverage and a documented v0.2.0 final validation record.
- Resilient pre-build embedded-Python downloads with cache retention, ZIP validation, atomic writes, and retries.
