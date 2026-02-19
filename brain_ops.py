from core.core_drivers import \
    apply_cpu_limits  ##  SAFETY MEASURE, DO NOT REMOVE OR CHANGE THE POSITION OF THIS LINE  ##
from core.core_lock import exclusive_execution

apply_cpu_limits()  ##  SAFETY MEASURE, DO NOT REMOVE OR CHANGE THE POSITION OF THIS LINE  ##
#############################################################################################################################
"""
Doris Tutor - Brain Operations
Core logic for Chat Engine, Memory, and TTS integration.
"""

# ---- Imports ----

# Standard Library
import os
import re
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



##  ##                                                      ##  ##  RAG Trigger Rules  ##  ##
# High-density technical tokens to force RAG lookup
# These lists define which keywords trigger the "Ancient Holocron" lookup.
RAG_TRIGGER_RULES = {
    "LEGACY": [
        "holocron", "documents", "my notes", "search", "it notes", "jedi", "python", "code", "rag"
    ],
    "FRAMEWORKS": [
        "NIST SP 800-61", "NIST AI RMF", "ISO/IEC 42001", "CMMC", "DFARS", "MITRE ATT&CK",
        "NIST"  # Short form
    ],
    "EXAMS": [
        "SY0-701", "CompTIA A+", "Cisco CCNA",
        "CompTIA"
    ],
    "PROTOCOLS": [
        "TCP/UDP", "APIPA", "DHCP", "S/MIME", "IMAP", "POP3", "RCE", "SQLi", "XSS",
        "TCP", "UDP"
    ],
    "AI_RAG": [
        "BM25", "HyDE", "RRF", "GraphRAG", "CRAG"
    ],
    "SOURCES": [
        "Coursera", "Per Scholas"
    ]
}


def should_trigger_rag(text: str) -> bool:
    """
    Determines if the input text should trigger a RAG lookup based on
    technical keywords, case sensitivity rules, and word boundaries.
    Affects: Whether the system queries the local vector DB or uses pure LLM.
    """
    
    # 1. LEGACY: Case-insensitive, word boundary check
    for kw in RAG_TRIGGER_RULES["LEGACY"]:
        if re.search(r'\b' + re.escape(kw) + r'\b', text, re.IGNORECASE):
            return True

    # 2. TECHNICAL: Strict Rules
    # "Treat tokens with 3+ uppercase letters as 'Case-Sensitive Exact Matches'"
    
    all_tech_tokens = (
        RAG_TRIGGER_RULES["FRAMEWORKS"] +
        RAG_TRIGGER_RULES["EXAMS"] +
        RAG_TRIGGER_RULES["PROTOCOLS"] +
        RAG_TRIGGER_RULES["AI_RAG"] +
        RAG_TRIGGER_RULES["SOURCES"] 
    )

    for token in all_tech_tokens:
        # Check for 3+ uppercase letters
        upper_count = sum(1 for c in token if c.isupper())
        
        pattern = r'\b' + re.escape(token) + r'\b'
        
        if upper_count >= 3:
            # Case-Sensitive specific match
            if re.search(pattern, text): # Default is case-sensitive in re
                return True
        else:
            # Case-Insensitive (Standard)
            if re.search(pattern, text, re.IGNORECASE):
                return True
                
    return False


##  ##                                                      ##  ##  Holocron API Client  ##  ##
def ask_the_holocron(question: str) -> str:
    """
    Queries the local Ancient_Holocron API.
    This routes the user's question to the separate RAG service running on port 8000.
    """
    # Informative log for tracking RAG requests
    print(f"[*] Accessing Holocron for: {question}")
    try:
        with httpx.Client(timeout=30.0) as client:
            # Post the question to the RAG endpoint
            response = client.post(
                "http://localhost:8000/query",
                json={"question": question}
            )
            response.raise_for_status()
            
            # Extract answer from JSON response
            return response.json().get("answer", "The Holocron is silent.")
    except Exception as e:
        # Return error as string so it's spoken/shown to user
        return f"[Holocron Error] {e}"


