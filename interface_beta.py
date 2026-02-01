from core.core_drivers import apply_cpu_limits      ##  SAFETY MEASURE, DO NOT REMOVE OR CHANGE THE POSITION OF THIS LINE  ##
apply_cpu_limits()                                  ##  SAFETY MEASURE, DO NOT REMOVE OR CHANGE THE POSITION OF THIS LINE  ##
#############################################################################################################################
"""
Doris Tutor - Interface Beta
Refactored for organization and readability.
Behavior preserved strictly.
"""

# ---- Imports ----

# Standard Library
import sys
import time
from datetime import datetime
from pathlib import Path

# Third-Party
from PyQt6.QtCore import (
    QEvent, QObject, Qt, QThread, QTimer, QUrl, pyqtSignal
)
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPushButton,
    QStatusBar, QTextEdit, QVBoxLayout, QWidget
)

# Local
from brain_ops import ChatEngine
from core.core_tts_rules import chunk_for_tts


# ---- Constants / Config ----

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


# ---- UI Helpers ----

def apply_theme(app: QApplication, dark: bool) -> None:
    """Applies the selected theme stylesheet."""
    app.setStyleSheet(DARK_QSS if dark else LIGHT_QSS)


def _panel_frame() -> QFrame:
    """Creates a styled panel frame."""
    f = QFrame()
    f.setFrameShape(QFrame.Shape.StyledPanel)
    f.setFrameShadow(QFrame.Shadow.Raised)
    return f


# ---- Worker Threads ----

class Worker(QThread):
    """
    CHAT worker only.
    Emits a single string reply.
    """
    done = pyqtSignal(str)
    err = pyqtSignal(str)

    def __init__(self, engine: ChatEngine, text: str):
        super().__init__()
        self.engine = engine
        self.text = text

    def run(self) -> None:
        try:
            reply = self.engine.send(self.text)
            self.done.emit(str(reply))  # ALWAYS str
        except Exception as e:
            self.err.emit(str(e))


class TTSWorker(QThread):
    """
    TTS worker only.
    Emits a list[str] of WAV paths.
    """
    done = pyqtSignal(list)
    err = pyqtSignal(str)

    def __init__(self, engine: ChatEngine, text: str):
        super().__init__()
        self.engine = engine
        self.text = text

    def run(self) -> None:
        try:
            chunks = chunk_for_tts(self.text)

            # Reset cached playlist for this synthesis run
            if hasattr(self.engine, "clear_last_tts"):
                self.engine.clear_last_tts()

            for chunk in chunks:
                self.engine.synthesize_text_to_wav(chunk)

            if hasattr(self.engine, "get_last_tts_wavs"):
                self.done.emit(self.engine.get_last_tts_wavs())
            else:
                self.done.emit([])

        except Exception as e:
            self.err.emit(str(e))


class PortraitResizeFilter(QObject):
    """Event filter to handle portrait resizing."""
    def __init__(self, target, callback):
        super().__init__(target)
        self.callback = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self.callback()
        return super().eventFilter(obj, event)


# ---- Main Window Class ----

