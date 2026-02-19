from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QMainWindow
from PyQt6.QtCore import QSize
# # Only needed for access to command line arguments
# import sys


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        ## ##                           ## ##  This is the outer window that contains app
        self.setWindowTitle("Dave's Test Window")
        self.setFixedSize(QSize(600,420))       ## Turn this off to allow the user the ability to resize.


        ## ## Vertical Box Alignment Layout
        layout = QVBoxLayout()

        ## ##  Places a label in the main window area
        self.label = QLabel("<h1>This is an informative text message</h1>")

        ## ##  Builds the main button in the app
        self.button = QPushButton("Click here...")
        self.button.clicked.connect(self.button_clicked)

        ## ##  Places the label and button widgets in the window.
        layout.addWidget(self.label)
        layout.addWidget(self.button)

        window = QWidget()
        window.setLayout(layout)

        self.setCentralWidget(window)

    ## ##                           ## ##  Defines the action when the button is clicked.
    def button_clicked(self):
        self.label.setText("<h1>This is an informative text message</h1>")
        self.button.setText("Thanks for clicking!")


# You need one (and only one) QApplication instance per application.
# Pass in sys.argv to allow command line arguments for your app.
# If you know you won't use command line arguments QApplication([]) works too.
app = QApplication([])
window = MainWindow()
window.show()

## ## Start the event loop.
app.exec()
