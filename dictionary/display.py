import sys
from PyQt6.QtWidgets import (
    QMainWindow, 
    QLabel, 
    QLineEdit, 
    QPushButton, 
    QWidget, 
    QAbstractItemView, 
    QVBoxLayout, 
    QHBoxLayout, 
    QTableView, 
    QHeaderView,
    QApplication
)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QEvent, QAbstractTableModel
from PyQt6.QtGui import QFontDatabase, QFont, QKeySequence
from PyQt6.QtWebEngineWidgets import QWebEngineView
import ujson
from dictionary.loader import get_definition
from dictionary.config import ConfigWindow
from PIL import ImageGrab
from PIL.PngImagePlugin import PngImageFile
from PIL.BmpImagePlugin import DibImageFile
from manga_ocr import MangaOcr
import re

def format_definitions(text):
    out = text.replace('\n','<br>')

    ## Make sure there is a line break before bracketed circled unicode numbers
    ## (?<!^) negative look behind to ensure that the pattern is not at the start of the string
    ## \uff08 and \uff09 are brackets
    ## \u2460-\u2473 is the range of circled unicode numbers
    out = re.sub(r'(?<!^)(<br>)*(\uff08[\u2460-\u2473]\uff09)',r"<br>\2",out)

    ## Similar to above, make sure there is a line break before unbracketed circled unicode numbers while ignoring the bracketed ones
    out = re.sub(r'(?<!^)(<br>)*([\u2460-\u2473])(?!\uff09)',r"<br>\2",out)
    return out

def definition_to_html(definition, expression, reading):
    _definition = ujson.loads(definition['glossary'])
    try:
        _headword, d = _definition[0].removesuffix('\n').split('\n',1)
        _definition_list = [d]+_definition[1:]
        _definition_list = [format_definitions(i) for i in _definition_list]
    except: #Mainly for JMdict
        if reading:
            _headword = f"{expression} 【{reading}】"
        else:
            _headword = f"{expression}"
        _headword = _headword+f"{'(P) ' if definition.get('term_tags').startswith('P ') else ''}"
        _definition_list = _definition

    if len(_definition) > 1:
        _definition_list = '<ol>'+''.join(f"<li>{i}</li>" for i in _definition)+'</ol>'
    else:
        _definition_list = _definition_list[0]
        
    if reading:
        return f"""<definition>
    <b>{_headword}</b><dictname>{definition['dictionary_name']}</dictname>
    <br>
    <blockquote>
    {_definition_list}
    </blockquote>
    </definition>
    """
    return f"""<definition>
    <b>{_headword}</b><dictname>{definition['dictionary_name']}</dictname>
    <br>
    <blockquote>
    {_definition_list}
    </blockquote>
    </definition>
    """

def definitions_to_html(definitions, expression, reading):
    return '<p>'.join(definition_to_html(definition, expression, reading) for definition in definitions)

def generate_page_html(entry):
    if entry:
        definitions = definitions_to_html(
            definitions = sorted(entry.definitions, key=lambda x: (x.get('dictionary_priority'), not x.get('term_tags').startswith('P '))), 
            expression = entry.expression,
            reading = entry.reading
        )
    else:
        definitions = ''
    return f"""
    <html>
    <head>
    <style type="text/css">
    blockquote {{
      margin: 1em;
      padding: 0 1em;
      border-left: .25em solid #d0d7de;
    }}
    ol li 
    {{
      margin: 0px;
      padding: 0px;
      margin-left: -1.4em;
    }}
    dictname
    {{
      padding: .2em .4em;
      margin: 0;
      font-size: 85%;
      background-color: rgba(175,184,193,0.2);
      border-radius: 6px;
    }}
    </style>
    </head>
    <body>
    {definitions} 
    </body>
    </html>"""

class LineEdit(QLineEdit):
    def __init__(self, ocr):
        super().__init__()
        self.ocr = ocr
    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.exec(event.globalPos())
    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Paste):
            if QApplication.clipboard().text():
                self.insert(QApplication.clipboard().text())
            elif not QApplication.clipboard().image().isNull():
                data = ImageGrab.grabclipboard()
                if type(data) in (PngImageFile, DibImageFile):
                    text = self.ocr(data)
                    self.insert(text)
            return
        super().keyPressEvent(event)

