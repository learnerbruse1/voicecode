"""Declarative catalog for VoiceCode runtime and extension dependencies."""

from __future__ import annotations

from .dependency_types import DependencySpec

DEPENDENCIES: tuple[DependencySpec, ...] = (
    DependencySpec(
        id="whisper-runtime",
        name="Whisper runtime",
        description="Core transcription engine powered by faster-whisper and CTranslate2.",
        pip_spec="faster-whisper>=1.1.1,<2",
        import_modules=("faster_whisper", "ctranslate2"),
        distributions=("faster-whisper", "ctranslate2"),
        github_specs=("git+https://github.com/SYSTRAN/faster-whisper.git",),
        required=True,
        notes="Required for transcription. Installing faster-whisper also installs its runtime dependencies.",
    ),
    DependencySpec(
        id="audio-capture",
        name="Audio capture",
        description="Microphone recording support via python-sounddevice.",
        pip_spec="sounddevice>=0.5,<1",
        import_modules=("sounddevice",),
        distributions=("sounddevice",),
        github_specs=("git+https://github.com/spatialaudio/python-sounddevice.git",),
        required=True,
        notes="Required for push-to-talk microphone recording.",
    ),
    DependencySpec(
        id="opencc-python-reimplemented",
        name="Chinese script conversion",
        description="Simplified/traditional Chinese conversion for the Chinese normalizer extension.",
        pip_spec="opencc-python-reimplemented>=0.1.7,<1",
        import_modules=("opencc",),
        distributions=("opencc-python-reimplemented",),
        feature_ids=("zh_normalizer",),
        github_specs=("git+https://github.com/yichen0831/opencc-python.git",),
    ),
    DependencySpec(
        id="jiwer",
        name="Quality metrics",
        description="WER/CER transcript quality metrics.",
        pip_spec="jiwer>=3,<5",
        import_modules=("jiwer",),
        distributions=("jiwer",),
        feature_ids=("quality",),
        github_specs=("git+https://github.com/jitsi/jiwer.git",),
    ),
    DependencySpec(
        id="silero-vad",
        name="Silero VAD",
        description="Optional Silero voice activity detection package for VAD adapters.",
        pip_spec="silero-vad",
        import_modules=("silero_vad",),
        distributions=("silero-vad",),
        feature_ids=("vad",),
        github_specs=("git+https://github.com/snakers4/silero-vad.git",),
        notes="The built-in faster-whisper VAD works without this package.",
    ),
    DependencySpec(
        id="pyannote-audio",
        name="Speaker diarization",
        description="Optional pyannote.audio dependency for speaker diarization adapters.",
        pip_spec="pyannote.audio>=3,<5",
        import_modules=("pyannote.audio",),
        distributions=("pyannote.audio",),
        feature_ids=("diarization",),
        github_specs=("git+https://github.com/pyannote/pyannote-audio.git",),
        notes="This is a large dependency and may require additional model credentials later.",
    ),
    DependencySpec(
        id="nemo-toolkit",
        name="NeMo punctuation",
        description="Optional NVIDIA NeMo toolkit dependency for punctuation adapters.",
        pip_spec="nemo-toolkit[nlp]>=1,<3",
        import_modules=("nemo",),
        distributions=("nemo-toolkit",),
        feature_ids=("punctuation",),
        github_specs=("nemo-toolkit[nlp] @ git+https://github.com/NVIDIA/NeMo.git",),
        notes="This is a large dependency. PyPI fallback is used if the GitHub install is unavailable.",
    ),
)

_DEPENDENCY_BY_ID = {dependency.id: dependency for dependency in DEPENDENCIES}
_DEPENDENCIES_BY_FEATURE = {
    feature_id: tuple(dep for dep in DEPENDENCIES if feature_id in dep.feature_ids)
    for feature_id in {feature for dep in DEPENDENCIES for feature in dep.feature_ids}
}


def get_dependency_spec(dependency_id: str) -> DependencySpec:
    try:
        return _DEPENDENCY_BY_ID[dependency_id]
    except KeyError as exc:
        raise ValueError(f"Unknown dependency: {dependency_id}") from exc


def dependencies_for_feature(feature_id: str) -> tuple[DependencySpec, ...]:
    return _DEPENDENCIES_BY_FEATURE.get(feature_id, ())
