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

    def clean_speed_scale(self, user_speed_factor: float) -> float:
        """
        Map user speed (0.5x .. 2.0x) to Piper length scale (inverse).
        2.0x speed = 0.5 length_scale.
        """
        # Clamp to reasonable bounds
        s = max(0.1, min(user_speed_factor, 5.0))
        # Apply perception compensation (Piper length_scale is non-linear/dampened)
        # s=2.0 -> s^1.5 = 2.8 -> length_scale ~0.35 -> effective speed ~2x
        s = s ** 1.5
        return 1.0 / s

    def synthesize(self, text: str, *, filename_stem: str = "reply") -> Path:
        """
        Legacy file-based synthesis.
        """
        if not text or not text.strip():
            raise ValueError("GhostVoiceEngine.synthesize() received empty text.")
        
        # Re-use the streaming implementation internally or keep distinct?
        # Keeping distinct to minimize risk to legacy paths, but sharing checks.
        self._check_ready()

        ns = time.time_ns()
        import uuid
        uid = str(uuid.uuid4())[:8]
        wav_path = (self.cfg.output_dir / f"{filename_stem}_{ns}_{uid}.wav").resolve()

        cmd = [
            self.cfg.piper_binary,
            "--model", str(self.cfg.model_path),
            "--output_file", str(wav_path),
        ]

        proc = subprocess.run(
            cmd,
            input=text.strip().encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        if proc.returncode != 0 or not wav_path.exists():
            stderr = proc.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Piper failed (exit={proc.returncode}). Stderr: {stderr}")

        return wav_path

    def stream_synthesis(self, text: str, speed_factor: float = 1.0):
        """
        Generator that yields chunks of PCM audio bytes (raw 16-bit little-endian).
        Sample rate depends on model (e.g. 16000Hz for 'low' quality voices).
        Used for low-latency streaming.
        """
        self._check_ready()
        
        length_scale = self.clean_speed_scale(speed_factor)
        
        cmd = [
            self.cfg.piper_binary,
            "--model", str(self.cfg.model_path),
            "--output_raw",  # Stream raw audio to stdout
            "--length_scale", str(length_scale),
        ]

        # Start process with pipes
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Feed text
        if process.stdin:
            try:
                process.stdin.write(text.strip().encode("utf-8"))
                process.stdin.close()  # Signal EOF to piper
            except (BrokenPipeError, OSError):
                pass

        # Read stdout in chunks
        # 4096 bytes is a reasonable chunk size for pumping audio
        # Read stdout in chunks
        try:
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                yield chunk
        except Exception:
            # If generator is closed/interrupted
            process.terminate()
            raise
        finally:
            # cleanup
            if process.poll() is None:
                process.terminate()
            process.wait()

    def _check_ready(self):
        if not self.cfg.enabled:
            raise RuntimeError("GhostVoice is disabled.")
        if not self.cfg.model_path or not self.cfg.model_path.exists():
             raise RuntimeError(f"Model missing: {self.cfg.model_path}")
        if shutil.which(self.cfg.piper_binary) is None:
             raise RuntimeError(f"Piper binary missing: {self.cfg.piper_binary}")