class MainWindow(QMainWindow):
    def __init__(self, ocr, parent_tab=None):
        super().__init__()
        self.ocr = ocr
        
        self.dictionary = QWebEngineView()
        self.parent_tab = parent_tab
        _id = QFontDatabase.addApplicationFont("font/NotoSansJP-Regular.otf")
        _fontstr = QFontDatabase.applicationFontFamilies(_id)[0]
        self._font = QFont(_fontstr, 12)
        self.dictionary.setFont(self._font)
        self.dictionary.setHtml(generate_page_html(None))
        self.dictionary.focusProxy().installEventFilter(self)
        
        self.search_box_label = QLabel('Search')
        self.search_box = LineEdit(ocr)
        self.search_box.setFont(self._font)
        self.search_box.setPlaceholderText("Use % and _ as wildcard characters") 
        self.search_box.returnPressed.connect(self.get_definitions)
        self.search_box.setStyleSheet("""
            QLineEdit { 
                border: 1px solid;
                border-color:#dcdcdc;
                border-radius: 4px;
            } 
            QLineEdit: focus {
                border:1px solid gray;
            }"""
        )

        self.config_button = QPushButton("Config", self)
        self.config_button.resize(100,32)
        self.config_button.clicked.connect(self.config_window)

        self.table = MatchTable()
        self.model = MatchTableModel()
        self.table.setModel(self.model)
        selection_model = self.table.selectionModel()
        selection_model.selectionChanged.connect(self.on_selectionChanged)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._font_table = QFont(_fontstr, 11)
        self.table.setFont(self._font_table)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setStyleSheet("""
            QTableView {
                border: 0px solid;
                border-right: 0px solid LightGray;
            }
            
            QHeaderView::section:horizontal { 
                border: 0px solid;
                background-color: palette(base);
            }
            
            QHeaderView {
                background-color: palette(base);
            }
        """)
        layout = QVBoxLayout()
        layout.setSpacing(2)
        
        horizontal_layout_1 = QHBoxLayout()
        horizontal_layout_2 = QHBoxLayout()
        
        horizontal_layout_1.addWidget(self.search_box_label)
        horizontal_layout_1.addWidget(self.search_box)
        horizontal_layout_1.addWidget(self.config_button)
        
        horizontal_layout_2.addWidget(self.table, stretch=1)
        horizontal_layout_2.addWidget(self.dictionary, stretch=3)
        
        layout.addLayout(horizontal_layout_1)
        layout.addLayout(horizontal_layout_2)
        
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        
    @pyqtSlot('QItemSelection', 'QItemSelection')
    def on_selectionChanged(self, selected, deselected):
        for ix in selected.indexes():
            self.dictionary.setHtml(generate_page_html(self.match_data[ix.row()]))
        
    def get_definitions(self, lookup_from_search_box=True, lookup_text=None):
        # Check if the search comes from querying through the search box or ctrl+d on selected text
        if lookup_from_search_box:
            search_text = self.search_box.text()
        else:
            search_text = lookup_text
        self.match_data = get_definition(search_text)
        
        if self.parent_tab:
            self.parent_tab.setTabText(self.parent_tab.currentIndex(),search_text)
            
        # Display first result upon finding matches (if any)
        try:
            if self.match_data:
                self.dictionary.setHtml(generate_page_html(self.match_data[0]))
            else:
                self.dictionary.setHtml(generate_page_html(None))
            self.model._data = [[f"{i.expression} 【{i.reading}】"] if i.reading else [f"{i.expression}"] for i in self.match_data]
            self.model.layoutChanged.emit()
            self.table.selectRow(0)
        except Exception as e:
            print(e)

    def eventFilter(self, source, event):
        if source is self.dictionary.focusProxy() and event.type() == QEvent.Type.KeyPress:
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                if event.key() == Qt.Key.Key_D:
                    text = self.dictionary.selectedText()
                    tab_idx = self.parent_tab._addTab(text, True, self.parent_tab.currentIndex()+1)
                    self.parent_tab.widget(tab_idx).get_definitions(lookup_from_search_box=False, lookup_text=text)
                    self.parent_tab.widget(tab_idx).search_box.setText(text)
        return super().eventFilter(source, event)
    
    def config_window(self):
        self.w = ConfigWindow()
        self.w.show()

class MatchTable(QTableView):
    lookup = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        
        h_header = self.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        h_header.setHighlightSections(False)
        h_header.setSectionsClickable(False)
        
        v_header = self.verticalHeader()
        v_header.setHighlightSections(False)
        v_header.setSectionsClickable(False)
        v_header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        
        self.setCornerButtonEnabled(False)
        self.setShowGrid(False)
        self.installEventFilter(self)

    def eventFilter(self, source, event):
        # Add entry to card
        if event.type() == QEvent.Type.KeyPress:
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                if event.key() == Qt.Key.Key_D:
                    text = self.handleSelectionChanged()
                    self.lookup.emit(text)
        return super().eventFilter(source, event)

class MatchTableModel(QAbstractTableModel):
    def __init__(self, data=[]):
        super().__init__()
        self._data = data

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid():
            if role == Qt.ItemDataRole.DisplayRole:
                try:
                    value = self._data[index.row()][index.column()]
                    return str(value)
                except Exception as e:
                    print(e)
                    print(self._data)

    def rowCount(self, index):
        return len(self._data)

    def columnCount(self, index):
        if self._data:
            return len(self._data[0])
        return 0
    
    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        header = dict(enumerate(["Matches"]))
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return header.get(section)
        return super().headerData(section, orientation, role)

    def flags(self, index):
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

if __name__ == "__main__":
    manga_ocr = MangaOcr()
    app = QApplication(sys.argv)
    window = MainWindow(manga_ocr)
    window.show()
    sys.exit(app.exec())