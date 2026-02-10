"""
core_drivers.py

Authoritative behavioral + TTS control surface for Doris.
No logic here — only defaults and tunable parameters.
"""

from dataclasses import dataclass
import os

# ============================================================================
##  ##                                                      ##  ##  EXISTING TTS BEHAVIOR DRIVERS  ##  ##
# ============================================================================

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


# ============================================================================
##  ##                                                      ##  ##  RUNTIME / CPU SAFETY DRIVERS (Phase 1)  ##  ##
# ============================================================================

# Hard CPU caps (Beelink-safe defaults)
CPU_THREADS: int = 8
TORCH_INTEROP_THREADS: int = 1

# TTS engine selection
# Valid values: "legacy", "qwen3"
TTS_ENGINE: str = "legacy"

# FlashAttention2 policy (OFF by default)
ENABLE_FLASH_ATTENTION_2: bool = False

def apply_cpu_limits() -> None:
    """
    Enforce hard CPU limits.
    Must be called before loading LLM or TTS models.
    Safe to call multiple times.
    """
    os.environ.setdefault("OMP_NUM_THREADS", str(CPU_THREADS))
    os.environ.setdefault("MKL_NUM_THREADS", str(CPU_THREADS))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(CPU_THREADS))
    os.environ.setdefault("NUMEXPR_NUM_THREADS", str(CPU_THREADS))

    try:
        import torch
        torch.set_num_threads(CPU_THREADS)
        torch.set_num_interop_threads(TORCH_INTEROP_THREADS)
    except Exception:
        # Torch may not be imported yet - acceptable
        pass