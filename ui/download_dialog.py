from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QWidget,
)

from engine.download_manager import DownloadManager
from models.song import Song


class DownloadDialog(QDialog):
    def __init__(self, song: Song, download_manager: DownloadManager, parent=None):
        super().__init__(parent)
        self._song = song
        self._download_manager = download_manager
        self._downloaded_path: str | None = None
        self._drag_pos: QPoint | None = None

        self.setWindowTitle("下载歌曲")
        self.setFixedSize(420, 220)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setStyleSheet(
            "QDialog { background-color: #1e1e36; border: 2px solid #3a3a5a; border-radius: 10px; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 8, 16, 16)

        # Custom title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(28)
        title_bar.setCursor(Qt.SizeAllCursor)
        title_bar.mousePressEvent = self._title_press
        title_bar.mouseMoveEvent = self._title_move
        title_bar.mouseReleaseEvent = self._title_release
        tl = QHBoxLayout(title_bar)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(QLabel("  下载歌曲"))
        tl.addStretch()
        btn_close = QPushButton("×")
        btn_close.setFixedSize(22, 22)
        btn_close.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #a0a0b0; font-size: 16px; }"
            "QPushButton:hover { background: #e81123; color: white; border-radius: 11px; }"
        )
        btn_close.clicked.connect(self.reject)
        tl.addWidget(btn_close)
        layout.addWidget(title_bar)

        # Info
        layout.addWidget(QLabel(f"歌曲: {self._song.display_name}"))
        artist_lbl = QLabel(f"歌手: {self._song.artist or '未知'}")
        artist_lbl.setStyleSheet("color: #a0a0b0; font-size: 12px;")
        layout.addWidget(artist_lbl)

        # Progress
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #808090; font-size: 12px;")
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_cancel = QPushButton("取消")
        self._btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_cancel)

        self._btn_download = QPushButton("开始下载")
        self._btn_download.setStyleSheet(
            "QPushButton { background-color: #6c63ff; color: white; font-weight: bold; "
            "border: none; border-radius: 6px; padding: 8px 20px; }"
            "QPushButton:hover { background-color: #7b73ff; }"
        )
        self._btn_download.clicked.connect(self._start_download)
        btn_layout.addWidget(self._btn_download)

        layout.addLayout(btn_layout)

    def _title_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos()

    def _title_move(self, event):
        if self._drag_pos is not None:
            delta = event.globalPos() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPos()

    def _title_release(self, event):
        self._drag_pos = None

    def _connect_signals(self):
        self._download_manager.download_progress.connect(self._on_progress)
        self._download_manager.download_finished.connect(self._on_finished)
        self._download_manager.download_error.connect(self._on_error)

    def _start_download(self):
        self._btn_download.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._btn_cancel.setText("取消下载")
        self._download_manager.download(self._song)

    def _on_progress(self, pct: float, status: str):
        self._progress_bar.setValue(int(pct))
        self._status_label.setText(status)

    def _on_finished(self, file_path: str):
        self._downloaded_path = file_path
        self._status_label.setText(f"已保存: {file_path}")
        self._status_label.setStyleSheet("color: #4caf50; font-size: 12px;")
        self._btn_cancel.setText("下载完成，即将关闭...")
        self._btn_cancel.setEnabled(False)
        # Auto-close after 1.5 seconds
        QTimer.singleShot(1500, self.accept)

    def _on_error(self, error: str):
        self._status_label.setText(error)
        self._status_label.setStyleSheet("color: #e81123; font-size: 12px;")
        self._btn_download.setEnabled(True)
        self._btn_cancel.setText("关闭")

    @property
    def downloaded_path(self) -> str | None:
        return self._downloaded_path

    def reject(self):
        self._download_manager.cancel()
        super().reject()
