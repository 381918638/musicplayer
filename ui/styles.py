DARK_THEME = """
/* ---- Global ---- */
QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}

/* ---- Main Window ---- */
QMainWindow {
    background-color: #1a1a2e;
    border: 1px solid #2a2a4a;
}

/* ---- Title Bar ---- */
#titleBar {
    background-color: #16162a;
    border-bottom: 1px solid #2a2a4a;
}
#titleLabel {
    font-size: 14px;
    font-weight: bold;
    color: #ffffff;
    padding-left: 12px;
}
#btnMin, #btnMax, #btnClose {
    background: transparent;
    border: none;
    color: #a0a0b0;
    font-size: 16px;
    padding: 4px 12px;
}
#btnMin:hover, #btnMax:hover {
    background-color: #2a2a4a;
    color: #ffffff;
}
#btnClose:hover {
    background-color: #e81123;
    color: #ffffff;
}

/* ---- Search Bar ---- */
#searchBar {
    background-color: #222240;
    border: 2px solid #2a2a4a;
    border-radius: 20px;
    padding: 6px 16px;
    color: #e0e0e0;
    font-size: 14px;
}
#searchBar:focus {
    border-color: #6c63ff;
}
#btnSearch {
    background-color: #6c63ff;
    color: #ffffff;
    border: none;
    border-radius: 16px;
    padding: 8px 24px;
    font-size: 14px;
    font-weight: bold;
}
#btnSearch:hover {
    background-color: #7b73ff;
}
#btnSearch:pressed {
    background-color: #5a52e0;
}

/* ---- Buttons ---- */
QPushButton {
    background-color: #2a2a4a;
    color: #e0e0e0;
    border: 1px solid #3a3a5a;
    border-radius: 6px;
    padding: 6px 16px;
}
QPushButton:hover {
    background-color: #3a3a5a;
    border-color: #6c63ff;
}
QPushButton:pressed {
    background-color: #4a4a6a;
}

/* ---- Playback Controls ---- */
#controlBar {
    background-color: #16162a;
    border-top: 1px solid #2a2a4a;
    border-bottom: 1px solid #2a2a4a;
}
#btnControl {
    background: transparent;
    border: none;
    color: #c0c0d0;
    font-size: 20px;
    padding: 8px 12px;
    border-radius: 20px;
}
#btnControl:hover {
    background-color: #2a2a4a;
    color: #ffffff;
}
#btnPlay {
    background-color: #6c63ff;
    border: none;
    color: #ffffff;
    font-size: 22px;
    padding: 10px 14px;
    border-radius: 24px;
}
#btnPlay:hover {
    background-color: #7b73ff;
}

/* ---- Progress Slider ---- */
QSlider::groove:horizontal {
    background: #2a2a4a;
    height: 6px;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #6c63ff;
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #7b73ff;
}
QSlider::sub-page:horizontal {
    background: #6c63ff;
    border-radius: 3px;
}

/* ---- Volume Slider ---- */
#volumeSlider::groove:horizontal {
    background: #2a2a4a;
    height: 4px;
    border-radius: 2px;
}
#volumeSlider::handle:horizontal {
    background: #a0a0b0;
    width: 10px;
    height: 10px;
    margin: -3px 0;
    border-radius: 5px;
}

/* ---- Lists & Tables ---- */
QListWidget, QTableWidget {
    background-color: #1e1e36;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
    outline: none;
    alternate-background-color: #222240;
}
QListWidget::item, QTableWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #252545;
}
QListWidget::item:selected, QTableWidget::item:selected {
    background-color: #3a3a6a;
    color: #ffffff;
}
QListWidget::item:hover, QTableWidget::item:hover {
    background-color: #2a2a4a;
}

/* ---- Table Header ---- */
QHeaderView::section {
    background-color: #16162a;
    color: #a0a0b0;
    padding: 8px 12px;
    border: none;
    border-bottom: 2px solid #2a2a4a;
    font-weight: bold;
}

/* ---- Scrollbar ---- */
QScrollBar:vertical {
    background: #1a1a2e;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #3a3a5a;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #6c63ff;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    height: 8px;
    background: #1a1a2e;
}
QScrollBar::handle:horizontal {
    background: #3a3a5a;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #6c63ff;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* ---- Labels ---- */
QLabel {
    color: #c0c0d0;
    background: transparent;
}
#songTitle {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
}
#songArtist {
    font-size: 14px;
    color: #a0a0b0;
}
#timeLabel {
    font-size: 12px;
    color: #808090;
}
#modeLabel {
    font-size: 13px;
    color: #6c63ff;
    font-weight: bold;
    padding: 4px 10px;
    background-color: #222240;
    border-radius: 4px;
}

/* ---- Tab Widget ---- */
QTabWidget::pane {
    background-color: #1e1e36;
    border: 1px solid #2a2a4a;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #16162a;
    color: #a0a0b0;
    padding: 8px 20px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    color: #6c63ff;
    border-bottom: 2px solid #6c63ff;
}
QTabBar::tab:hover {
    color: #c0c0d0;
}

/* ---- Menu ---- */
QMenu {
    background-color: #222240;
    border: 1px solid #3a3a5a;
    border-radius: 4px;
    padding: 4px;
}
QMenu::item {
    padding: 8px 32px 8px 16px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #3a3a6a;
}
QMenu::separator {
    height: 1px;
    background: #3a3a5a;
    margin: 4px 8px;
}

/* ---- ComboBox ---- */
QComboBox {
    background-color: #222240;
    border: 1px solid #3a3a5a;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e0e0e0;
}
QComboBox:hover {
    border-color: #6c63ff;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #222240;
    border: 1px solid #3a3a5a;
    selection-background-color: #3a3a6a;
}

/* ---- Progress Bar ---- */
QProgressBar {
    background-color: #2a2a4a;
    border: none;
    border-radius: 6px;
    height: 12px;
    text-align: center;
    font-size: 11px;
    color: #ffffff;
}
QProgressBar::chunk {
    background-color: #6c63ff;
    border-radius: 6px;
}

/* ---- Splitter ---- */
QSplitter::handle {
    background-color: #2a2a4a;
    width: 2px;
}

/* ---- Tooltip ---- */
QToolTip {
    background-color: #222240;
    color: #e0e0e0;
    border: 1px solid #3a3a5a;
    padding: 4px 8px;
    border-radius: 4px;
}
"""
