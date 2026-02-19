import sys
from brain_ops import ChatEngine
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QCheckBox
)


class Worker(QThread):
    done = pyqtSignal(str)

    def __init__(self, engine: ChatEngine, text: str):
        super().__init__()
        self.engine = engine
        self.text = text

    def run(self) -> None:
        reply = self.engine.send(self.text)
        self.done.emit(reply)


class TTSWorker(QThread):
    done = pyqtSignal(str)
    err = pyqtSignal(str)

    def __init__(self, engine: ChatEngine, text: str):
        super().__init__()
        self.engine = engine
        self.text = text

    def run(self) -> None:
        try:
            wav_path = self.engine.synthesize_text_to_wav(self.text)
            self.done.emit(str(wav_path))
        except Exception as e:
            self.err.emit(str(e))


def main() -> None:
    app = QApplication(sys.argv)

    win = QWidget()
    win.setWindowTitle("🧑‍🏫 Doris — Gamma")

    layout = QVBoxLayout(win)

    chat_out = QTextEdit()
    chat_out.setReadOnly(True)
    layout.addWidget(chat_out)

    # --- TTS controls (explicit only)
    tts_row = QHBoxLayout()

    chk_speak = QCheckBox("Speak replies")
    chk_speak.setChecked(False)
    chk_speak.setEnabled(False)   # autoplay later

    btn_speak_now = QPushButton("Speak last")
    btn_speak_now.setEnabled(False)

    btn_stop = QPushButton("Stop")
    btn_stop.setEnabled(False)    # playback later

    tts_row.addWidget(chk_speak)
    tts_row.addStretch(1)
    tts_row.addWidget(btn_speak_now)
    tts_row.addWidget(btn_stop)

    layout.addLayout(tts_row)

    # --- Input row
    row = QHBoxLayout()
    chat_in = QLineEdit()
    send_btn = QPushButton("Send")
    row.addWidget(chat_in)
    row.addWidget(send_btn)
    layout.addLayout(row)

    # --- Theme
    chat_out.setStyleSheet("background-color: #000; color: #fff;")
    chat_in.setStyleSheet("background-color: #000; color: #fff;")
    send_btn.setStyleSheet("background-color: #222; color: #fff;")

    engine = ChatEngine(user_name="Dave")
    worker_ref = {"worker": None}
    tts_ref = {"worker": None}
    last_reply = {"text": ""}

    def on_send() -> None:
        text = chat_in.text().strip()
        if not text:
            return
        if text.lower() in {"/quit", "/exit"}:
            win.close()
            return

        chat_out.append(f"You: {text}")
        chat_in.clear()

        send_btn.setEnabled(False)
        chat_in.setEnabled(False)
        chat_out.append("Doris: ...\n")

        worker = Worker(engine, text)
        worker_ref["worker"] = worker

        def on_done(reply: str) -> None:
            chat_out.append(f"Doris: {reply}\n")
            last_reply["text"] = reply.strip()
            btn_speak_now.setEnabled(bool(last_reply["text"]))
            send_btn.setEnabled(True)
            chat_in.setEnabled(True)
            chat_in.setFocus()

        worker.done.connect(on_done)
        worker.start()

    def on_speak_last() -> None:
        text = last_reply["text"].strip()
        if not text:
            return

        send_btn.setEnabled(False)
        chat_in.setEnabled(False)
        btn_speak_now.setEnabled(False)

        chat_out.append("TTS: generating WAV...\n")

        worker = TTSWorker(engine, text)
        tts_ref["worker"] = worker

        def on_tts_done(wav_path: str) -> None:
            chat_out.append(f"TTS: WAV saved: {wav_path}\n")
            send_btn.setEnabled(True)
            chat_in.setEnabled(True)
            btn_speak_now.setEnabled(True)
            chat_in.setFocus()

        def on_tts_err(msg: str) -> None:
            chat_out.append(f"TTS error: {msg}\n")
            send_btn.setEnabled(True)
            chat_in.setEnabled(True)
            btn_speak_now.setEnabled(True)

        worker.done.connect(on_tts_done)
        worker.err.connect(on_tts_err)
        worker.start()

    send_btn.clicked.connect(on_send)
    chat_in.returnPressed.connect(on_send)
    btn_speak_now.clicked.connect(on_speak_last)

    win.resize(640, 520)
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
