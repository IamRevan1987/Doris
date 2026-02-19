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
    QEvent, QObject, Qt, QThread, QTimer, QUrl, pyqtSignal, QSettings, QIODevice, QByteArray
)
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtMultimedia import (
    QSoundEffect, QAudioSink, QAudioFormat, QMediaDevices, QAudio
)
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPushButton,
    QStatusBar, QTextEdit, QVBoxLayout, QWidget, QSlider, QStyle
)

# Local
from brain_ops import ChatEngine
from core.core_tts_rules import chunk_for_tts


##  ##                                                      ##  ##  Constants / Config  ##  ##

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


##  ##                                                      ##  ##  UI Helpers  ##  ##

def apply_theme(app: QApplication, dark: bool) -> None:
    """Applies the selected theme stylesheet."""
    app.setStyleSheet(DARK_QSS if dark else LIGHT_QSS)


def _panel_frame() -> QFrame:
    """Creates a styled panel frame."""
    f = QFrame()
    f.setFrameShape(QFrame.Shape.StyledPanel)
    f.setFrameShadow(QFrame.Shadow.Raised)
    return f


##  ##                                                      ##  ##  Worker Threads  ##  ##

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


class TTSStreamWorker(QThread):
    """
    TTS worker for STREAMING.
    Emits raw PCM bytes in chunks to be played immediately.
    """
    chunk_ready = pyqtSignal(bytes)
    finished_ok = pyqtSignal()
    err = pyqtSignal(str)

    def __init__(self, engine: ChatEngine, text: str, speed: float = 1.0):
        super().__init__()
        self.engine = engine
        self.text = text
        self.speed = speed
        self._is_stopped = False

    def stop(self):
        self._is_stopped = True

    def run(self) -> None:
        try:
            # Pre-chunk text so we can start generating immediately
            # The engine.tts.stream_synthesis handles the subprocess
            # We iterate over text chunks here to allow finer interruption?
            # Actually, passing full text to piper is fine, but splitting helps latency
            # if we wanted to pipeline generation of chunk 2 while playing chunk 1.
            # For simplicity, we feed sentence chunks to the generator one by one.
            
            text_chunks = chunk_for_tts(self.text)
            if not text_chunks:
                self.finished_ok.emit()
                return

            for content in text_chunks:
                if self._is_stopped:
                    break
                
                # Streaming generator loop
                for pcm_chunk in self.engine.tts.stream_synthesis(content, self.speed):
                    if self._is_stopped:
                        break
                    self.chunk_ready.emit(pcm_chunk)
            
            self.finished_ok.emit()

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


