import sys, time
from pathlib import Path
from brain_ops import ChatEngine
from core.core_tts_rules import chunk_for_tts
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QUrl, QTimer, QObject, QEvent
from PyQt6.QtGui import QPixmap, QAction
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QMainWindow,
    QTextEdit, QLineEdit, QPushButton, QListWidget,
    QLabel, QFrame, QCheckBox, QStatusBar, QMessageBox
)

# ---- Theme (temporary, simple; replace later with full color controls) ----

DARK_QSS = """
QWidget {
    background: #121212;
    color: #EAEAEA;
}
QTextEdit, QLineEdit, QListWidget {
    background: #1E1E1E;
    color: #EAEAEA;
    border: 1px solid #2A2A2A;
    border-radius: 6px;
}
QPushButton {
    background: #232323;
    color: #EAEAEA;
    border: 1px solid #2A2A2A;
    border-radius: 6px;
    padding: 6px 10px;
}
QPushButton:disabled {
    color: #777777;
    background: #1A1A1A;
}
QCheckBox, QLabel {
    color: #EAEAEA;
}
QStatusBar {
    background: #121212;
    color: #BDBDBD;
}
"""

LIGHT_QSS = ""  # default Qt look for now


def apply_theme(app, dark: bool) -> None:
    # app is your QApplication
    app.setStyleSheet(DARK_QSS if dark else LIGHT_QSS)


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
    done = pyqtSignal(list)
    err = pyqtSignal(str)

    def __init__(self, engine: ChatEngine, text: str):
        super().__init__()
        self.engine = engine
        self.text = text

    def run(self) -> None:
        try:
            chunks = chunk_for_tts(self.text)
            wavs: list[str] = []
            for chunk in chunks:
                wav = self.engine.synthesize_text_to_wav(chunk)
                wavs.append(str(wav))
            self.done.emit(wavs)
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
    win = QMainWindow()
    apply_theme(app, True)

    win.setWindowTitle("🧑‍🏫 Doris — Tutor Console (Beta)")
    win.resize(1100, 650)

    central = QWidget()
    win.setCentralWidget(central)

    root = QVBoxLayout(central)
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
    btn_prev = QPushButton("◀")
    btn_next = QPushButton("▶")
    btn_prev.setEnabled(False)
    btn_next.setEnabled(False)
    btn_speak_now.setEnabled(False)
    btn_play.setEnabled(False)
    btn_stop.setEnabled(False)

    tr.addWidget(chk_speak)
    tr.addStretch(1)
    tr.addWidget(btn_speak_now)
    tr.addWidget(btn_prev)
    tr.addWidget(btn_play)
    tr.addWidget(btn_next)
    tr.addWidget(btn_stop)

    left_layout.addWidget(tts_row)

    portrait_frame = _panel_frame()
    pf = QVBoxLayout(portrait_frame)
    portrait = QLabel("AI Portrait\n(placeholder)")
    portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)



    ##  ##                                      ##  ## --- Portrait image ---
    img_path = Path(__file__).resolve().parent / "resources" / "Doris002_1.png"
    portrait_pixmap = None


    if img_path.exists():
        portrait_pixmap = QPixmap(str(img_path))
        portrait.setText("")
        portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
    else:
        portrait.setText(f"Missing:\n{img_path.name}")

    pf.addWidget(portrait)
    left_layout.addWidget(portrait_frame, stretch=1)

    def update_portrait() -> None:
        if portrait_pixmap is None:
            return
        size = portrait.size()
        portrait.setPixmap(
            portrait_pixmap.scaled(
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )

    class _ResizeFilter(QObject):
        def eventFilter(self, obj, event):
            if obj is portrait and event.type() == QEvent.Type.Resize:
                update_portrait()
            return super().eventFilter(obj, event)

    _resize_filter = _ResizeFilter(portrait)
    portrait.installEventFilter(_resize_filter)


    # hook resize AFTER update_portrait exists
    _old_resize = portrait.resizeEvent

    def _on_portrait_resize(event):
        update_portrait()
        if _old_resize:
            _old_resize(event)

    portrait.resizeEvent = _on_portrait_resize


    ##  ##                          ##  ## ---------------- RIGHT PANEL ----------------
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
    last_tts = {"wavs": [], "idx": 0}
    _tts_stop_flag = {"stopped": False}

    # ---------------- AUDIO ----------------
    sfx = QSoundEffect()
    sfx.setLoopCount(1)
    sfx.setVolume(0.9)

    ###   ###  ---------------- HANDLERS ----------------  ###   ###

    ##  ##                      Memory Handlers              ##  ##

    # ---- Menu: View -> Dark Mode ----
    view_menu = win.menuBar().addMenu("View")

    dark_mode_action = QAction("Dark Mode", win)
    dark_mode_action.setCheckable(True)
    dark_mode_action.setChecked(True)  # default to dark for now; change later if you want
    view_menu.addAction(dark_mode_action)

    # ---- Apply default theme ----
    apply_theme(app, True)

    # ---- Dark mode toggle handler ----
    def on_toggle_dark_mode(checked: bool) -> None:
        apply_theme(app, checked)

    dark_mode_action.toggled.connect(on_toggle_dark_mode)

    def on_clear_memory() -> None:
        # Confirm — no silent nukes
        res = QMessageBox.question(
            win,
            "Clear Memory (Archive + Wipe)",
            "This will archive your memory to a timestamped file, then wipe memory on disk and in RAM.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            status.showMessage("Clear Memory cancelled")
            return

        try:
            archive_path = engine.archive_and_wipe_memory()

            # Reset UI state
            chat_out.clear()
            last_reply["text"] = ""
            last_tts["wavs"] = []
            last_tts["idx"] = 0

            btn_speak_now.setEnabled(False)
            btn_play.setEnabled(False)
            btn_stop.setEnabled(False)

            status.showMessage(f"Memory archived + wiped: {archive_path.name}")
            chat_out.append(
                "[Memory archived + wiped]\n"
                f"Archive file: {archive_path.name}\n"
                f"Location: {archive_path.parent}\n"
            )

        except Exception as e:
            chat_out.append(f"[CLEAR MEMORY ERROR] {e}\n")
            status.showMessage("Clear Memory failed")

    def set_busy(is_busy: bool) -> None:
        btn_clear_memory.setEnabled(not is_busy)
        btn_new_chat.setEnabled(not is_busy)

    def on_new_chat() -> None:
        # Stop any current audio
        sfx.stop()

        # Reset in-memory conversation only (no disk wipe)
        try:
            engine.reset_conversation()
        except Exception:
            # If reset_conversation isn't present for some reason, fail soft
            if hasattr(engine, "history"):
                engine.history.clear()

        # Reset UI
        chat_out.clear()
        chat_in.clear()
        last_reply["text"] = ""
        last_tts["wavs"] = []
        last_tts["idx"] = 0
        btn_speak_now.setEnabled(False)
        btn_play.setEnabled(False)
        btn_stop.setEnabled(False)

        status.showMessage("New chat started")

    def _play_current_chunk() -> None:
        wavs = last_tts["wavs"]
        if not wavs:
            return

        idx = last_tts["idx"]
        idx = max(0, min(idx, len(wavs) - 1))
        last_tts["idx"] = idx

        p = Path(wavs[idx])
        if not p.exists():
            status.showMessage("Missing WAV")
            return

        sfx.setSource(QUrl.fromLocalFile(str(p)))
        sfx.play()
        _update_tts_nav_buttons()

    def _update_tts_nav_buttons() -> None:
        wavs = last_tts["wavs"]
        has = bool(wavs)
        btn_play.setEnabled(has)
        btn_stop.setEnabled(has)

        if not has:
            btn_prev.setEnabled(False)
            btn_next.setEnabled(False)
            return

        idx = last_tts["idx"]
        btn_prev.setEnabled(idx > 0)
        btn_next.setEnabled(idx < len(wavs) - 1)

    def on_prev() -> None:
        wavs = last_tts["wavs"]
        if not wavs:
            return
        last_tts["idx"] = max(0, last_tts["idx"] - 1)
        _tts_stop_flag["stopped"] = False
        _play_current_chunk()

    def on_next() -> None:
        wavs = last_tts["wavs"]
        if not wavs:
            return
        last_tts["idx"] = min(len(wavs) - 1, last_tts["idx"] + 1)
        _tts_stop_flag["stopped"] = False
        _play_current_chunk()

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
            set_busy(False)

        def on_done(reply: str) -> None:
            chat_out.append(f"Doris: {reply}\n")
            last_reply["text"] = reply.strip()
            btn_speak_now.setEnabled(bool(last_reply["text"]))
            send_btn.setEnabled(True)
            chat_in.setEnabled(True)
            chat_in.setFocus()
            chat_in.setFocus()
            
            if chk_speak.isChecked():
                on_speak_last()
            
            # _cleanup() moved to finished signal

        def on_err(msg: str) -> None:
            chat_out.append(f"[BACKEND ERROR] {msg}\n")
            status.showMessage(msg)
            send_btn.setEnabled(True)
            chat_in.setEnabled(True)
            chat_in.setFocus()
            # _cleanup() moved to finished signal

        worker.done.connect(on_done)
        worker.err.connect(on_err)
        worker.finished.connect(_cleanup)
        set_busy(True)
        worker.start()

    def on_speak_last() -> None:
        _update_tts_nav_buttons()
        text = last_reply["text"]
        if not text:
            return

        worker = TTSWorker(engine, text)
        active_threads.append(worker)

        def _cleanup() -> None:
            if worker in active_threads:
                active_threads.remove(worker)
            worker.deleteLater()
            set_busy(False)

        def on_done(wavs: list) -> None:
            last_tts["wavs"] = [str(w) for w in (wavs or [])]
            last_tts["idx"] = 0
            btn_play.setEnabled(bool(last_tts["wavs"]))
            btn_stop.setEnabled(bool(last_tts["wavs"]))
            status.showMessage("TTS ready")

            if chk_speak.isChecked():
                on_play()

            # _cleanup() moved to finished signal

        def on_err(msg: str) -> None:
            chat_out.append(f"[TTS ERROR] {msg}\n")
            status.showMessage(msg)
            # _cleanup() moved to finished signal

        worker.done.connect(on_done)
        worker.err.connect(on_err)
        worker.finished.connect(_cleanup)
        set_busy(True)
        worker.start()

    def on_play() -> None:
        _tts_stop_flag["stopped"] = False
        _play_current_chunk()


    def _shutdown_threads() -> None:
        # Wait a moment for any in-flight threads to finish to avoid SIGABRT
        for t in list(active_threads):
            t.wait(3000)

    app.aboutToQuit.connect(_shutdown_threads)

    def on_stop() -> None:
        _tts_stop_flag["stopped"] = True
        sfx.stop()

    def _maybe_autonext(*_args) -> None:
        # Some PyQt builds emit playingChanged() with no args.
        # Determine state directly from the object.
        if sfx.isPlaying():
            return

        wavs = last_tts["wavs"]
        if not wavs:
            return

        # If user hit Stop, don't auto-advance
        if _tts_stop_flag["stopped"]:
            _tts_stop_flag["stopped"] = False
            return

        # Advance to next chunk if available
        if last_tts["idx"] < len(wavs) - 1:
            last_tts["idx"] += 1
            QTimer.singleShot(50, _play_current_chunk)
        else:
            status.showMessage("TTS finished")

    # ---------------- WIRING ----------------
    sfx.playingChanged.connect(_maybe_autonext)
    btn_clear_memory.clicked.connect(on_clear_memory)
    send_btn.clicked.connect(on_send)
    chat_in.returnPressed.connect(on_send)
    btn_new_chat.clicked.connect(on_new_chat)
    btn_exit.clicked.connect(win.close)
    btn_speak_now.clicked.connect(on_speak_last)
    btn_play.clicked.connect(on_play)
    btn_stop.clicked.connect(on_stop)
    btn_prev.clicked.connect(on_prev)
    btn_next.clicked.connect(on_next)

    win.show()
    QTimer.singleShot(0, update_portrait)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
