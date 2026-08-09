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

**Partial result**:
A provisional transcription preview shown in the VoiceCode panel while recording; it is replaced by the final transcription when recording stops, and is never delivered to the target application.
_Avoid_: draft, live transcript

**Decode preset**:
A named bundle of decoding parameters expressing a speed/accuracy trade-off (`fast`, `balanced`, `high_quality`); `custom` disables the bundle so individual settings apply.
_Avoid_: mode, profile

**Final transcription**:
The definitive transcription produced from the complete utterance after recording stops; it is delivered to the target application and stored in history.
_Avoid_: output
