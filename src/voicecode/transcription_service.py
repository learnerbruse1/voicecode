"""Configuration-driven transcription preprocessing and result finalization."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from .extensions import audio_io, diarization, hotwords, punctuation, vad, zh_normalizer
from .extensions import registry as extension_registry


class TranscriptionService:
    def __init__(
        self,
        load_config: Callable[[], dict[str, Any]],
        post_process_text: Callable[[str, str], str],
    ) -> None:
        self._load_config = load_config
        self._post_process_text = post_process_text

    @staticmethod
    def language_prompt(language: str | None) -> str | None:
        if language == "zh":
            return "Transcribe the speech as Simplified Chinese text."
        if language == "ja":
            return "Transcribe the speech as Japanese text."
        return None

    def transcribe_kwargs(
        self, language: str | None, config: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        config = config or self._load_config()
        vad_config = extension_registry.extension_config(config, "vad")
        hotwords_config = extension_registry.extension_config(config, "hotwords")
        initial_prompt = self.language_prompt(language)
        if extension_registry.is_enabled(config, "hotwords"):
            initial_prompt = hotwords.build_prompt(initial_prompt, hotwords_config)
        kwargs: dict[str, Any] = {
            "language": language,
            "task": "transcribe",
            "beam_size": int(config.get("beam_size", 5)),
            "best_of": 1,
            "condition_on_previous_text": False,
            "initial_prompt": initial_prompt,
            "temperature": 0.0,
        }
        kwargs.update(vad.transcribe_options(vad_config, bool(config.get("vad_filter", True))))
        return kwargs

    def prepare_audio(
        self, audio: np.ndarray | str, config: dict[str, Any]
    ) -> tuple[np.ndarray | str, dict[str, Any] | None]:
        return vad.preprocess_audio(audio, extension_registry.extension_config(config, "vad"))

    def coerce_audio_samples(self, value: Any) -> np.ndarray:
        config = self._load_config()
        audio_config = extension_registry.extension_config(config, "audio_io")
        if not extension_registry.is_enabled(config, "audio_io"):
            raise ValueError("audio_io extension is disabled.")
        return audio_io.coerce_audio_samples(value, audio_config)

    def finalize(self, result: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        audio_context = result.pop("_audio_context", None)
        result["text"] = self._post_process_text(
            result["text"], str(config.get("text_mode", "plain"))
        )
        if extension_registry.is_enabled(config, "zh_normalizer"):
            extension_config = extension_registry.extension_config(config, "zh_normalizer")
            result["text"] = zh_normalizer.normalize(
                result["text"], str(result.get("language", "auto")), extension_config
            )
        if extension_registry.is_enabled(config, "punctuation"):
            extension_config = extension_registry.extension_config(config, "punctuation")
            result["text"] = punctuation.restore(
                result["text"], str(result.get("language", "auto")), extension_config
            )
        if (
            extension_registry.is_enabled(config, "diarization")
            and audio_context is not None
            and result.get("segments")
        ):
            extension_config = extension_registry.extension_config(config, "diarization")
            result["segments"] = diarization.assign_speakers(
                result["segments"], audio_context, extension_config
            )
        return result
