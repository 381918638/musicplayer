"""Custom frameless dialogs to replace native Windows dialogs."""
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QWidget,
)


class _FramelessDialog(QDialog):
    """Base frameless dialog with custom title bar."""
    def __init__(self, parent=None, title: str = ""):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self._drag_pos: QPoint | None = None
        self.setStyleSheet(
            "QDialog { background-color: #1e1e36; border: 2px solid #3a3a5a; border-radius: 10px; }"
            "QLabel { color: #e0e0e0; background: transparent; }"
            "QLineEdit { background-color: #222240; border: 1px solid #3a3a5a; "
            "border-radius: 4px; padding: 6px 10px; color: #e0e0e0; }"
            "QPushButton { background-color: #2a2a4a; color: #e0e0e0; border: none; "
            "border-radius: 4px; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #3a3a5a; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 6, 14, 14)

        # Title bar
        bar = QWidget()
        bar.setFixedHeight(26)
        bar.setCursor(Qt.SizeAllCursor)
        bar.mousePressEvent = self._bar_press
        bar.mouseMoveEvent = self._bar_move
        bar.mouseReleaseEvent = self._bar_release
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 0, 0, 0)
        bl.addWidget(QLabel(title))
        bl.addStretch()
        btn = QPushButton("×")
        btn.setFixedSize(22, 22)
        btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #a0a0b0; font-size: 16px; }"
            "QPushButton:hover { background: #e81123; color: white; border-radius: 11px; }"
        )
        btn.clicked.connect(self.reject)
        bl.addWidget(btn)
        layout.addWidget(bar)

        self._content_layout = layout

    def _bar_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos()
    def _bar_move(self, event):
        if self._drag_pos is not None:
            self.move(self.pos() + event.globalPos() - self._drag_pos)
            self._drag_pos = event.globalPos()
    def _bar_release(self, event):
        self._drag_pos = None


class ConfirmDialog(_FramelessDialog):
    """Frameless Yes/No confirmation dialog."""
    def __init__(self, parent=None, title: str = "确认", message: str = ""):
        super().__init__(parent, title)
        self.setFixedSize(380, 160)
        self._result = False

        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("padding: 8px 0;")
        self._content_layout.addWidget(lbl)
        self._content_layout.addStretch()

        bl = QHBoxLayout()
        bl.addStretch()
        btn_no = QPushButton("取消")
        btn_no.clicked.connect(self.reject)
        bl.addWidget(btn_no)
        btn_yes = QPushButton("确定")
        btn_yes.setStyleSheet(
            "QPushButton { background-color: #6c63ff; color: white; font-weight: bold; "
            "border: none; border-radius: 4px; padding: 6px 20px; }"
            "QPushButton:hover { background-color: #7b73ff; }"
        )
        btn_yes.clicked.connect(self._accept)
        bl.addWidget(btn_yes)
        self._content_layout.addLayout(bl)

    def _accept(self):
        self._result = True
        self.accept()

    @property
    def confirmed(self) -> bool:
        return self._result


class InputDialog(_FramelessDialog):
    """Frameless text input dialog."""
    def __init__(self, parent=None, title: str = "输入", label: str = "", text: str = ""):
        super().__init__(parent, title)
        self.setFixedSize(380, 170)
        self._text = text

        lbl = QLabel(label)
        self._content_layout.addWidget(lbl)

        self._input = QLineEdit(text)
        self._input.selectAll()
        self._content_layout.addWidget(self._input)

        self._content_layout.addStretch()

        bl = QHBoxLayout()
        bl.addStretch()
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        bl.addWidget(btn_cancel)
        btn_ok = QPushButton("确定")
        btn_ok.setStyleSheet(
            "QPushButton { background-color: #6c63ff; color: white; font-weight: bold; "
            "border: none; border-radius: 4px; padding: 6px 20px; }"
            "QPushButton:hover { background-color: #7b73ff; }"
        )
        btn_ok.clicked.connect(self._accept)
        bl.addWidget(btn_ok)
        self._content_layout.addLayout(bl)

    def _accept(self):
        self._text = self._input.text()
        self.accept()

    @property
    def value(self) -> str:
        return self._text
