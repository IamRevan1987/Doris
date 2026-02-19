
from PyQt6.QtMultimedia import QMediaDevices, QAudioFormat, QAudioSink, QAudio
from PyQt6.QtWidgets import QApplication
import sys

def check():
    app = QApplication(sys.argv)
    device = QMediaDevices.defaultAudioOutput()
    print(f"Device: {device.description()}")
    
    pref = device.preferredFormat()
    print(f"Preferred: {pref.sampleRate()}Hz, {pref.channelCount()}ch, {pref.sampleFormat()}")
    
    fmt16 = QAudioFormat()
    fmt16.setSampleRate(16000)
    fmt16.setChannelCount(1)
    fmt16.setSampleFormat(QAudioFormat.SampleFormat.Int16)
    
    print(f"Is 16000Hz Supported? {device.isFormatSupported(fmt16)}")

if __name__ == "__main__":
    check()
