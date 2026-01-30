from pathlib import Path

PIPER_BIN = "resources/piper/piper/piper"
VOICE_MODEL = "resources/piper/voices/en_GB-southern_english_female-low.onnx"
TTS_OUT_DIR = "data/tts"

def piper_bin_path() -> str:
    return str(Path(PIPER_BIN))

def voice_model_path() -> Path:
    return Path(VOICE_MODEL)

def tts_out_dir() -> Path:
    return Path(TTS_OUT_DIR)
