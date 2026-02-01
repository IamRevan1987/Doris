from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import subprocess
import shutil
import time


@dataclass(frozen=True)
class GhostVoiceConfig:
    """
    GhostVoice = synthesis-only layer.
    - No playback
    - No UI knowledge
    - Only runs when explicitly called
    """
    enabled: bool = True
    piper_binary: str = "piper"          # expects Piper CLI on PATH
    model_path: Optional[Path] = None    # set later (Irish female model)
    output_dir: Path = Path("data/tts")  # safe default
    sample_rate: int = 22050             # metadata only for now


class GhostVoiceEngine:
    def __init__(self, cfg: GhostVoiceConfig) -> None:
        self.cfg = cfg
        self.cfg.output_dir.mkdir(parents=True, exist_ok=True)

    def is_available(self) -> bool:
        if not self.cfg.enabled:
            return False
        if shutil.which(self.cfg.piper_binary) is None:
            return False
        if self.cfg.model_path is None:
            return False
        return self.cfg.model_path.exists()

    def health_check(self) -> dict:
        return {
            "enabled": self.cfg.enabled,
            "piper_on_path": shutil.which(self.cfg.piper_binary) is not None,
            "model_path_set": self.cfg.model_path is not None,
            "model_exists": (self.cfg.model_path.exists() if self.cfg.model_path else False),
            "output_dir": str(self.cfg.output_dir.resolve()),
        }

    def synthesize(self, text: str, *, filename_stem: str = "reply") -> Path:
        """
        Synthesize `text` to a WAV file and return its Path.
        NOTE: This does NOT play audio.
        """
        if not text or not text.strip():
            raise ValueError("GhostVoiceEngine.synthesize() received empty text.")

        if not self.cfg.enabled:
            raise RuntimeError("GhostVoice is disabled (cfg.enabled=False).")

        if shutil.which(self.cfg.piper_binary) is None:
            raise RuntimeError(
                f"Piper binary '{self.cfg.piper_binary}' not found on PATH."
            )

        if self.cfg.model_path is None:
            raise RuntimeError("No Piper model configured (cfg.model_path=None).")

        if not self.cfg.model_path.exists():
            raise RuntimeError(f"Piper model not found: {self.cfg.model_path}")

        # Use high-precision timestamp + random component to prevent collisions during rapid synthesis
        ns = time.time_ns()
        import uuid
        uid = str(uuid.uuid4())[:8]
        wav_path = (self.cfg.output_dir / f"{filename_stem}_{ns}_{uid}.wav").resolve()

        cmd = [
            self.cfg.piper_binary,
            "--model", str(self.cfg.model_path),
            "--output_file", str(wav_path),
        ]

        # Piper reads text from stdin. We keep it that way for clean piping.
        proc = subprocess.run(
            cmd,
            input=text.strip().encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        if proc.returncode != 0 or not wav_path.exists():
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"Piper failed (exit={proc.returncode}). Stderr:\n{stderr}"
            )

        return wav_path
