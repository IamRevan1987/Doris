from datetime import datetime
from pathlib import Path
import numpy as np
import wave
import io

###  ###  ###                               ###  ###  --  --  Rules for the wav file builds  --  --  ###  ###
def _waveform_to_wav_bytes(self, waveform: np.ndarray, sample_rate: int) -> bytes:
    """
    Convert a float waveform into a PCM16 WAV (in-memory).
    Expects waveform as mono float32/float64 in [-1 , 1] (or close).
    """
    if sample_rate <= 0:
        raise ValueError("sample_rate must be > 0")

    wav = np.asarray(waveform)
    if np.issubdtype(wav.dtype, np.integer):
        # Assume already PCM-ish; normalize to float [-1, 1] based on dtype range
        info = np.iinfo(wav.dtype)
        wav = wav.astype(np.float32) / float(max(abs(info.min), info.max))

    # If model returns shape (n, 1) or (1, n), flatten to mono
    if wav.ndim > 1:
        wav = wav.reshape(-1)

    # Handle empty audio safety
    if wav.size == 0:
        wav = np.zeros((0,), dtype = np.float32)

    # Convert float waveform to PCM16
    wav = np.clip(wav, -1.0, 1.0)
    pcm16 = (wav * 32767.0).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm16.tobytes())

    return buf.getvalue()

###  ###  ###                               ###  ###  --  --  Archival  --  --  ###  ###


def _get_audio_archive_dir(self) -> Path:
    """
    Central place for Doris audio archives.
    Prefer project-local storage over home-wide clutter.
    """
    # If VoxBox already has a base dir / app dir, use it here instead.
    # Fallback: <project_root>/MEMORY_BACKUP/audio
    base = Path.cwd()
    archive_dir = base / "MEMORY_BACKUP" / "audio"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir

###  ###  ###                               ###  ###  --  --  Helpers  --  --  ###  ###

def _build_archive_wav_name(self, *, prefix: str = "DorisTutor_Archived_MemoryWipe_Alternative") -> str:
    ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    return f"{prefix}_{ts}.wav"


def archive_audio_from_synth(self, synth_out: dict, *, prefix: str = "DorisTutor_Archived_MemoryWipe_Alternative") -> Path:
    """
    Conditionally persist synth output to a WAV archive.
    Call this ONLY when user action requests archive/playback persistence.
    """
    waveform = synth_out.get("waveform", None)
    sr = synth_out.get("sample_rate", None)
    if waveform is None or sr is None:
        raise ValueError("synth_out must include 'waveform' and 'sample_rate'")

    wav_bytes = self._waveform_to_wav_bytes(waveform, int(sr))

    out_dir = self._get_audio_archive_dir()
    fname = self._build_archive_wav_name(prefix=prefix)
    out_path = out_dir / fname

    out_path.write_bytes(wav_bytes)
    return out_path
