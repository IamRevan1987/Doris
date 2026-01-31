"""
core_stem.py

Central execution stem for TTS.

Responsibilities:
- Select active TTS engine
- Enforce exclusive execution via core_lock
- Delegate to the appropriate driver
- Provide a stable call surface for the rest of Doris
"""

from __future__ import annotations
from typing import Dict, Any
from core.core_drivers import TTS_ENGINE
from core.core_lock import exclusive_execution
from core.core_driver_qwen3 import Qwen3TTSDriver


# Singleton driver instance (lazy-initialized)
_qwen3_driver: Qwen3TTSDriver | None = None


def _get_qwen3_driver() -> Qwen3TTSDriver:
    global _qwen3_driver
    if _qwen3_driver is None:
        _qwen3_driver = Qwen3TTSDriver()
        _qwen3_driver.initialize()
    return _qwen3_driver


def synthesize_tts(text: str) -> Dict[str, Any]:
    """
    Main TTS entry point for Doris.

    This function:
    - Acquires the global execution lock
    - Routes to the selected TTS engine
    - Returns raw audio + metadata
    """
    with exclusive_execution("tts"):
        if TTS_ENGINE == "qwen3":
            driver = _get_qwen3_driver()
            return driver.synthesize(text)

        # Legacy TTS path (existing implementation)
        raise NotImplementedError(
            "Legacy TTS routing not yet wired into core_stem"
        )
