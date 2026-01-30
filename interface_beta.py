import sys, time
from pathlib import Path
from brain_ops import ChatEngine
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QUrl, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QListWidget,
    QLabel, QFrame, QCheckBox, QStatusBar
)

# -----------------------------
# Worker threads
# -----------------------------

class Worker(QThread):
    done = pyqtSignal(str)
    err = pyqtSignal(str)

    def __init__(self, engine: ChatEngine, text: str):
        super().__init__()
        self.engine = engine
        self.text = text

    def run(self) -> None:
        try:
            reply = self.engine.send(self.text)
            self.done.emit(reply)
        except Exception as e:
            self.err.emit(str(e))


class TTSWorker(QThread):
    done = pyqtSignal(str)
    err = pyqtSignal(str)

    def __init__(self, engine: ChatEngine, text: str):
        super().__init__()
        self.engine = engine
        self.text = text

    def run(self) -> None:
        try:
            wav = self.engine.synthesize_text_to_wav(self.text)
            self.done.emit(str(wav))
        except Exception as e:
            self.err.emit(str(e))


# -----------------------------
# UI helpers
# -----------------------------

def _panel_frame() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.StyledPanel)
    f.setFrameShadow(QFrame.Shadow.Raised)
    return f


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    app = QApplication(sys.argv)

    # Window
    win = QWidget()
    win.setWindowTitle("🧑‍🏫 Doris — Tutor Console (Beta)")
    win.resize(1100, 650)

    root = QVBoxLayout(win)
    row = QHBoxLayout()
    root.addLayout(row, stretch=1)

    # ---------------- LEFT PANEL ----------------
    left = _panel_frame()
    left_layout = QVBoxLayout(left)

    history_controls = _panel_frame()
    hc = QHBoxLayout(history_controls)
    btn_exit = QPushButton("Exit")
    btn_new_chat = QPushButton("New Chat")
    btn_clear_memory = QPushButton("Clear Memory")
    hc.addWidget(btn_exit)
    hc.addWidget(btn_new_chat)
    hc.addWidget(btn_clear_memory)
    left_layout.addWidget(history_controls)

    history_list = QListWidget()
    history_list.addItem("Session 1 (placeholder)")
    left_layout.addWidget(history_list, stretch=1)

    tts_row = _panel_frame()
    tr = QHBoxLayout(tts_row)
    chk_speak = QCheckBox("Speak replies")
    btn_speak_now = QPushButton("Speak last")
    btn_play = QPushButton("Play")
    btn_stop = QPushButton("Stop")
    btn_speak_now.setEnabled(False)
    btn_play.setEnabled(False)
    btn_stop.setEnabled(False)

    tr.addWidget(chk_speak)
    tr.addStretch(1)
    tr.addWidget(btn_speak_now)
    tr.addWidget(btn_play)
    tr.addWidget(btn_stop)
    left_layout.addWidget(tts_row)

    portrait_frame = _panel_frame()
    pf = QVBoxLayout(portrait_frame)
    portrait = QLabel("AI Portrait\n(placeholder)")
    portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
    portrait.setMinimumHeight(220)
    pf.addWidget(portrait)
    left_layout.addWidget(portrait_frame)

    # ---------------- RIGHT PANEL ----------------
    right = _panel_frame()
    right_layout = QVBoxLayout(right)

    chat_out = QTextEdit()
    chat_out.setReadOnly(True)
    right_layout.addWidget(chat_out, stretch=1)

    input_row = QHBoxLayout()
    chat_in = QLineEdit()
    chat_in.setPlaceholderText("Type here…")
    send_btn = QPushButton("Send")
    input_row.addWidget(chat_in, stretch=1)
    input_row.addWidget(send_btn)
    right_layout.addLayout(input_row)

    row.addWidget(left, stretch=1)
    row.addWidget(right, stretch=2)

    status = QStatusBar()
    status.showMessage("Ready")
    root.addWidget(status)

    # ---------------- ENGINE ----------------
    engine = ChatEngine(user_name="Dave")

    # Keep thread references alive (prevents QThread GC crash)
    active_threads: list[QThread] = []
    last_reply = {"text": ""}
    last_tts = {"wav": ""}

    # ---------------- AUDIO ----------------
    sfx = QSoundEffect()
    sfx.setLoopCount(1)
    sfx.setVolume(0.9)

    # ---------------- HANDLERS ----------------

    def on_send() -> None:
        text = chat_in.text().strip()
        if not text:
            return
        if text.lower() in {"/quit", "/exit"}:
            win.close()
            return

        chat_out.append(f"You: {text}")
        chat_in.clear()
        chat_out.append("Doris: ...\n")

        send_btn.setEnabled(False)
        chat_in.setEnabled(False)

        worker = Worker(engine, text)
        active_threads.append(worker)

        def _cleanup() -> None:
            if worker in active_threads:
                active_threads.remove(worker)
            worker.deleteLater()

        def on_done(reply: str) -> None:
            chat_out.append(f"Doris: {reply}\n")
            last_reply["text"] = reply.strip()
            btn_speak_now.setEnabled(bool(last_reply["text"]))
            send_btn.setEnabled(True)
            chat_in.setEnabled(True)
            chat_in.setFocus()
            _cleanup()

        def on_err(msg: str) -> None:
            chat_out.append(f"[BACKEND ERROR] {msg}\n")
            status.showMessage(msg)
            send_btn.setEnabled(True)
            chat_in.setEnabled(True)
            chat_in.setFocus()
            _cleanup()

        worker.done.connect(on_done)
        worker.err.connect(on_err)
        worker.start()

    def on_speak_last() -> None:
        text = last_reply["text"]
        if not text:
            return

        worker = TTSWorker(engine, text)
        active_threads.append(worker)

        def _cleanup() -> None:
            if worker in active_threads:
                active_threads.remove(worker)
            worker.deleteLater()

        def on_done(wav: str) -> None:
            last_tts["wav"] = wav
            btn_play.setEnabled(True)
            btn_stop.setEnabled(True)
            status.showMessage("TTS ready")
            _cleanup()

        def on_err(msg: str) -> None:
            chat_out.append(f"[TTS ERROR] {msg}\n")
            status.showMessage(msg)
            _cleanup()

        worker.done.connect(on_done)
        worker.err.connect(on_err)
        worker.start()

    def on_play() -> None:
        wav = last_tts["wav"]
        if not wav:
            return
        p = Path(wav)
        if not p.exists():
            status.showMessage("Missing WAV")
            return
        sfx.setSource(QUrl.fromLocalFile(str(p)))
        sfx.play()

    def _shutdown_threads() -> None:
        # Wait a moment for any in-flight threads to finish to avoid SIGABRT
        for t in list(active_threads):
            t.wait(3000)

    app.aboutToQuit.connect(_shutdown_threads)

    def on_stop() -> None:
        sfx.stop()

    # ---------------- WIRING ----------------
    send_btn.clicked.connect(on_send)
    chat_in.returnPressed.connect(on_send)
    btn_exit.clicked.connect(win.close)
    btn_speak_now.clicked.connect(on_speak_last)
    btn_play.clicked.connect(on_play)
    btn_stop.clicked.connect(on_stop)

    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
