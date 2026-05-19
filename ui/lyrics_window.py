import re

from PyQt5.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QFontMetrics, QCursor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMenu, QAction, QSizeGrip, QApplication,
)


class LyricsWidget(QWidget):
    """Custom widget that paints LRC lyrics with KTV fill + smooth animation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: list[tuple[float, str]] = []
        self._current_index = -1
        self._target_position: float = 0.0   # latest position from player
        self._display_position: float = 0.0  # smoothly interpolated position
        self._vertical = True
        self._font_size = 26
        self._played_color = QColor("#6c63ff")
        self._upcoming_color = QColor("#e0e0e0")
        self.setMinimumSize(300, 200)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Smooth animation timer — 30 FPS
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._anim_tick)
        self._anim_timer.start()

    def _anim_tick(self):
        """Smoothly interpolate display position towards target."""
        if abs(self._display_position - self._target_position) < 0.01:
            return  # nothing to do
        # Lerp: move 30% closer each frame → smooth exponential ease
        self._display_position += (self._target_position - self._display_position) * 0.3
        # Update current line index based on interpolated position
        new_idx = -1
        for i, (t, _) in enumerate(self._lines):
            if t <= self._display_position:
                new_idx = i
            else:
                break
        if new_idx != self._current_index:
            self._current_index = new_idx
        self.update()

    def set_orientation(self, vertical: bool):
        self._vertical = vertical
        self.update()

    def set_font_size(self, size: int):
        self._font_size = max(12, min(60, size))
        self.update()

    def set_lyrics(self, lrc_text: str):
        self._lines = self._parse_lrc(lrc_text)
        self._current_index = -1
        self._display_position = 0.0
        self._target_position = 0.0
        self.update()

    def set_position(self, seconds: float):
        """Receive position from player — smoothly animate towards it."""
        self._target_position = seconds

    def _parse_lrc(self, lrc_text: str) -> list[tuple[float, str]]:
        lines = []
        pattern = re.compile(r"\[(\d{2}):(\d{2})[\.:](\d{2,3})\]")
        for line in lrc_text.strip().split("\n"):
            matches = list(pattern.finditer(line))
            text = pattern.sub("", line).strip()
            if not text:
                continue
            for m in matches:
                minutes = int(m.group(1))
                seconds = int(m.group(2))
                frac = m.group(3)
                ms = int(frac) * 10 if len(frac) == 2 else int(frac)
                time_sec = minutes * 60 + seconds + ms / 1000.0
                lines.append((time_sec, text))
        lines.sort(key=lambda x: x[0])
        return lines

    def paintEvent(self, event):
        if not self._lines:
            return
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            if self._vertical:
                self._paint_vertical(painter)
            else:
                self._paint_horizontal(painter)

            painter.end()
        except Exception:
            pass

    def _line_progress(self, index: int) -> float:
        """Return how far through the lyric line we are, using smooth display position."""
        if index < 0 or index >= len(self._lines):
            return 0.0
        line_start = self._lines[index][0]
        if index + 1 < len(self._lines):
            line_end = self._lines[index + 1][0]
        else:
            line_end = line_start + 4.0
        if line_end <= line_start:
            return 1.0
        return max(0.0, min(1.0, (self._display_position - line_start) / (line_end - line_start)))

    def _draw_ktv_text(self, painter: QPainter, x: int, y: int, text: str,
                       progress: float, font: QFont, fill_color: QColor,
                       unfill_color: QColor, shadow: QColor):
        """Draw text with KTV fill effect — each portion gets its own shadow."""
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(text)
        fill_w = int(tw * progress)
        ascent = fm.ascent()
        h = fm.height() + 6

        def _draw_shadowed(tx, ty, t, col):
            """Draw text with 4-way shadow outline, then colored on top."""
            for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                painter.setFont(font)
                painter.setPen(QPen(shadow))
                painter.drawText(tx + dx, ty + dy, t)
            painter.setFont(font)
            painter.setPen(QPen(col))
            painter.drawText(tx, ty, t)

        if progress <= 0.0:
            _draw_shadowed(x, y, text, unfill_color)
        elif progress >= 1.0:
            _draw_shadowed(x, y, text, fill_color)
        else:
            # Filled portion — clipped to left fill_w pixels
            painter.save()
            painter.setClipRect(x - 2, y - ascent - 2, fill_w + 4, h)
            _draw_shadowed(x, y, text, fill_color)
            painter.restore()

            # Unfilled portion — clipped to right remaining pixels
            painter.save()
            painter.setClipRect(x + fill_w - 2, y - ascent - 2, tw - fill_w + 4, h)
            _draw_shadowed(x, y, text, unfill_color)
            painter.restore()

    def _paint_vertical(self, painter: QPainter):
        font = QFont("Microsoft YaHei", self._font_size)
        if not font.exactMatch():
            font = QFont("SimSun", self._font_size)
        fm = QFontMetrics(font)
        line_height = fm.height() + 10
        center_y = self.height() // 2
        shadow = QColor(0, 0, 0, 180)

        start = max(0, self._current_index - 4)
        end = min(len(self._lines), self._current_index + 6)

        for i in range(start, end):
            _t, text = self._lines[i]
            y = int(center_y + (i - self._current_index - 0.5) * line_height)
            text_width = fm.horizontalAdvance(text)
            x = int((self.width() - text_width) // 2)

            if i == self._current_index:
                # Background glow
                bg = QColor(self._played_color)
                bg.setAlpha(40)
                painter.fillRect(0, y - fm.ascent() - 2, self.width(), fm.height() + 6, bg)
                # KTV fill
                progress = self._line_progress(i)
                f = QFont("Microsoft YaHei", self._font_size + 2, QFont.Bold)
                self._draw_ktv_text(painter, x, y, text, progress, f,
                                    QColor(0, 229, 255),    # filled: bright cyan
                                    QColor(100, 100, 130),  # unfilled: dark gray
                                    shadow)
            elif i < self._current_index:
                c = self._played_color.darker(140)
                f = QFont("Microsoft YaHei", self._font_size - 2)
                for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                    painter.setFont(f)
                    painter.setPen(QPen(shadow))
                    painter.drawText(x + dx, y + dy, text)
                painter.setFont(f)
                painter.setPen(QPen(c))
                painter.drawText(x, y, text)
            else:
                alpha = max(30, 255 - abs(i - self._current_index) * 35)
                c = QColor(self._upcoming_color)
                c.setAlpha(alpha)
                f = QFont("Microsoft YaHei", self._font_size - 2)
                for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                    painter.setFont(f)
                    painter.setPen(QPen(shadow))
                    painter.drawText(x + dx, y + dy, text)
                painter.setFont(f)
                painter.setPen(QPen(c))
                painter.drawText(x, y, text)

    def _paint_horizontal(self, painter: QPainter):
        font = QFont("Microsoft YaHei", self._font_size)
        if not font.exactMatch():
            font = QFont("SimSun", self._font_size)
        fm = QFontMetrics(font)
        shadow = QColor(0, 0, 0, 180)

        if 0 <= self._current_index < len(self._lines):
            _, text = self._lines[self._current_index]
            tw = fm.horizontalAdvance(text)
            x = int((self.width() - tw) // 2)
            y = int(self.height() * 0.3)

            bg = QColor(self._played_color)
            bg.setAlpha(40)
            painter.fillRect(0, y - fm.ascent() - 2, self.width(), fm.height() + 6, bg)

            # KTV fill for current line
            progress = self._line_progress(self._current_index)
            f = QFont("Microsoft YaHei", self._font_size + 2, QFont.Bold)
            self._draw_ktv_text(painter, x, y, text, progress, f,
                                QColor(0, 229, 255),
                                QColor(100, 100, 130),
                                shadow)

            # Next line preview
            if self._current_index + 1 < len(self._lines):
                _, next_text = self._lines[self._current_index + 1]
                ntw = fm.horizontalAdvance(next_text)
                nx = int((self.width() - ntw) // 2)
                ny = int(self.height() * 0.65)
                c = QColor(self._upcoming_color)
                c.setAlpha(100)
                f2 = QFont("Microsoft YaHei", self._font_size - 3)
                for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                    painter.setFont(f2)
                    painter.setPen(QPen(shadow))
                    painter.drawText(nx + dx, ny + dy, next_text)
                painter.setFont(f2)
                painter.setPen(QPen(c))
                painter.drawText(nx, ny, next_text)


class LyricsWindow(QWidget):
    """Frameless, always-on-top desktop lyrics overlay."""
    closed = pyqtSignal()

    def __init__(self):
        super().__init__(None)
        self.setWindowTitle("桌面歌词")
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(800, 500)

        self._drag_pos: QPoint | None = None
        self._resizing = False
        self._vertical = True
        self._font_size = 26

        self._setup_ui()
        self._load_position()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        # Top bar
        bar = QWidget()
        bar.setFixedHeight(26)
        bar.setStyleSheet("background: rgba(0,0,0,60); border-radius: 6px;")
        bar.setCursor(Qt.SizeAllCursor)

        bl = QHBoxLayout(bar)
        bl.setContentsMargins(8, 0, 4, 0)
        bl.setSpacing(4)

        title = QLabel("🎵 桌面歌词")
        title.setStyleSheet("color: #a0a0b0; font-size: 11px; background: transparent;")

        btn_close = QPushButton("×")
        btn_close.setFixedSize(20, 20)
        btn_close.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,20); border: none; "
            "border-radius: 10px; color: #ccc; font-size: 14px; }"
            "QPushButton:hover { background: #e81123; color: white; }"
        )
        btn_close.clicked.connect(self.hide)
        btn_close.setCursor(Qt.PointingHandCursor)

        bl.addWidget(title)
        bl.addStretch()
        bl.addWidget(btn_close)

        # Lyrics display area
        self._lyrics_widget = LyricsWidget()
        self._lyrics_widget.setStyleSheet("background: transparent;")

        # Size grip for resizing
        grip = QSizeGrip(self)
        grip.setFixedSize(16, 16)
        grip.setStyleSheet("background: transparent;")
        grip.setCursor(Qt.SizeFDiagCursor)
        grip_layout = QHBoxLayout()
        grip_layout.addStretch()
        grip_layout.addWidget(grip)

        layout.addWidget(bar)
        layout.addWidget(self._lyrics_widget, 1)
        layout.addLayout(grip_layout)

    def _on_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #222240; border: 1px solid #3a3a5a; border-radius: 4px; }"
            "QMenu::item { padding: 8px 24px; color: #e0e0e0; }"
            "QMenu::item:selected { background-color: #3a3a6a; }"
        )

        orient_action = menu.addAction(
            "📝 切换为横向" if self._vertical else "📝 切换为竖向"
        )
        orient_action.triggered.connect(self._toggle_orientation)

        menu.addSeparator()

        bigger = menu.addAction("🔍 字体放大")
        bigger.triggered.connect(lambda: self._change_font_size(2))

        smaller = menu.addAction("🔎 字体缩小")
        smaller.triggered.connect(lambda: self._change_font_size(-2))

        menu.addSeparator()

        bigger_win = menu.addAction("⬛ 窗口放大")
        bigger_win.triggered.connect(lambda: self.resize(
            int(self.width() * 1.15), int(self.height() * 1.15)))

        smaller_win = menu.addAction("⬜ 窗口缩小")
        smaller_win.triggered.connect(lambda: self.resize(
            int(self.width() * 0.85), int(self.height() * 0.85)))

        menu.exec_(self.mapToGlobal(pos))

    def _toggle_orientation(self):
        self._vertical = not self._vertical
        self._lyrics_widget.set_orientation(self._vertical)
        if self._vertical:
            self.resize(800, 500)
        else:
            self.resize(900, 140)
        self._save_state()

    def _change_font_size(self, delta: int):
        self._font_size += delta
        self._lyrics_widget.set_font_size(self._font_size)
        self._save_state()

    def set_lyrics(self, lrc_text: str):
        self._lyrics_widget.set_lyrics(lrc_text)

    def set_position(self, seconds: float):
        self._lyrics_widget.set_position(seconds)

    # ---- Drag ----

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            delta = event.globalPos() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = None
            self._save_state()

    # ---- Persistence ----

    def _save_state(self):
        from models.playlist_manager import PlaylistManager
        pm = PlaylistManager()
        pm.set_setting("lyrics_x", str(self.x()))
        pm.set_setting("lyrics_y", str(self.y()))
        pm.set_setting("lyrics_w", str(self.width()))
        pm.set_setting("lyrics_h", str(self.height()))
        pm.set_setting("lyrics_vertical", "1" if self._vertical else "0")
        pm.set_setting("lyrics_font_size", str(self._font_size))

    def _load_position(self):
        from models.playlist_manager import PlaylistManager
        pm = PlaylistManager()
        x = int(pm.get_setting("lyrics_x", "100"))
        y = int(pm.get_setting("lyrics_y", "100"))
        w = int(pm.get_setting("lyrics_w", "800"))
        h = int(pm.get_setting("lyrics_h", "500"))
        self._vertical = pm.get_setting("lyrics_vertical", "1") == "1"
        self._font_size = int(pm.get_setting("lyrics_font_size", "26"))
        self.move(x, y)
        self.resize(w, h)
        self._lyrics_widget.set_orientation(self._vertical)
        self._lyrics_widget.set_font_size(self._font_size)

    def closeEvent(self, event):
        self._save_state()
        self.closed.emit()
        super().closeEvent(event)