##  ##                                                      ##  ##  Main Window Class  ##  ##

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
        self.is_speaking = False
        self.portrait_pixmap = None
        self.current_worker = None # Track TTS worker specifically for cancellation

        # # SETTINGS (Persistence) #
        self.settings = QSettings("Doris", "Tutor")
        
        # # AUDIO SINK (Streaming) #
        self.audio_sink = None
        self.audio_io = None
        self.audio_buffer = bytearray() # App-level buffer for overflow
        self._init_audio_output()

        # # INIT UI #
        self.setWindowTitle("🧑‍🏫 Doris — Tutor Console (Beta)")
        self.resize(1100, 650)
        self._build_ui()
        self._setup_menu()
        self._load_portrait()
        
        # # SHUTDOWN HOOK #
        self.app.aboutToQuit.connect(self._shutdown_threads)

    def _init_audio_output(self):
        """Setup QAudioSink for raw PCM streaming. Upsampling 16k->48k for compatibility."""
        # Informative but short: Initializes QAudioSink with 48kHz sampling rate.
        if self.audio_sink is not None:
            return
            
        fmt = QAudioFormat()
        # Force 48000Hz as it's the standard for most hardware
        fmt.setSampleRate(48000)
        fmt.setChannelCount(1)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        
        device = QMediaDevices.defaultAudioOutput()
        print(f"[AUDIO] Default Device: {device.description()}")
        if not device.isFormatSupported(fmt):
             print(f"[AUDIO] Warning: 48000Hz S16LE buffer format not supported by {device.description()}.")
        
        self.audio_sink = QAudioSink(device, fmt)
        # Low-latency buffer (~0.5s).
        # We rely on self.audio_buffer (app-level) to handle TTS surges.
        # This ensures 'Stop' is near-instant even if reset() is sluggish.
        self.audio_sink.setBufferSize(48 * 1024)
        
        # Restore volume
        saved_vol = self.settings.value("volume", 0.8, type=float)
        self.audio_sink.setVolume(saved_vol)
        
        # Verify what we got
        actual = self.audio_sink.format()
        print(f"[AUDIO] Sink Initialized: {actual.sampleRate()}Hz, {actual.channelCount()}ch, Buffer: {self.audio_sink.bufferSize()}")
        
        # Connect state changes to UI
        self.audio_sink.stateChanged.connect(self._on_audio_state_changed)
        
        # Setup Timer for pumping buffer (Qt6 QAudioSink has no notify signal)
        self.pump_timer = QTimer(self)
        self.pump_timer.timeout.connect(self._pump_audio)
        self.pump_timer.start(50) # Check every 50ms

    # ... UI Building omitted ...

    def _resample_chunk(self, data: bytes, in_rate: int = 22050, out_rate: int = 48000) -> bytes:
        """
        Simple Nearest-Neighbor Resampling to match hardware rate.
        22050 / 48000 ~= 0.459375
        """
        if in_rate == out_rate:
            return data
            
        import array
        # Input 16-bit
        in_arr = array.array('h')
        in_arr.frombytes(data)
        
        out_arr = array.array('h')
        
        ratio = in_rate / out_rate
        # Output length
        out_len = int(len(in_arr) / ratio)
        
        # Simple loop (integer math approximation for speed?)
        # For pure python, simple float mult inside loop might be okay for small chunks.
        # chunk size ~4096 bytes -> 2048 samples. 
        # Output -> ~4500 samples. 4500 iters is fast enough.
        
        for i in range(out_len):
            idx = int(i * ratio)
            if idx >= len(in_arr):
                idx = len(in_arr) - 1
            out_arr.append(in_arr[idx])
            
        return out_arr.tobytes()

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
        
        # Checkbox
        self.chk_speak = QCheckBox("Speak replies")
        self.chk_speak.setChecked(True)
        
        # Manual Trigger
        self.btn_speak_now = QPushButton("Speak last")
        self.btn_speak_now.setEnabled(False)
        
        # Stop
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setEnabled(False)
        
        # -- Audio Control Block --
        # Layout: VBox with Vol and Speed
        audio_ctrl_layout = QVBoxLayout()
        audio_ctrl_layout.setContentsMargins(0, 0, 0, 0)
        audio_ctrl_layout.setSpacing(2)

        # Volume Row
        vol_row = QHBoxLayout()
        vol_val = int(self.audio_sink.volume() * 100)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(vol_val)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setToolTip(f"Volume: {vol_val}%")
        vol_row.addWidget(QLabel("🔊"))
        vol_row.addWidget(self.vol_slider)
        
        # Speed Row
        speed_row = QHBoxLayout()
        saved_speed = self.settings.value("speed", 1.0, type=float)
        # Slider range: 50% to 200% -> int 50 to 200
        speed_int = int(saved_speed * 100)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(speed_int)
        self.speed_slider.setFixedWidth(80)
        self.speed_slider.setToolTip(f"Speed: {saved_speed}x")
        
        speed_label = QLabel("⚡") # lightning/speed icon
        speed_row.addWidget(speed_label)
        speed_row.addWidget(self.speed_slider)
        
        audio_ctrl_layout.addLayout(vol_row)
        audio_ctrl_layout.addLayout(speed_row)
        
        # Assemble TTS Row
        tr.addWidget(self.chk_speak)
        tr.addWidget(self.btn_speak_now)
        tr.addWidget(self.btn_stop)
        tr.addSpacing(10)
        tr.addLayout(audio_ctrl_layout)
        tr.addStretch(1)
        
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
        self.btn_stop.clicked.connect(self.on_stop)
        
        self.vol_slider.valueChanged.connect(self.on_volume_changed)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)

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

    # ---- Handlers ----
    ##  ##                                                      ##  ##  Event Handlers  ##  ##

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
    
    def on_volume_changed(self, value: int):
        vol = value / 100.0
        self.audio_sink.setVolume(vol)
        self.settings.setValue("volume", vol)
        self.vol_slider.setToolTip(f"Volume: {value}%")

    def on_speed_changed(self, value: int):
        speed_factor = value / 100.0
        self.settings.setValue("speed", speed_factor)
        self.speed_slider.setToolTip(f"Speed: {speed_factor}x")

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
            self.on_stop()

            self.btn_speak_now.setEnabled(False)

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
        self.on_stop()

        # Reset in-memory conversation only (no disk wipe)
        try:
            self.engine.reset_conversation()
        except Exception:
            if hasattr(self.engine, "history"):
                self.engine.history.clear()

        # Reset UI
        self.chat_out.clear()
        self.chat_in.clear()
        self.last_reply_text = ""
        self.btn_speak_now.setEnabled(False)

        self.status.showMessage("New chat started")

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
        
        # Stop any ongoing speech when new request is made
        self.on_stop()

        worker = Worker(self.engine, text)
        self.active_threads.append(worker)

        # Worker callbacks
        worker.done.connect(self._on_msg_done)
        worker.err.connect(self._on_msg_err)
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
        """Start TTS Streaming for last reply."""
        text = self.last_reply_text
        if not text:
            return
            
    def on_speak_last(self) -> None:
        """Start TTS Streaming for last reply."""
        text = self.last_reply_text
        if not text:
            return
            
        # Stop existing (invalidates current_worker, so late chunks are ignored)
        self.on_stop()

        self.status.showMessage("Synthesizing...")
        self.btn_stop.setEnabled(True)
        
        # Retrieve speed setting
        speed = self.settings.value("speed", 1.0, type=float)
        
        # Ensure Audio Sink is ready (should be always ready, but check incase of error recovery)
        if not self.audio_sink:
            self._init_audio_output()

        # Start Audio IO
        # If sink is stopped, start() returns the IO device.
        # If it's already active (unlikely if strictly sequential), it might return None or existing IO.
        # But we called on_stop() above, so it should be StoppedState.
        self.audio_io = self.audio_sink.start()

        # Create Worker
        worker = TTSStreamWorker(self.engine, text, speed=speed)
        self.current_worker = worker
        self.active_threads.append(worker)

        worker.chunk_ready.connect(self._on_tts_chunk)
        worker.finished_ok.connect(self._on_tts_finished)
        worker.err.connect(self._on_tts_err)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        
        worker.start()

    def _on_tts_chunk(self, data: bytes) -> None:
        if not self.audio_io or not self.audio_sink:
            return
            
        if self.sender() is not self.current_worker:
            print("[DEBUG] Dropping chunk: Stale worker")
            return

        # Upsample 22050 -> 48000
        new_data = self._resample_chunk(data, in_rate=22050, out_rate=48000)
        
        # Append to app buffer
        self.audio_buffer.extend(new_data)
        
        # Try to pump immediately
        self._pump_audio()

    def _pump_audio(self) -> None:
        """Write pending audio from app buffer to sink."""
        # Informative but short: Writes available audio data to the output device.
        if not self.audio_sink or not self.audio_io or not self.audio_buffer:
            return

        # AudioSink might be in Idle or Active state.
        if self.audio_sink.state() == QAudio.State.StoppedState:
             return

        bytes_free = self.audio_sink.bytesFree()
        if bytes_free > 0:
            to_write = self.audio_buffer[:bytes_free]
            written = self.audio_io.write(to_write)
            if written > 0:
                del self.audio_buffer[:written]

    def _on_audio_state_changed(self, state: QAudio.State) -> None:
        """Update UI based on audio state."""
        if state == QAudio.State.ActiveState:
            self.btn_stop.setEnabled(True)
        elif state == QAudio.State.IdleState or state == QAudio.State.StoppedState:
            self.btn_stop.setEnabled(False)
            if state == QAudio.State.IdleState:
                # Finished playing buffer
                self.status.showMessage("Playback finished")

    def _on_tts_finished(self):
        self.status.showMessage("Generation finished (playing buffer...)")
        self.current_worker = None
        # Do NOT disable stop button here; we might still be playing audio from buffer.
        
    def _on_tts_err(self, msg: str) -> None:
        self.chat_out.append(f"[TTS ERROR] {msg}\n")
        self.status.showMessage("TTS Error")
        self.on_stop()

    def on_stop(self) -> None:
        """Stop playback and generation immediately."""
        print(f"[DEBUG] on_stop called. Worker={self.current_worker is not None}")
        
        if self.current_worker:
            print("[DEBUG] Stopping worker thread...")
            # This sets the worker's internal flag so it stops emitting chunks
            self.current_worker.stop()
            self.current_worker = None
        
        # Audio Stop Logic
        self.audio_buffer.clear() # Clear app buffer!
        
        # 1. Invalidate IO so no more rights happen from any lingering signals
        self.audio_io = None 
        
        # 2. Stop and Reset the sink
        if self.audio_sink:
            state = self.audio_sink.state()
            if state == QAudio.State.ActiveState or state == QAudio.State.IdleState:
                self.audio_sink.stop() 
                self.audio_sink.reset() # Drop all buffers immediately
        
        self.status.showMessage("Stopped")
        # Button state is handled by _on_audio_state_changed signal

    def _shutdown_threads(self) -> None:
        self.on_stop()
        for t in list(self.active_threads):
            t.wait(1000)

    def trigger_greeting(self) -> None:
        """
        Warm-up greeting.
        """
        hour = datetime.now().hour
        if 5 <= hour < 12:
            time_greeting = "Good morning"
        elif 12 <= hour < 18:
            time_greeting = "Good afternoon"
        else:
            time_greeting = "Good evening"

        day_name = datetime.now().strftime("%A")
        greeting_text = f"{time_greeting} {self.engine.user_name}, happy {day_name}."
        
        # Set explicitly so 'Speak Last' works for it
        self.last_reply_text = greeting_text
        self.on_speak_last()


##  ##                                                      ##  ##  Bootstrap  ##  ##

def main() -> None:
    app = QApplication(sys.argv)
    apply_theme(app, True)

    win = DorisWindow(app)
    win.show()

    # Trigger greeting shortly after show
    QTimer.singleShot(800, win.trigger_greeting)
    QTimer.singleShot(0, win.update_portrait)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

# ---- Invariants Check ----
# SAFETY: CPU limits applied at top of file (preserved implicitly by replacement range, checking...).
# Wait, user instructions said "match existing code".
# LIMITATION: My replacement text started AFTER the safety harness?
# The tool replaces lines 12-652. Lines 1-11 were preserved?
# Accessing file to check...
