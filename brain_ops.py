from core.core_drivers import apply_cpu_limits      ##  SAFETY MEASURE, DO NOT REMOVE OR CHANGE THE POSITION OF THIS LINE  ##
from core.core_lock import exclusive_execution
apply_cpu_limits()                                  ##  SAFETY MEASURE, DO NOT REMOVE OR CHANGE THE POSITION OF THIS LINE  ##
#############################################################################################################################
"""
Doris Tutor - Brain Operations
Core logic for Chat Engine, Memory, and TTS integration.
"""

# ---- Imports ----

# Standard Library
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List

# Third-Party
import httpx
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_ollama import ChatOllama

# Local
from core.core_memories import load_turns, append_turn
from tts.tts_config import piper_bin_path, voice_model_path, tts_out_dir
from tts.ghost_voice import GhostVoiceConfig, GhostVoiceEngine


# ---- Chat Engine ----

@dataclass
class ChatEngine:
    """
    Main controller for LLM interaction, Memory management, and TTS synthesis.
    """
    # Config
    user_name: str = "David"
    model_name: str = "llama3.2:1b"
    base_url: str = "http://127.0.0.1:11434"
    memory_path: Path = Path("data/chat.jsonl")
    tts_enabled: bool = True
    temperature: float = 0.15
    num_ctx: int = 12288
    num_predict: int = 205
    timeout: int = 90
    keep_alive: str = "30m"

    # Internal State (init=False)
    tts: GhostVoiceEngine = field(init=False)
    llm: ChatOllama = field(init=False)
    history: List[BaseMessage] = field(default_factory=list, init=False)
    last_tts_wavs: list[str] = field(default_factory=list, init=False)
    last_tts_idx: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        """Initialize LLM, TTS backend, and load memory."""
        print(
            f"[ENGINE] file={__file__} cwd={os.getcwd()} model={self.model_name} "
            f"base_url={self.base_url} keep_alive={self.keep_alive} "
            f"num_ctx={self.num_ctx} num_predict={self.num_predict}"
        )

        # 1. Setup LLM
        self.llm = ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=self.temperature,
            num_ctx=self.num_ctx,
            num_predict=self.num_predict,
            keep_alive=self.keep_alive,
            timeout=self.timeout,
        )

        # 2. Setup TTS
        cfg = GhostVoiceConfig(
            enabled=self.tts_enabled,
            piper_binary=piper_bin_path(),
            model_path=voice_model_path(),
            output_dir=tts_out_dir(),
        )
        self.tts = GhostVoiceEngine(cfg)
        self.last_tts_wavs.clear()
        self.last_tts_idx = 0

        # 3. Setup Memory / History
        system_msg = SystemMessage(
            content=(
                "You are Doris, a life-long teacher, here to help tutor and educate the user. "
                f"The user's name is {self.user_name}"
            )
        )

        self.history = [system_msg]

        if not self.memory_path.exists():
            append_turn(self.memory_path, "system", system_msg.content)

        for t in load_turns(self.memory_path, limit=200):
            role = t.get("role")
            content = (t.get("content") or "").strip()
            if not content:
                continue
            if role == "user":
                self.history.append(HumanMessage(content=content))
            elif role == "assistant":
                self.history.append(AIMessage(content=content))

    # ---- Diagnostics ----

    def backend_ok(self) -> bool:
        """Check if Ollama backend is reachable."""
        url = f"{self.base_url}/api/tags"
        try:
            r = httpx.get(url, timeout=2.0)
            print(f"[BACKEND_OK] url={url} status={r.status_code}")
            return r.status_code == 200
        except Exception as e:
            print(f"[BACKEND_ERR] url={url} EXC={type(e).__name__}: {repr(e)}")
            if getattr(e, '__context__', None):
                print(f"  __context__: {e.__context__}")
            if getattr(e, '__cause__', None):
                print(f"  __cause__: {e.__cause__}")
            return False

    # ---- Memory Operations ----

    def archive_and_wipe_memory(self) -> Path:
        """
        Archive on-disk memory + current in-memory state into a timestamped txt file,
        then wipe both. Returns the archive path.
        """
        ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        backup_dir = self.memory_path.parent / "MEMORY_BACKUP"
        backup_dir.mkdir(parents=True, exist_ok=True)

        archive_name = f"DorisTutor_Archived_MemoryWipe_{ts}.txt"
        archive_path = backup_dir / archive_name

        disk_text = ""
        if self.memory_path.exists():
            try:
                disk_text = self.memory_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                disk_text = "[ERROR] Could not read memory file.\n"

        # Best-effort human-readable dump of in-memory history
        mem_lines: list[str] = []
        for m in getattr(self, "history", []):
            role = getattr(m, "type", None) or getattr(m, "role", None) or m.__class__.__name__
            content = getattr(m, "content", None)
            if content is None:
                content = str(m)
            mem_lines.append(f"{role}: {content}")

        mem_text = "\n".join(mem_lines).strip()

        archive_body = (
            f"=== Doris Tutor Memory Wipe Archive ===\n"
            f"Timestamp: {ts}\n"
            f"Memory file: {self.memory_path}\n\n"
            f"--- On-disk memory (raw) ---\n"
            f"{disk_text}\n\n"
            f"--- In-memory history (best effort) ---\n"
            f"{mem_text}\n"
        )

        archive_path.write_text(archive_body, encoding="utf-8")

        # Wipe disk + RAM
        try:
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
            self.memory_path.write_text("", encoding="utf-8")
        except Exception:
            pass

        if hasattr(self, "history"):
            self.history.clear()

        return archive_path
    
    # ---- TTS Operations ----

    def get_last_tts_wavs(self) -> list[str]:
        return list(self.last_tts_wavs)

    def clear_last_tts(self) -> None:
        self.last_tts_wavs.clear()
        self.last_tts_idx = 0

    def synthesize_text_to_wav(self, text: str) -> Path:
        """
        High-level TTS entry point used by UI.
        Returns a filesystem path to a WAV file.
        """
        if not hasattr(self, "last_tts_wavs"):
            self.last_tts_wavs = []
            self.last_tts_idx = 0

        wav_path = self.tts.synthesize(text)
        self.last_tts_wavs.append(str(wav_path))
        return wav_path

    # ---- Core Logic ----

    def send(self, text: str) -> str:
        """
        Send user message to LLM and return text response.
        Updates history and persists turn.
        """
        text = text.strip()
        if not text:
            return ""

        self.history.append(HumanMessage(content=text))
        append_turn(self.memory_path, "user", text)

        print(f"[SEND] attempting generation. base_url={self.base_url!r}")

        # Retry logic: Try twice.
        max_retries = 1
        reply = None # scope init
        
        for attempt in range(max_retries + 1):
            try:
                with exclusive_execution("llm"):
                    reply = self.llm.invoke(self.history)
                break
            except Exception as e:
                print(f"[SEND_ERR] attempt={attempt+1} error={e}")
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                raise

        content = reply.content

        # Handle LangChain content list
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text", "")))
                else:
                    parts.append(str(item))
            content = "".join(parts).strip()
        else:
            content = str(content).strip()

        self.history.append(AIMessage(content=content))
        append_turn(self.memory_path, "assistant", content)
        return content


# ---- CLI Helper ----

def main() -> None:
    user = input("Welcome, user, please enter a user-name: ").strip() or "Sir and/or Ma'am"
    engine = ChatEngine(user_name=user)

    print("\nType your message. Type /quit to exit.\n")
    while True:
        text = input(f"{user} >> ").strip()
        if not text:
            continue
        if text.lower() in {"/quit", "/exit"}:
            break

        out = engine.send(text)
        print(f"Doris >> {out}\n")


if __name__ == "__main__":
    main()

# ---- Invariants Check ----
# SAFETY: CPU limits applied at top.
# ENGINE: ChatEngine parameters matching.
# IO: JSONL paths preserved.
