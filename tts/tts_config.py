from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PIPER_BIN = BASE_DIR / "resources/piper/piper/piper"
TTS_OUT_DIR = BASE_DIR / "data/tts"

def piper_bin_path() -> str:
    return str(PIPER_BIN)

def piper_voice_dir() -> Path:
    return BASE_DIR / "resources/piper/voices"

def voice_model_path() -> Path:
    return piper_voice_dir() / "jenny.onnx"

def tts_out_dir() -> Path:
    return TTS_OUT_DIR