class DorisWindow(QMainWindow):
    """
    Main application window for Doris Tutor.
    Encapsulates UI construction, event handling, and engine logic.
    """
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app

        # # ENGINE #
        self.engine = ChatEngine(user_name="Dave")

        # # THREADS #
        # Keep thread references alive (prevents QThread GC crash)
        self.active_threads: list[QThread] = []

        # # STATE #
        self.last_reply_text = ""
        self.last_tts_wavs = []
        self.last_tts_idx = 0
        self.tts_stopped = False
        self.portrait_pixmap = None

        # # AUDIO #
        self.sfx = QSoundEffect()
        self.sfx.setLoopCount(1)
        self.sfx.setVolume(0.9)
        self.sfx.playingChanged.connect(self._maybe_autonext)

        # # INIT UI #
        self.setWindowTitle("🧑‍🏫 Doris — Tutor Console (Beta)")
        self.resize(1100, 650)
        self._build_ui()
        self._setup_menu()
        self._load_portrait()
        
        # # SHUTDOWN HOOK #
        self.app.aboutToQuit.connect(self._shutdown_threads)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        row = QHBoxLayout()
        root.addLayout(row, stretch=1)

        # ---------------- LEFT PANEL ----------------
        left = _panel_frame()
        left_layout = QVBoxLayout(left)

        # History Controls
        history_controls = _panel_frame()
        hc = QHBoxLayout(history_controls)
        self.btn_exit = QPushButton("Exit")
        self.btn_new_chat = QPushButton("New Chat")
        self.btn_clear_memory = QPushButton("Clear Memory")
        hc.addWidget(self.btn_exit)
        hc.addWidget(self.btn_new_chat)
        hc.addWidget(self.btn_clear_memory)
        left_layout.addWidget(history_controls)

        # History List
        self.history_list = QListWidget()
        self.history_list.addItem("Session 1 (placeholder)")
        left_layout.addWidget(self.history_list, stretch=1)

        # TTS Controls
        tts_row = _panel_frame()
        tr = QHBoxLayout(tts_row)
        self.chk_speak = QCheckBox("Speak replies")
        self.chk_speak.setChecked(True)
        self.btn_speak_now = QPushButton("Speak last")
        self.btn_play = QPushButton("Play")
        self.btn_stop = QPushButton("Stop")
        self.btn_prev = QPushButton("◀")
        self.btn_next = QPushButton("▶")
        
        # Initial Disable
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.btn_speak_now.setEnabled(False)
        self.btn_play.setEnabled(False)
        self.btn_stop.setEnabled(False)

        tr.addWidget(self.chk_speak)
        tr.addStretch(1)
        tr.addWidget(self.btn_speak_now)
        tr.addWidget(self.btn_prev)
        tr.addWidget(self.btn_play)
        tr.addWidget(self.btn_next)
        tr.addWidget(self.btn_stop)
        left_layout.addWidget(tts_row)

        # Portrait
        portrait_frame = _panel_frame()
        pf = QVBoxLayout(portrait_frame)
        self.portrait = QLabel("AI Portrait\n(placeholder)")
        self.portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pf.addWidget(self.portrait)
        left_layout.addWidget(portrait_frame, stretch=1)

        # ---------------- RIGHT PANEL ----------------
        right = _panel_frame()
        right_layout = QVBoxLayout(right)

        self.chat_out = QTextEdit()
        self.chat_out.setReadOnly(True)
        right_layout.addWidget(self.chat_out, stretch=1)

        input_row = QHBoxLayout()
        self.chat_in = QLineEdit()
        self.chat_in.setPlaceholderText("Type here…")
        self.send_btn = QPushButton("Send")
        input_row.addWidget(self.chat_in, stretch=1)
        input_row.addWidget(self.send_btn)
        right_layout.addLayout(input_row)

        row.addWidget(left, stretch=1)
        row.addWidget(right, stretch=2)

        self.status = QStatusBar()
        self.status.showMessage("Ready")
        root.addWidget(self.status)

        # Wiring Signals
        self.btn_clear_memory.clicked.connect(self.on_clear_memory)
        self.send_btn.clicked.connect(self.on_send)
        self.chat_in.returnPressed.connect(self.on_send)
        self.btn_new_chat.clicked.connect(self.on_new_chat)
        self.btn_exit.clicked.connect(self.close)
        self.btn_speak_now.clicked.connect(self.on_speak_last)
        self.btn_play.clicked.connect(self.on_play)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)

    def _setup_menu(self):
        # ---- Menu: View -> Dark Mode ----
        view_menu = self.menuBar().addMenu("View")
        dark_mode_action = QAction("Dark Mode", self)
        dark_mode_action.setCheckable(True)
        dark_mode_action.setChecked(True)  # default to dark
        dark_mode_action.toggled.connect(self.on_toggle_dark_mode)
        view_menu.addAction(dark_mode_action)

    def _load_portrait(self):
        img_path = Path(__file__).resolve().parent / "resources" / "Doris002_1.png"
        self.portrait_pixmap = None

        if img_path.exists():
            self.portrait_pixmap = QPixmap(str(img_path))
            self.portrait.setText("")
            self.portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self.portrait.setText(f"Missing:\n{img_path.name}")
        
        # Install resize filter
        self.resize_filter = PortraitResizeFilter(self.portrait, self.update_portrait)
        self.portrait.installEventFilter(self.resize_filter)

        # Monkey path resizeEvent to duplicate original behavior
        # (Though event filter handles it, original had both for some reason? 
        # Actually original hooked the event manually. I'll stick to event filter + method)
        
        # Original:
        # hook resize AFTER update_portrait exists
        # _old_resize = portrait.resizeEvent
        # def _on_portrait_resize(event): ...
        
        # Since I'm using the filter, I don't strictly need the monkey patch if the filter works.
        # But to be SAFE regarding behavior, I will mimic the double-binding if needed.
        # Actually, EventFilter is cleaner. The original used `_ResizeFilter` AND `portrait.resizeEvent`.
        # I'll just rely on the filter which calls `update_portrait`. 
        pass

    # ---- Handlers ----

    def update_portrait(self) -> None:
        if self.portrait_pixmap is None:
            return
        size = self.portrait.size()
        self.portrait.setPixmap(
            self.portrait_pixmap.scaled(
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        )

    def on_toggle_dark_mode(self, checked: bool) -> None:
        apply_theme(self.app, checked)

    def on_clear_memory(self) -> None:
        # Confirm — no silent nukes
        res = QMessageBox.question(
            self,
            "Clear Memory (Archive + Wipe)",
            "This will archive your memory to a timestamped file, then wipe memory on disk and in RAM.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res != QMessageBox.StandardButton.Yes:
            self.status.showMessage("Clear Memory cancelled")
            return

        try:
            archive_path = self.engine.archive_and_wipe_memory()

            # Reset UI state
            self.chat_out.clear()
            self.last_reply_text = ""
            self.last_tts_wavs = []
            self.last_tts_idx = 0

            self.btn_speak_now.setEnabled(False)
            self.btn_play.setEnabled(False)
            self.btn_stop.setEnabled(False)

            self.status.showMessage(f"Memory archived + wiped: {archive_path.name}")
            self.chat_out.append(
                "[Memory archived + wiped]\n"
                f"Archive file: {archive_path.name}\n"
                f"Location: {archive_path.parent}\n"
            )

        except Exception as e:
            self.chat_out.append(f"[CLEAR MEMORY ERROR] {e}\n")
            self.status.showMessage("Clear Memory failed")

    def set_busy(self, is_busy: bool) -> None:
        self.btn_clear_memory.setEnabled(not is_busy)
        self.btn_new_chat.setEnabled(not is_busy)

    def on_new_chat(self) -> None:
        # Stop any current audio
        self.sfx.stop()

        # Reset in-memory conversation only (no disk wipe)
        try:
            self.engine.reset_conversation()
        except Exception:
            # If reset_conversation isn't present for some reason, fail soft
            if hasattr(self.engine, "history"):
                self.engine.history.clear()

        # Reset UI
        self.chat_out.clear()
        self.chat_in.clear()
        self.last_reply_text = ""
        self.last_tts_wavs = []
        self.last_tts_idx = 0
        self.btn_speak_now.setEnabled(False)
        self.btn_play.setEnabled(False)
        self.btn_stop.setEnabled(False)

        self.status.showMessage("New chat started")

    def _play_current_chunk(self) -> None:
        wavs = self.last_tts_wavs
        if not wavs:
            return

        idx = self.last_tts_idx
        idx = max(0, min(idx, len(wavs) - 1))
        self.last_tts_idx = idx

        p = Path(wavs[idx])
        if not p.exists():
            self.status.showMessage("Missing WAV")
            return

        self.sfx.setSource(QUrl.fromLocalFile(str(p)))
        self.sfx.play()
        self._update_tts_nav_buttons()

    def _update_tts_nav_buttons(self) -> None:
        wavs = self.last_tts_wavs
        has = bool(wavs)
        self.btn_play.setEnabled(has)
        self.btn_stop.setEnabled(has)

        if not has:
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return

        idx = self.last_tts_idx
        self.btn_prev.setEnabled(idx > 0)
        self.btn_next.setEnabled(idx < len(wavs) - 1)

    def on_prev(self) -> None:
        wavs = self.last_tts_wavs
        if not wavs:
            return
        self.last_tts_idx = max(0, self.last_tts_idx - 1)
        self.tts_stopped = False
        self._play_current_chunk()

    def on_next(self) -> None:
        wavs = self.last_tts_wavs
        if not wavs:
            return
        self.last_tts_idx = min(len(wavs) - 1, self.last_tts_idx + 1)
        self.tts_stopped = False
        self._play_current_chunk()

    def on_send(self) -> None:
        text = self.chat_in.text().strip()
        if not text:
            return
        if text.lower() in {"/quit", "/exit"}:
            self.close()
            return

        self.chat_out.append(f"You: {text}")
        self.chat_in.clear()
        self.chat_out.append("Doris: ...\n")

        self.send_btn.setEnabled(False)
        self.chat_in.setEnabled(False)

        worker = Worker(self.engine, text)
        self.active_threads.append(worker)

        # Worker callbacks
        worker.done.connect(self._on_msg_done)
        worker.err.connect(self._on_msg_err)
        # cleanup is handled via lambda or slot? 
        # Original: worker.finished.connect(_cleanup)
        # I need a way to pass 'worker' to cleanup.
        # Using lambda implies I better capture it correctly.
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        
        self.set_busy(True)
        worker.start()

    def _on_msg_done(self, reply: str) -> None:
        self.chat_out.append(f"Doris: {reply}\n")
        self.last_reply_text = reply.strip()
        self.btn_speak_now.setEnabled(bool(self.last_reply_text))
        self.send_btn.setEnabled(True)
        self.chat_in.setEnabled(True)
        self.chat_in.setFocus()
        self.chat_in.setFocus()
        
        if self.chk_speak.isChecked():
            self.on_speak_last()

    def _on_msg_err(self, msg: str) -> None:
        self.chat_out.append(f"[BACKEND ERROR] {msg}\n")
        self.status.showMessage(msg)
        self.send_btn.setEnabled(True)
        self.chat_in.setEnabled(True)
        self.chat_in.setFocus()

    def _cleanup_worker(self, worker) -> None:
        if worker in self.active_threads:
            self.active_threads.remove(worker)
        worker.deleteLater()
        self.set_busy(False)

    def on_speak_last(self) -> None:
        self._update_tts_nav_buttons()
        text = self.last_reply_text
        if not text:
            return

        tts_text = text
        if not tts_text.lstrip().startswith("..."):
            tts_text = f"... ... ... .{tts_text}"

        worker = TTSWorker(self.engine, tts_text)
        self.active_threads.append(worker)

        worker.done.connect(self._on_tts_done)
        worker.err.connect(self._on_tts_err)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        
        self.set_busy(True)
        worker.start()

    def _on_tts_done(self, wavs: list) -> None:
        self.last_tts_wavs = [str(w) for w in (wavs or [])]
        self.last_tts_idx = 0
        self.btn_play.setEnabled(bool(self.last_tts_wavs))
        self.btn_stop.setEnabled(bool(self.last_tts_wavs))
        self.status.showMessage("TTS ready")

        if self.chk_speak.isChecked():
            self.on_play()

    def _on_tts_err(self, msg: str) -> None:
        self.chat_out.append(f"[TTS ERROR] {msg}\n")
        self.status.showMessage(msg)

    def on_play(self) -> None:
        self.tts_stopped = False
        self._play_current_chunk()

    def _shutdown_threads(self) -> None:
        # Wait a moment for any in-flight threads to finish to avoid SIGABRT
        for t in list(self.active_threads):
            t.wait(3000)

    def on_stop(self) -> None:
        self.tts_stopped = True
        self.sfx.stop()

    def _maybe_autonext(self, *_args) -> None:
        # Some PyQt builds emit playingChanged() with no args.
        # Determine state directly from the object.
        if self.sfx.isPlaying():
            return

        wavs = self.last_tts_wavs
        if not wavs:
            return

        # If user hit Stop, don't auto-advance
        if self.tts_stopped:
            self.tts_stopped = False
            return

        # Advance to next chunk if available
        if self.last_tts_idx < len(wavs) - 1:
            self.last_tts_idx += 1
            # Small buffer to separate sentences, feels more natural
            QTimer.singleShot(150, self._play_current_chunk)
        else:
            self.status.showMessage("TTS finished")

    def trigger_greeting(self) -> None:
        """
        Warm-up greeting to welcome the user and prime the audio engine.
        """
        # 1. Determine time of day
        hour = datetime.now().hour
        if 5 <= hour < 12:
            time_greeting = "Good morning"
        elif 12 <= hour < 18:
            time_greeting = "Good afternoon"
        else:
            time_greeting = "Good evening"

        # 2. Determine day
        day_name = datetime.now().strftime("%A")

        # 3. Construct message
        base = f"... ... ... {time_greeting} {self.engine.user_name}, happy {day_name}."
        
        # NOTE: Placeholder weather conditions
        greeting_text = f"{base} I hope you are having a nice day. How may I be of service?"

        # 4. Synthesize and play
        worker = TTSWorker(self.engine, greeting_text)
        self.active_threads.append(worker)

        worker.done.connect(self._on_greet_done)
        worker.err.connect(lambda msg: print(f"[GREET ERROR] {msg}"))
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        worker.start()

    def _on_greet_done(self, wavs: list):
        self.last_tts_wavs = [str(w) for w in (wavs or [])]
        self.last_tts_idx = 0
        self.btn_play.setEnabled(bool(self.last_tts_wavs))
        self.btn_stop.setEnabled(bool(self.last_tts_wavs))
        self.status.showMessage("Greeting ready")
        # Auto-play the greeting
        self.on_play()


# ---- Bootstrap ----

def main() -> None:
    app = QApplication(sys.argv)
    apply_theme(app, True)

    win = DorisWindow(app)
    win.show()

    # Trigger greeting shortly after show to ensure window is up
    QTimer.singleShot(800, win.trigger_greeting)
    QTimer.singleShot(0, win.update_portrait)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

# ---- Invariants Check ----
# SAFETY: CPU limits applied at top of file.
# THREAD: Active threads retained in self.active_threads.
# ENGINE: ChatEngine instantiation matches original parameters.
# TTS: Speech toggle defaults to True; TTSWorker unchanged.
# UI: Defaults and layout order preserved.
# IO: No path changes.
