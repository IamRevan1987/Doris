"""
core_drivers.py

Authoritative behavioral + TTS control surface for Doris.
No logic here — only defaults and tunable parameters.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TTSDrivers:
    # --- Text sanitation ---
    strip_markdown: bool = True
    strip_code_blocks: bool = True
    strip_inline_code: bool = True
    strip_urls: bool = True

    # --- Chunking behavior ---
    max_chars_per_chunk: int = 240
    min_chars_per_chunk: int = 60

    # --- Speech formatting rules ---
    speak_lists_as_sentences: bool = True
    collapse_whitespace: bool = True
    normalize_punctuation: bool = True

    # --- Playback behavior ---
    autoplay_on_reply: bool = False
    allow_interrupt: bool = True


# Single exported instance (import this elsewhere)
TTS = TTSDrivers()
