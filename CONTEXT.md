# VoiceCode

Local-first speech-to-text desktop app: it captures speech, transcribes it locally with the Whisper model, and delivers the text into the active application.

## Language

**Transcription**:
Converting an audio utterance into text with the Whisper model.
_Avoid_: dictation result, speech-to-text output

**Typing delivery**:
Inserting the transcription text into the active target application. Distinct from transcription: transcription produces text, typing delivery places it.
_Avoid_: paste, autotype, input

**Utterance**:
A single continuous audio capture between recording start and stop; the unit fed to transcription.
_Avoid_: clip
