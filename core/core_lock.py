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


# Multiple locks for different subsystems
_LOCKS = {
    "llm": Lock(),
    "tts": Lock(),
    "core": Lock()
}

@contextmanager
def exclusive_execution(label: str = "core"):
    """
    Enforces exclusive execution per subsystem.
    
    Usage:
        with exclusive_execution("llm"):
             # Only one LLM call at a time
             pass
             
        with exclusive_execution("tts"):
             # Only one TTS call at a time
             pass
    """
    lock = _LOCKS.get(label, _LOCKS["core"])
    lock.acquire()
    try:
        yield
    finally:
        lock.release()

