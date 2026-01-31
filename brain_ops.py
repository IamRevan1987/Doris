from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from tts.tts_config import piper_bin_path, voice_model_path, tts_out_dir
from tts.ghost_voice import GhostVoiceConfig, GhostVoiceEngine
from core_memories import load_turns, append_turn
from dataclasses import dataclass, field
from langchain_ollama import ChatOllama
from pathlib import Path
from typing import List
import httpx
import os


@dataclass
class ChatEngine:
    user_name: str = "David"
    model_name: str = "ministral-3:3b"
    base_url: str = "http://127.0.0.1:11434"
    memory_path: Path = Path("data/chat.jsonl")
    tts_enabled: bool = True           # This will turn off all TTS
    tts: GhostVoiceEngine = field(init = False)
    temperature: float = 0.15
    num_ctx: int = 12288
    num_predict: int = 256
    timeout: int = 90
    keep_alive: str = "30m"

    llm: ChatOllama = field(init=False)
    history: List[BaseMessage] = field(default_factory = list, init = False)

    def backend_ok(self) -> bool:
        url = f"{self.base_url}/api/tags"
        try:
            r = httpx.get(url, timeout=2.0)
            print(f"[BACKEND_OK] url={url} status={r.status_code}")
            return r.status_code == 200
        except Exception as e:
            # repr(e) gives a cleaner string for some connection errors
            print(f"[BACKEND_ERR] url={url} EXC={type(e).__name__}: {repr(e)}")
            if getattr(e, '__context__', None):
                print(f"  __context__: {e.__context__}")
            if getattr(e, '__cause__', None):
                print(f"  __cause__: {e.__cause__}")
            return False

    def __post_init__(self) -> None:
        print(
            f"[ENGINE] file={__file__} cwd={os.getcwd()} model={self.model_name} "
            f"base_url={self.base_url} keep_alive={self.keep_alive} "
            f"num_ctx={self.num_ctx} num_predict={self.num_predict}"
        )

        self.llm = ChatOllama(
            model = self.model_name,
            base_url = self.base_url,
            temperature = self.temperature,
            num_ctx = self.num_ctx,
            num_predict = self.num_predict,
            keep_alive = self.keep_alive,
            timeout = self.timeout,
        )
        cfg = GhostVoiceConfig(
            enabled = self.tts_enabled,
            piper_binary = piper_bin_path(),
            model_path = voice_model_path(),
            output_dir = tts_out_dir(),
        )
        self.tts = GhostVoiceEngine(cfg)

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

    def synthesize_text_to_wav(self, text: str) -> Path:
        """
        Explicit TTS call.
        No autoplay. UI will decide when to call this.
        """
        if not self.tts_enabled:
            raise RuntimeError("TTS is disabled (tts_enabled = False).")
        return self.tts.synthesize(text, filename_stem="reply")

    def send(self, text: str) -> str:
        text = text.strip()
        if not text:
            return ""

        self.history.append(HumanMessage(content = text))
        append_turn(self.memory_path, "user", text)

        print(f"[SEND] attempting generation. base_url={self.base_url!r}")

        # Retry logic: Try twice.
        max_retries = 1
        for attempt in range(max_retries + 1):
            try:
                reply = self.llm.invoke(self.history)
                break
            except Exception as e:
                print(f"[SEND_ERR] attempt={attempt+1} error={e}")
                if attempt < max_retries:
                    import time
                    time.sleep(0.5)
                    continue
                # If we're out of retries, re-raise the last exception
                raise

        self.history.append(AIMessage(content = reply.content))
        append_turn(self.memory_path, "assistant", reply.content)
        return reply.content

def main() -> None:
    user = input("Welcome, user, please enter a user-name: ").strip() or "Sir and/or Ma'am"
    engine = ChatEngine(user_name = user)
    worker_ref = {"worker": None}

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
