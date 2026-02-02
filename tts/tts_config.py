from pathlib import Path

PIPER_BIN = "resources/piper/piper/piper"
TTS_OUT_DIR = "data/tts"

def piper_bin_path() -> str:
    return str(Path(PIPER_BIN))

def piper_voice_dir() -> Path:
    return Path("resources/piper/voices")

def voice_model_path() -> Path:
    return piper_voice_dir() / "jenny.onnx"

def tts_out_dir() -> Path:
    return Path(TTS_OUT_DIR)
