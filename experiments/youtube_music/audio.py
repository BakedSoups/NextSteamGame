from __future__ import annotations

import math
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Segment:
    start_seconds: float
    end_seconds: float
    confidence: float


def read_wav_mono(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        sample_rate = source.getframerate()
        width = source.getsampwidth()
        frames = source.readframes(source.getnframes())
    if width != 2:
        raise ValueError("The experiment currently accepts 16-bit PCM WAV files")
    audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, sample_rate


def spectral_signature(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    if len(audio) == 0:
        return np.zeros(12, dtype=np.float32)
    window = np.hanning(len(audio))
    spectrum = np.abs(np.fft.rfft(audio * window)) + 1e-8
    frequencies = np.fft.rfftfreq(len(audio), 1.0 / sample_rate)
    edges = np.geomspace(35, min(sample_rate / 2, 16000), 13)
    bands = [float(np.log1p(spectrum[(frequencies >= left) & (frequencies < right)]).mean())
             if np.any((frequencies >= left) & (frequencies < right)) else 0.0
             for left, right in zip(edges[:-1], edges[1:])]
    vector = np.asarray(bands, dtype=np.float32)
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def detect_music_segments(
    audio: np.ndarray,
    sample_rate: int,
    window_seconds: float = 12.0,
    min_segment_seconds: float = 45.0,
    change_threshold: float = 0.18,
) -> list[Segment]:
    window_samples = max(1, int(window_seconds * sample_rate))
    signatures = [
        spectral_signature(audio[start : start + window_samples], sample_rate)
        for start in range(0, len(audio), window_samples)
        if len(audio[start : start + window_samples]) >= window_samples // 2
    ]
    if not signatures:
        return []
    minimum_windows = max(1, math.ceil(min_segment_seconds / window_seconds))
    boundaries = [0]
    for index in range(1, len(signatures)):
        distance = 1.0 - float(np.dot(signatures[index - 1], signatures[index]))
        if distance >= change_threshold and index - boundaries[-1] >= minimum_windows:
            boundaries.append(index)
    boundaries.append(len(signatures))
    duration = len(audio) / sample_rate
    return [
        Segment(
            start_seconds=start * window_seconds,
            end_seconds=min(end * window_seconds, duration),
            confidence=1.0,
        )
        for start, end in zip(boundaries[:-1], boundaries[1:])
        if end > start
    ]


class SpectralBaselineClassifier:
    """Deterministic smoke-test classifier, not a production music model."""

    def predict(self, audio: np.ndarray, sample_rate: int) -> dict[str, list[dict[str, float | str]]]:
        signature = spectral_signature(audio, sample_rate)
        low = float(signature[:4].mean())
        middle = float(signature[4:8].mean())
        high = float(signature[8:].mean())
        instruments = sorted(
            [("bass / low strings", low), ("guitar / keys", middle), ("cymbals / bright synth", high)],
            key=lambda item: item[1],
            reverse=True,
        )
        return {
            "instruments": [{"label": label, "score": score} for label, score in instruments],
            "genres": [],
            "warning": [{"label": "spectral baseline only; configure a pretrained CNN", "score": 1.0}],
        }

