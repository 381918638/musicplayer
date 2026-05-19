"""
MusicPlayer - 全功能音乐播放器
"""
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Suppress pygame banner
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QPen


def _create_splash_pixmap() -> QPixmap:
    """Create a quick splash image programmatically (no file dependency)."""
    pm = QPixmap(420, 260)
    pm.fill(QColor("#1a1a2e"))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)

    # App title
    font_title = QFont("Microsoft YaHei", 26, QFont.Bold)
    painter.setFont(font_title)
    painter.setPen(QPen(QColor("#6c63ff")))
    painter.drawText(0, 80, pm.width(), 50, Qt.AlignCenter, "Music Player")

    # Subtitle
    font_sub = QFont("Microsoft YaHei", 12)
    painter.setFont(font_sub)
    painter.setPen(QPen(QColor("#a0a0b0")))
    painter.drawText(0, 130, pm.width(), 30, Qt.AlignCenter, "正在启动...")

    # Simple music note
    font_note = QFont("Microsoft YaHei", 48)
    painter.setFont(font_note)
    painter.setPen(QPen(QColor("#6c63ff")))
    painter.drawText(0, 40, pm.width(), 60, Qt.AlignCenter, "🎵")

    painter.end()
    return pm


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("MusicPlayer")
    app.setApplicationVersion("1.0.0")
    app.setFont(QFont("Microsoft YaHei", 10))
    app.setStyle("Fusion")

    # ---- Splash screen (appears instantly) ----
    splash = QSplashScreen(_create_splash_pixmap())
    splash.show()
    app.processEvents()

    # ---- Heavy imports after splash is visible ----
    from ui.main_window import MainWindow

    window = MainWindow()

    # Close splash, show main window
    splash.finish(window)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
