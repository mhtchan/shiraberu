import sys
import dictionary_display
import tab_widget
from PyQt6.QtWidgets import (
    QApplication
    ,QMainWindow
)
from manga_ocr import MangaOcr
import functools

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.manga_ocr = MangaOcr()
        self.dictionary_display = functools.partial(dictionary_display.MainWindow,self.manga_ocr)
        self.tab_widget = tab_widget.ShrinkTabWidget(self.dictionary_display)
        self.setCentralWidget(self.tab_widget)
        self.setWindowTitle("Dictionary lookup")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())