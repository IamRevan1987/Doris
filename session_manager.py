import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

SESSION_DIR = Path("data/sessions")

def ensure_session_dir() -> None:
    """Ensures the session directory exists."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)

def save_session(history: List[BaseMessage]) -> str:
    """
    Saves the current conversation history to a JSON file.
    Returns the filename of the saved session.
    """
    ensure_session_dir()
    
    # Filter out empty system messages or irrelevant ones if needed
    # For now, we save everything to preserve context.
    
    messages = []
    for msg in history:
        role = ""
        if isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        elif isinstance(msg, SystemMessage):
            role = "system"
        else:
            continue
            
        messages.append({
            "role": role,
            "content": msg.content
        })
    
    if not messages:
        return ""

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"session_{timestamp}.json"
    filepath = SESSION_DIR / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)
        
    return filename

def load_session(filename: str) -> List[BaseMessage]:
    """
    Loads a session from a JSON file and returns a list of LangChain messages.
    """
    filepath = SESSION_DIR / filename
    if not filepath.exists():
        return []
        
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    history = []
    for msg in data:
        role = msg.get("role")
        content = msg.get("content")
        
        if role == "user":
            history.append(HumanMessage(content=content))
        elif role == "assistant":
            history.append(AIMessage(content=content))
        elif role == "system":
            history.append(SystemMessage(content=content))
            
    return history

def list_sessions() -> List[str]:
    """
    Returns a list of session filenames, sorted by modification time (newest first).
    """
    ensure_session_dir()
    files = list(SESSION_DIR.glob("session_*.json"))
    # Sort by modification time, newest first
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return [f.name for f in files]

def delete_all_sessions() -> None:
    """
    Deletes all session files in the session directory.
    """
    ensure_session_dir()
    for f in SESSION_DIR.glob("session_*.json"):
        try:
            f.unlink()
        except OSError as e:
            print(f"Error deleting {f}: {e}")
