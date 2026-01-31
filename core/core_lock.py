"""
core_lock.py

Global execution lock for Doris.

Guarantees that:
- LLM inference
- TTS synthesis

never run at the same time.

This is a hard safety boundary to prevent CPU contention.
"""

from threading import Lock
from contextlib import contextmanager


# Single global lock shared across the app
CORE_EXECUTION_LOCK = Lock()

@contextmanager
def exclusive_execution(label: str = "core"):
    """
        Context manager enforcing exclusive execution.

        Usage:
            with exclusive_execution("tts"):
                run_tts()

        The label is for logging / debugging only.
        """
    CORE_EXECUTION_LOCK.acquire()
    try:
        yield
    finally:
        CORE_EXECUTION_LOCK.release()
