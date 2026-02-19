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
        self._persistent_piper: Optional[PersistentPiper] = None

    def start_persistent_piper(self, speed_factor: float = 1.0):
        """Pre-warm or restart the persistent piper process."""
        self._check_ready()
        length_scale = self.clean_speed_scale(speed_factor)
        if self._persistent_piper:
            self._persistent_piper.stop()
        self._persistent_piper = PersistentPiper(
            self.cfg.piper_binary,
            self.cfg.model_path,
            length_scale=length_scale
        )

    def stop_persistent_piper(self):
        if self._persistent_piper:
            self._persistent_piper.stop()
            self._persistent_piper = None


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
        Generator that yields chunks of PCM audio bytes.
        Uses persistent piper if available, otherwise spawns a one-off process.
        """
        self._check_ready()
        
        # Use persistent piper if pre-warmed
        if self._persistent_piper:
            for chunk in self._persistent_piper.speak(text):
                yield chunk
            return

        # Fallback to one-off process (legacy/backup)
        length_scale = self.clean_speed_scale(speed_factor)
        cmd = [
            self.cfg.piper_binary,
            "--model", str(self.cfg.model_path),
            "--output_raw",
            "--length_scale", str(length_scale),
        ]
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if process.stdin:
            try:
                process.stdin.write(text.strip().encode("utf-8"))
                process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        try:
            while True:
                chunk = process.stdout.read(4096)
                if not chunk: break
                yield chunk
        finally:
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


class PersistentPiper:
    """
    Manages a single Piper process that stays open for streaming.
    Eliminates the ~100ms process spawn overhead.
    """
    def __init__(self, piper_binary: str, model_path: Path, length_scale: float = 1.0):
        self.cmd = [
            piper_binary,
            "--model", str(model_path),
            "--output_raw",
            "--length_scale", str(length_scale),
        ]
        self.process: Optional[subprocess.Popen] = None
        self._start()

    def _start(self):
        self.process = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # removed bufsize=0 to get BufferedReader for read1()
        )

    def speak(self, text: str):
        """Send text to piper and yield PCM chunks."""
        if not self.process or self.process.poll() is not None:
            self._start()
        
        try:
            # Send text with newline to trigger synthesis
            self.process.stdin.write((text.strip() + "\n").encode("utf-8"))
            self.process.stdin.flush()
        except (BrokenPipeError, OSError):
            self._start()
            self.process.stdin.write((text.strip() + "\n").encode("utf-8"))
            self.process.stdin.flush()

        # NOTE: Piper with --output_raw will output audio for the line and then wait.
        # However, reading from stdout can block. We need a way to know when the sentence is done.
        # Alternatively, we rely on the fact that we yield whatever we read.
        # For true persistent streaming, piper might need to be in a specific mode or 
        # we read fixed size chunks until some silence/marker?
        # Actually, Piper --output_raw yields audio as soon as it's ready.
        
        # Simple read loop for this sentence. 
        # Warning: This might read into the start of the NEXT sentence if pushed too fast.
        # But for Doris, we send sentences sequentially.
        
        # Since we don't have an 'end of audio' marker in raw pcm, 
        # we might need to use a short timeout or read in smaller chunks.
        # Standard Piper behavior: it outputs audio and stays silent.
        
        while True:
            # use read1() to get whatever is available without waiting for full 4096 bytes
            # this is significantly better for a persistent stream
            try:
                chunk = self.process.stdout.read1(4096)
                if not chunk:
                    break
                yield chunk
                
                # Heuristic: if we got less than requested, we might be at the end of the current burst
                if len(chunk) < 4096:
                    # Give Piper a tiny bit of time to produce more if it's slow
                    # but don't block forever.
                    break
            except Exception as e:
                print(f"[PIPER DEBUG] Read error: {e}")
                break

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
