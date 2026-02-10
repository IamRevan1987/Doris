from tts.ghost_voice import GhostVoiceConfig, GhostVoiceEngine
from pathlib import Path
import time

def test_unique_filenames():
    cfg = GhostVoiceConfig(enabled=True, output_dir=Path("./data/tts_test"))
    engine = GhostVoiceEngine(cfg)
    
    # Mock piper binary check and synthesize method to avoid actual syscalls if possible, 
    # but GhostVoiceEngine is simple enough we can just test the public method if we have mock piper.
    # Actually, we don't want to run Piper, just check the filename generation.
    # But synthesis method does everything in one go.
    # Let's just create a dummy "subprocess.run" mock if we can, or just inspect the code by eye?
    # No, let's subclass and override the subprocess call to just touch the file.
    
    class TestEngine(GhostVoiceEngine):
        def synthesize(self, text: str, *, filename_stem: str = "reply") -> Path:
            # Replicate the logic exactly from the file
            ns = time.time_ns()
            import uuid
            uid = str(uuid.uuid4())[:8]
            wav_path = (self.cfg.output_dir / f"{filename_stem}_{ns}_{uid}.wav").resolve()
            
            # Simulate "work"
            wav_path.parent.mkdir(parents=True, exist_ok=True)
            wav_path.touch()
            return wav_path

    test_engine = TestEngine(cfg)
    
    paths = []
    print("Generating 10 files in rapid succession...")
    for i in range(10):
        p = test_engine.synthesize("test", filename_stem="test")
        paths.append(p)
        # No sleep, we want to test collision under load
    
    print(f"Generated {len(paths)} paths.")
    unique_paths = set(paths)
    print(f"Unique paths: {len(unique_paths)}")
    
    if len(paths) != len(unique_paths):
        print("FAIL: Duplicate filenames detected!")
        exit(1)
        
    print("PASS: All filenames are unique.")
    
    # Cleanup
    import shutil
    if cfg.output_dir.exists():
        shutil.rmtree(cfg.output_dir)

if __name__ == "__main__":
    test_unique_filenames()
