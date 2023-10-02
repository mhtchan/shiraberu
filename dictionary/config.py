import sys
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from dictionary.loader import load_dictionary, Dictionary, remove_dictionary, remove_all_dictionaries, update_dictionary_priority

class ConfigWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configure dictionary")

        self.save_button = QPushButton('Save changes',self)
        self.save_button.clicked.connect(self.save_button_clicked)
        self.file_browse_button = QPushButton('Import dictionary',self)
        self.file_browse_button.clicked.connect(self.browse_button_clicked)
        self.delete_all_button = QPushButton('Delete all dictionaries',self)
        self.delete_all_button.clicked.connect(self.delete_all_button_clicked)
        self.dictionaries_table = ReorderTableView(self)
        self.display_dictionaries_table()

        layout = QVBoxLayout()
        layout.setSpacing(2)
        
        horizontal_layout_1 = QHBoxLayout()
        horizontal_layout_2 = QHBoxLayout()
        
        horizontal_layout_1.addWidget(self.dictionaries_table)
        
        horizontal_layout_2.addWidget(self.save_button)
        horizontal_layout_2.addWidget(self.file_browse_button)
        horizontal_layout_2.addWidget(self.delete_all_button)
        
        layout.addLayout(horizontal_layout_1)
        layout.addLayout(horizontal_layout_2)
        
        widget = QWidget()
        widget.setLayout(layout)
        
        self.setCentralWidget(widget)

    def save_button_clicked(self):
        for i in range(self.dictionaries_table.model().rowCount()):
            dictionary_id = self.dictionaries_table.model().index(i, 0).data()
            new_priority = self.dictionaries_table.model().index(i, 1).data()
            update_dictionary_priority(dictionary_id, new_priority)

    def browse_button_clicked(self):
        file_name, _ = QFileDialog.getOpenFileName(self,"Choose file","","zip (*.zip)")
        if file_name:
            load_dictionary(file_name)
            self.display_dictionaries_table()
        
    def delete_all_button_clicked(self):
        message_box = QMessageBox()
        message_box.setText("Remove all loaded dictionaries?")
        message_box.setWindowTitle("Confirm")
        message_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        
        return_value = message_box.exec()
        if return_value == QMessageBox.StandardButton.Ok:
            remove_all_dictionaries()
            self.display_dictionaries_table()

    def display_dictionaries_table(self):
        self.dictionaries = Dictionary.select().order_by(Dictionary.priority.asc())
        try:
            self.dictionaries_table.setModel(ReorderTableModel(
                [[i.id, i.priority, i.title, i.revision] for i in self.dictionaries]
            ))
        except Exception as e:
            print(e)
        self.dictionaries_table.setColumnHidden(0, True)

class ReorderTableModel(QAbstractTableModel):
    def __init__(self, data, parent=None, *args):
        super().__init__(parent, *args)
        self._data = data

    def columnCount(self, parent=None) -> int:
        try:
            return len(self._data[0])
        except:
            return 0

    def rowCount(self, parent=None) -> int:
        return len(self._data)

    def headerData(self, column: int, orientation, role: Qt.ItemDataRole):
        return (('id','Priority', 'Title', 'Revision')[column]
                if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal
                else None)

    def data(self, index: QModelIndex, role: Qt.ItemDataRole):
        if not index.isValid() or role not in {Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole}:
            return None
        return (self._data[index.row()][index.column()])

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.EditRole:
            row = index.row()
            column = index.column()
            self._data[row][column] = value
            self.dataChanged.emit(index, index)
            return True
        return QAbstractTableModel.setData(self, index, value, role)

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        if index.row() < len(self._data):
            if index.column() in (1,2,3): #priority, title and revision are not editable
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled
            else:
                return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable

    def supportedDropActions(self) -> bool:
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction

    def relocateRow(self, row_source, row_target) -> None:
        row_a, row_b = max(row_source, row_target), min(row_source, row_target)
        self.beginMoveRows(QModelIndex(), row_a, row_a, QModelIndex(), row_b)
        self._data.insert(row_target, self._data.pop(row_source))
        self.endMoveRows()


class ReorderTableView(QTableView):
    """QTableView with the ability to make the model move a row with drag & drop"""

    class DropmarkerStyle(QProxyStyle):
        def drawPrimitive(self, element, option, painter, widget=None):
            """Draw a line across the entire row rather than just the column we're hovering over.
            This may not always work depending on global style - for instance I think it won't
            work on OSX."""
            if element == self.PrimitiveElement.PE_IndicatorItemViewItemDrop and not option.rect.isNull():
                option_new = QStyleOption(option)
                option_new.rect.setLeft(0)
                if widget:
                    option_new.rect.setRight(widget.width())
                option = option_new
            super().drawPrimitive(element, option, painter, widget)

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.verticalHeader().hide()
        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setSelectionMode(self.SelectionMode.SingleSelection)
        self.setDragDropMode(self.DragDropMode.InternalMove)
        self.setDragDropOverwriteMode(False)
        self.setStyle(self.DropmarkerStyle())

    def dropEvent(self, event):
        if (event.source() is not self or
            (event.dropAction() != Qt.DropAction.MoveAction and
             self.dragDropMode() != QAbstractItemView.DragDropMode.InternalMove)):
            super().dropEvent(event)

        selection = self.selectedIndexes()
        from_index = selection[0].row() if selection else -1
        to_index = self.indexAt(event.position().toPoint()).row()
        if (0 <= from_index < self.model().rowCount() and
            0 <= to_index < self.model().rowCount() and
            from_index != to_index):
            self.model().relocateRow(from_index, to_index)

            ## Selection should remain on the moved row
            self.clearSelection()
            for i in range(self.model().columnCount()):
                self.setSelection(self.visualRect(self.model().index(to_index,i)), QItemSelectionModel.SelectionFlag.Select)
            
            ## Reassign priorities
            for i in range(self.model().rowCount()):
                if self.model().setData(self.model().index(i,1), i+1):
                    self.model().dataChanged.emit(
                        self.model().index(0,1),
                        self.model().index(self.model().rowCount(),1)
                    )
            event.accept()
        super().dropEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.lastWindowClosed.connect(app.quit)
    w = ConfigWindow()
    w.show()
    app.exec()