##  ##                                                      ##  ##  Main Chat Controller  ##  ##
@dataclass
class ChatEngine:
    """
    Main controller for LLM interaction, Memory management, and TTS synthesis.
    Manages the conversation history (context) and interfaces with Ollama and GhostVoice.
    """
    # Config
    user_name: str = "Dave"
    model_name: str = "llama3.2:1b"
    base_url: str = "http://127.0.0.1:11434"
    memory_path: Path = Path("data/chat.jsonl")
    tts_enabled: bool = True
    temperature: float = 0.15
    num_ctx: int = 12288
    num_predict: int = 1024
    timeout: int = 90
    keep_alive: str = "30m"

    # Internal State (init=False)
    tts: GhostVoiceEngine = field(init=False)
    llm: ChatOllama = field(init=False)
    history: List[BaseMessage] = field(default_factory=list, init=False)
    last_tts_wavs: list[str] = field(default_factory=list, init=False)
    last_tts_idx: int = field(default=0, init=False)
    summary: str = field(default="", init=False)
    _summarizing: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        """Initialize LLM, TTS backend, and load memory."""
        # Informative but short: Prints the engine configuration for debugging context.
        print(
            f"[ENGINE] file={__file__} cwd={os.getcwd()} model={self.model_name} "
            f"base_url={self.base_url} keep_alive={self.keep_alive} "
            f"num_ctx={self.num_ctx} num_predict={self.num_predict}"
        )

        # 1. Setup LLM
        # Connects to the local Ollama instance
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
        # Configures the Piper TTS engine using paths from tts_config.py
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
        # Loads the persona and previous conversation turns
        persona_path = Path(__file__).parent / "core" / "core_persona.md"
        if persona_path.exists():
            persona_text = persona_path.read_text(encoding="utf-8").strip()
            persona_text += f"\n\nUser Context:\nThe user's name is {self.user_name}"
        else:
            persona_text = (
                f"You are Doris, a life-long teacher. The user's name is {self.user_name}"
            )

        system_msg = SystemMessage(content=persona_text)
        self.history = [system_msg]

        # Initialize memory file if it doesn't exist
        if not self.memory_path.exists():
            append_turn(self.memory_path, "system", system_msg.content)

        # Rehydrate history from disk
        for t in load_turns(self.memory_path, limit=200):
            role = t.get("role")
            content = (t.get("content") or "").strip()
            if not content: continue
            if role == "user":
                self.history.append(HumanMessage(content=content))
            elif role == "assistant":
                self.history.append(AIMessage(content=content))

    def backend_ok(self) -> bool:
        """Check if Ollama backend is reachable."""
        url = f"{self.base_url}/api/tags"
        try:
            r = httpx.get(url, timeout=2.0)
            return r.status_code == 200
        except Exception:
            return False

    def send(self, text: str) -> str:
        """
        Process a user message and generate a reply.
        Routes to RAG if triggers are matched, otherwise uses standard LLM.
        """
        text = text.strip()
        if not text:
            return ""

        self.history.append(HumanMessage(content=text))
        append_turn(self.memory_path, "user", text)

        # Informative check: Decides if we need external knowledge
        if should_trigger_rag(text):
            # RAG Path: Query Holocron
            rag_response = ask_the_holocron(text)
            self.history.append(AIMessage(content=rag_response))
            append_turn(self.memory_path, "assistant", rag_response)
            return rag_response

        # Fallback to LLM
        # Informative log: Showing we are falling back to general generation
        print(f"[SEND] attempting generation. base_url={self.base_url!r}")
        max_retries = 1
        reply = None

        for attempt in range(max_retries + 1):
            try:
                with exclusive_execution("llm"):
                    reply = self.llm.invoke(self.history)
                break
            except Exception as e:
                print(f"[SEND_ERR] attempt={attempt + 1} error={e}")
                if attempt < max_retries:
                    time.sleep(0.5)
                    continue
                raise

        content = str(reply.content).strip()
        self.history.append(AIMessage(content=content))
        append_turn(self.memory_path, "assistant", content)
        
        # Check for summarization trigger
        if len(self.history) > 15: # Arbitrary threshold for raw turns
            self.summarize_history()
            
        return content

    def summarize_history(self) -> None:
        """
        Compresses the middle of the history into a summary.
        Keeps the persona/system message and the last 4 turns raw.
        """
        if self._summarizing:
            return
            
        print("[ENGINE] Summarizing long history...")
        if len(self.history) <= 6:
            return
            
        self._summarizing = True
        try:
            # Keep system message (0) and last 4 turns
            keep_last = 4
            raw_tail = self.history[-keep_last:]
            to_summarize = self.history[1:-keep_last]
            
            # Build a prompt for summarization
            # Using the same LLM for summarization (llama3.2:1b is fast)
            prompt = (
                "Summarize the following conversation history concisely, "
                "focusing on key facts and user preferences. "
                "Keep the summary under 100 words.\n\n"
            )
            for msg in to_summarize:
                role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                prompt += f"{role}: {msg.content}\n"

            with exclusive_execution("llm"):
                summary_reply = self.llm.invoke([SystemMessage(content="You are a helpful assistant."), HumanMessage(content=prompt)])
                new_summary = str(summary_reply.content).strip()
                
                # Update rolling summary
                self.summary = new_summary
                
                # Reconstruct history: System + Summary + Raw Tail
                # We update the system prompt or add a summary message
                new_history = [self.history[0]]
                new_history.append(SystemMessage(content=f"Context Summary of previous turns: {self.summary}"))
                new_history.extend(raw_tail)
                
                self.history = new_history
                print(f"[ENGINE] History compressed. New count: {len(self.history)}")
        except Exception as e:
            print(f"[SUMMARIZE_ERR] {e}")
        finally:
            self._summarizing = False


    def stream_send(self, text: str):
        """
        Generator that yields tokens from the LLM in real-time.
        Handles RAG routing and history management internally.
        """
        text = text.strip()
        if not text:
            return

        self.history.append(HumanMessage(content=text))
        append_turn(self.memory_path, "user", text)

        # RAG Check
        if should_trigger_rag(text):
            rag_response = ask_the_holocron(text)
            self.history.append(AIMessage(content=rag_response))
            append_turn(self.memory_path, "assistant", rag_response)
            # Emit in one go for RAG (it's not natively streaming tokens here usually)
            yield rag_response
            return

        # LLM Stream Path
        full_reply = ""
        try:
            with exclusive_execution("llm"):
                for chunk in self.llm.stream(self.history):
                    token = str(chunk.content)
                    full_reply += token
                    yield token
        except Exception as e:
            print(f"[STREAM_ERR] {e}")
            raise

        # Save to history AFTER completion
        if full_reply.strip():
            self.history.append(AIMessage(content=full_reply.strip()))
            append_turn(self.memory_path, "assistant", full_reply.strip())
            
            # Check for summarization trigger
            if len(self.history) > 15:
                self.summarize_history()



    def clear_active_memory(self) -> None:
        """
        Clears the in-memory history and wipes the chat.jsonl file.
        Resets to just the SystemMessage.
        """
        # 1. Reset in-memory
        if self.history:
             # Keep the system prompt (first item)
            self.history = [self.history[0]]
        
        # 2. Wipe disk file
        if self.memory_path.exists():
            # Truncate
            with open(self.memory_path, "w", encoding="utf-8") as f:
                pass
            # Re-write system prompt
            if self.history:
                msg = self.history[0]
                if isinstance(msg, SystemMessage):
                    append_turn(self.memory_path, "system", msg.content)


##  ##                                                      ##  ##  CLI Entry Point  ##  ##
def main() -> None:
    user = input("Enter name: ").strip() or "Sir"
    engine = ChatEngine(user_name=user)
    while True:
        text = input(f"{user} >> ").strip()
        if text.lower() in {"/quit", "/exit"}: break
        print(f"Doris >> {engine.send(text)}\n")


if __name__ == "__main__":
    main()