
import sys
import os
import subprocess
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from tts.tts_config import piper_bin_path, voice_model_path, tts_out_dir
from tts.ghost_voice import GhostVoiceConfig, GhostVoiceEngine
from core.core_tts_rules import chunk_for_tts

def test_streaming():
    print("--- Testing TTS Streaming & Sanitization ---")
    
    # 1. Setup Engine
    cfg = GhostVoiceConfig(
        enabled=True,
        piper_binary=piper_bin_path(),
        model_path=voice_model_path(),
        output_dir=tts_out_dir(),
    )
    engine = GhostVoiceEngine(cfg)
    
    # 2. Test Content (Markdown + Hashtags)
    raw_text = "Testing *emphasis* and #hashtags. This is a robust test... of the streaming system!"
    print(f"Raw Input: {raw_text}")
    
    # 3. Validation: Chunking
    chunks = chunk_for_tts(raw_text)
    print(f"Chunks: {chunks}")
    
    # Verify sanitization
    combined = " ".join(chunks)
    if "*" in combined:
        print("[FAIL] Asterisks not stripped!")
    if "#" in combined:
        print("[FAIL] Hashtags not stripped!")
    else:
        print("[PASS] Sanitization looks good.")

    # 4. Audio Playback Test (Backend Only)
    # We pipe PCM to aplay. Piper output for Jenny is 22050Hz S16LE Mono.
    print("Playing audio via aplay (ensure speakers are on)...")
    
    try:
        aplay = subprocess.Popen(
            ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-c", "1"],
            stdin=subprocess.PIPE
        )
        
        for chunk_text in chunks:
            print(f"Speaking: '{chunk_text}'")
            for pcm_data in engine.stream_synthesis(chunk_text, speed_factor=1.0):
                aplay.stdin.write(pcm_data)
                
        aplay.stdin.close()
        aplay.wait()
        print("[PASS] Audio commands executed.")
    except FileNotFoundError:
        print("[WARN] 'aplay' not found. Skipping audio playback test.")
    except Exception as e:
        print(f"[FAIL] Audio playback failed: {e}")

if __name__ == "__main__":
    test_streaming()
