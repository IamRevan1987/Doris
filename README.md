# Doris — AI Tutor Companion (v0.3.1)

Doris is a high-performance, local-first AI tutor designed to provide near-instant, conversational educational support. By combining real-time LLM streaming with a persistent TTS pipeline and RAG-enhanced knowledge retrieval, Doris creates a seamless interaction layer for students and researchers.

---

## 🚀 Overview

Doris isn't just a chatbot; it's a **Tutor Console** built for low-latency feedback. It operates primarily on-device, leveraging local LLMs (Ollama) and lightweight TTS (Piper) to ensure your data stays private and your interactions remain fluid. 

Whether you're exploring complex technical topics or reviewing personal notes, Doris provides a modular environment that balances reasoning speed with depth of knowledge.

---

## ✨ Key Features

- **Real-Time Token Streaming**: Watch as the AI's thoughts appear instantly on your screen, powered by a streaming-first backend.
- **Persistent TTS Pipeline**: Features a low-latency "GhostVoice" engine using Piper TTS. Doris starts speaking as soon as the first sentence is complete.
- **Granular Audio Control**:
  - **Volume**: 0–100% normalized control.
  - **Speed Snapping**: 10 discrete speed levels (0.25x to 2.5x) with snapping logic for a clean UX.
- **Local-First RAG (Ancient Holocron)**: Seamlessly retrieves context from your local knowledge base using a dedicated RAG API.
- **Session Management**: Automatically saves and loads conversation history, allowing for continuous learning across sessions.
- **Theme Support**: Includes a refined Dark Mode optimized for long tutoring sessions.

---

## 🏗 Architecture

Doris is built with a modular, decoupled architecture to ensure stability and performance:

- **Frontend (UI Layer)**: Developed with **PyQt6**, managing the event loop and real-time UI updates.
- **Orchestrator (Brain Ops)**: Manages the integration between the LLM, Memory, and TTS systems.
- **LLM Engine**: Uses **ChatOllama** via LangChain to interface with local models (default: `llama3.2:1b`).
- **TTS Engine (Persistent Piper)**: A standalone subprocess-managed synthesis pipeline that maintains a live Piper process for immediate audio generation.
- **Retrieval Layer**: Connects via `httpx` to the **Ancient Holocron API** (running on port 8000) for vectorless or semantic retrieval.

---

## 🔍 How RAG Works in Doris

**Retrieval-Augmented Generation (RAG)** is the bridge between the AI’s general reasoning and your specific expertise. 

1. **Triggering**: When you mention technical keywords or specific documents, Doris triggers the "Ancient Holocron."
2. **Retrieval**: The system queries your local knowledge base for relevant snippets.
3. **Augmentation**: The context is injected into the AI's current window, allowing it to answer with high precision based on your actual data.
4. **Depth vs. Reasoning**: RAG provides the *facts*, while the LLM provides the *logic*. This split ensures that Doris remains fast for chat while becoming "instant-smart" on your personal documentation when needed.

---

## 🛠 Installation

### Prerequisites
- Python 3.12+
- [Ollama](https://ollama.com/) (running `llama3.2:1b` or similar)
- [Piper TTS](https://github.com/rhasspy/piper) (Must be available in your system path or `tts/` directory)

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/YourUsername/Doris.git
   cd Doris
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
   *(Or use `uv sync` if using the uv package manager)*

3. Configure Paths:
   Ensure `tts/tts_config.py` points to your local Piper binary and voice models.

---

## 📂 Project Structure

- `main.py`: Entry point for the application.
- `interface_beta.py`: Primary GUI and event handling logic.
- `brain_ops.py`: Core logic for LLM streaming and RAG routing.
- `session_manager.py`: Handles saving/loading conversation history to `.jsonl` files.
- `tts/`: Contains the `GhostVoice` engine and Piper configuration.
- `core/`: Driver management and thread locking utilities.

---

## 🚦 Usage

Launch Doris from the root directory:
```bash
python main.py
```

### Tips for User:
- Use the **Volume** and **Speed** sliders to fine-tune your listening experience.
- Use **"New Chat"** to archive the current session and start fresh.
- Trigger RAG by asking about specific topics in your Library (e.g., "Tell me about my Python notes").

---

## 🛣 Future Roadmap

- [ ] Advanced Semantic RAG with vector-store support.
- [ ] On-the-fly model switching between vision and language models.
- [ ] Adaptive UI layouts for mobile/tablet companion use.

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
