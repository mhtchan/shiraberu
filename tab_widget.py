import sys
from collections import deque
from PyQt6.QtWidgets import (
    QApplication
    ,QMainWindow
    ,QTabWidget
    ,QToolButton
    ,QTabBar
    ,QStyleOptionTab
    ,QStyle
    ,QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFontDatabase, QFont, QAction, QCursor
from PyQt6.QtWebEngineWidgets import QWebEngineView


class MainWindow(QMainWindow):  
    def __init__(self):
        super().__init__()
        self.tab_widget = ShrinkTabWidget()
        self.setCentralWidget(self.tab_widget)

class ShrinkTabBar(QTabBar):
    _widthHint = -1
    _initialized = False
    _recursiveCheck = False
    addClicked = pyqtSignal()
    def __init__(self, parent):
        super().__init__(parent)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setExpanding(False)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDrawBase(False)
        self.tabCloseRequested.connect(lambda x: self.parent()._tabClosed(x))
        self.addButton = QToolButton(self.parent(), text='+')
        self.addButton.clicked.connect(self.addClicked)
        self._recursiveTimer = QTimer(singleShot=True, timeout=self._unsetRecursiveCheck, interval=0)
        self._closeIconTimer = QTimer(singleShot=True, timeout=self._updateClosable, interval=0)
        
        _id = QFontDatabase.addApplicationFont("font/NotoSansJP-Regular.otf")
        _fontstr = QFontDatabase.applicationFontFamilies(_id)[0]
        self._font = QFont(_fontstr, 10)
        self.setFont(self._font)

        ## Context menu
        self.context_menu = QMenu()
        self.context_menu_close = QAction("Close")
        self.context_menu_close_others = QAction("Close other tabs")
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu)
        self.context_menu_close.triggered.connect(self.context_menu_tab_close)
        self.context_menu_close_others.triggered.connect(self.context_menu_tab_close_others)
    
    def on_context_menu(self, pos):
        self.context_menu.addAction(self.context_menu_close)
        self.context_menu.addAction(self.context_menu_close_others)
        self.global_cursor_pos = QCursor.pos()
        self.context_menu.exec(self.global_cursor_pos)
    
    def _get_tab_index(self):
        # Returns tab index of clicked tab from right click
        pos_local = self.mapFromGlobal(self.global_cursor_pos)
        for i in range(self.count()):
            if self.tabRect(i).contains(pos_local):
                break
        return i
    
    def context_menu_tab_close(self):
        self.parent()._tabClosed(self._get_tab_index())
                
    def context_menu_tab_close_others(self):
        total_tabs = self.count()
        clicked_tab_index = self._get_tab_index()
        for _ in range(clicked_tab_index):
            self.parent()._tabClosed(0)
        for _ in range(clicked_tab_index+1,total_tabs):
            self.parent()._tabClosed(1)
    
    def _unsetRecursiveCheck(self):
        self._recursiveCheck = False

    def _updateClosable(self):
        if self._baseWidth < self._minimumCloseWidth:
            for i in range(self.count()):
                if i == self.currentIndex():
                    self.tabButton(i, QTabBar.ButtonPosition.RightSide).show()
                    continue
                self.tabButton(i, QTabBar.ButtonPosition.RightSide).hide()
        else:
            for i in range(self.count()):
                self.tabButton(i, QTabBar.ButtonPosition.RightSide).show()

    def _computeHints(self):
        if self.count() > 1:
            return
        self._recursiveCheck = True

        opt = QStyleOptionTab()
        self.initStyleOption(opt, 0)
        width = self.style().pixelMetric(QStyle.PixelMetric.PM_TabBarTabHSpace, opt, self)
        iconWidth = self.iconSize().width() + 4
        self._minimumWidth = width + iconWidth

        # default text widths are arbitrary
        fm = self.fontMetrics()
        self._minimumCloseWidth = self._minimumWidth + fm.horizontalAdvance('x' * 7) + iconWidth
        self._defaultWidth = width + fm.horizontalAdvance('x' * 17)
        self._defaultHeight = super().tabSizeHint(0).height()
        self._minimumHint = QSize(self._minimumWidth, self._defaultHeight)
        self._tabHint = {0: QSize(self._defaultWidth, self._defaultHeight)}

        self._initialized = True
        self._recursiveTimer.start()

    def _updateSize(self):
        if not self.count():
            return
        frameWidth = self.style().pixelMetric(
            QStyle.PixelMetric.PM_DefaultFrameWidth, None, self.parent())
        buttonWidth = self.addButton.sizeHint().width()
        self._baseWidth = (self.parent().width() - frameWidth - buttonWidth) // self.count()
        self._remainderWidth = (self.parent().width() - frameWidth - buttonWidth) % self.count()
        
        # If the tabs fill the bar, and if _baseWidth doesn't divide evenly, then spread the remainder n pixels to the last n tabs
        if self._defaultWidth <= self._baseWidth:
            self._tabHint = {
                k: QSize(self._defaultWidth, self._defaultHeight)
                for k in range(self.count())
            }
        else:
            self._tabHint = {
                k: QSize((self._baseWidth+1 if k in range(self.count()-self._remainderWidth,self.count()) else self._baseWidth), self._defaultHeight)
                for k in range(self.count())
            }

        # dirty trick to ensure that the layout is updated
        if not self._recursiveCheck:
            self._recursiveCheck = True
            self.setIconSize(self.iconSize())
            self._recursiveTimer.start()

    def minimumTabSizeHint(self, index):
        if not self._initialized:
            self._computeHints()
        return self._minimumHint

    def tabSizeHint(self, index):
        if not self._initialized:
            self._computeHints()
        self._updateSize()
        self._closeIconTimer.start()
        return self._tabHint[index]

    def tabLayoutChange(self):
        if self.count() and not self._recursiveCheck:
            self._updateSize()
            self._closeIconTimer.start()

    def tabRemoved(self, index):
        if not self.count():
            self.addButton.setGeometry(1, 2, 
                self.addButton.sizeHint().width(), self.height() - 4)

    def resizeEvent(self, event):
        if not self.count():
            super().resizeEvent(event)
            return
        self._recursiveCheck = True
        super().resizeEvent(event)
        height = self.sizeHint().height()
        if height < 0:
            # a tab bar without tabs returns an invalid size
            height = self.addButton.height()
        self.addButton.setGeometry(self.geometry().right() + 1, 2, 
            self.addButton.sizeHint().width(), height - 4)
        self._closeIconTimer.start()
        self._recursiveTimer.start()


class ShrinkTabWidget(QTabWidget):
    def __init__(self, display_window=QWebEngineView):
        super().__init__()
        self._tabBar = ShrinkTabBar(self)
        self.removedTabs = deque()
        self.setTabBar(self._tabBar)
        self._tabBar.addClicked.connect(self._addTab)
        self.display_window = display_window
        if display_window is not None:
            self._addTab()

    def resizeEvent(self, event):
        self._tabBar._updateSize()
        super().resizeEvent(event)

    def _addTab(self, tab_title="New Tab", tab_from_lookup=False, insert_at_position=None):
        if not tab_from_lookup:
            self.addTab(self.display_window(self), tab_title)
            self.setCurrentIndex(self.count()-1)
        else:
            idx = self.insertTab(insert_at_position, self.display_window(self), tab_title)
            self.setCurrentIndex(idx)
            return idx
        
    def _tabClosed(self, index):
        self.removedTabs.append({"index": index, "widget": self.widget(index)})
        self.removeTab(index)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())