import os
import requests

from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QFont, QColor, QMouseEvent
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSlider, QStyle, QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSplitter, QMenu, QFileDialog, QMessageBox, QFrame, QApplication,
)

from engine.audio_player import AudioPlayer, PlayMode, PlayerState
from engine.search_engine import SearchEngine
from engine.download_manager import DownloadManager
from engine.lyrics_fetcher import LyricsFetcher
from engine.myhkw_api import MyHKWAPI
from models.playlist_manager import PlaylistManager
from models.song import Song
from ui.lyrics_window import LyricsWindow
from ui.styles import DARK_THEME
from ui.custom_dialogs import ConfirmDialog, InputDialog
from utils.helpers import format_time

MODE_LABELS = {
    PlayMode.SEQUENTIAL: "顺序",
    PlayMode.RANDOM: "随机",
    PlayMode.LOOP_ONE: "单曲循环",
    PlayMode.LOOP_ALL: "列表循环",
}

ROLE_TYPE = Qt.UserRole      # "all", "downloads", "playlist"
ROLE_ID = Qt.UserRole + 1    # playlist_id or -1
ROLE_SONG = Qt.UserRole + 2  # Song.to_dict()


class SeekSlider(QSlider):
    """Slider that seeks on click anywhere on the groove."""
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            # Map click position to slider value
            val = QStyle.sliderValueFromPosition(
                self.minimum(), self.maximum(),
                event.x(), self.width()
            )
            self.setValue(val)
            # Emit the sliderMoved signal so the parent can seek
            self.sliderMoved.emit(val)
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MusicPlayer")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Core engines
        self._player = AudioPlayer(self)
        self._search_engine = SearchEngine(self)
        self._download_manager = DownloadManager(self)
        self._lyrics_fetcher = LyricsFetcher(self)
        self._playlist_mgr = PlaylistManager()

        # State
        self._search_results: list[Song] = []
        self._current_view: str = "all"   # "all", "downloads", "playlist"
        self._current_playlist_id: int = -1
        self._is_seeking = False
        self._is_dragging_title = False
        self._drag_start_pos: QPoint | None = None
        self._lyrics_fetch_for_song_id: str = ""

        # Download tasks (session-only)
        self._download_tasks: list[dict] = []  # {song, pct, status, speed, elapsed, remaining}

        # Init UI
        self._setup_ui()
        self._apply_style()
        self._connect_signals()
        self._load_user_state()

        # Lyrics window
        self._lyrics_window = LyricsWindow()

        # Periodic UI tick
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(250)
        self._ui_timer.timeout.connect(self._on_ui_tick)
        self._ui_timer.start()

    # ============================================================
    #  UI Setup
    # ============================================================

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._create_title_bar())
        main_layout.addWidget(self._create_search_bar())

        # Main content: left panel + right panel
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.addWidget(self._create_left_panel())

        # Right: now-playing + song table
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._create_now_playing())

        # Section label
        self._section_label = QLabel("  全部歌曲")
        self._section_label.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #ffffff; "
            "padding: 8px 16px; background-color: #1e1e36;"
        )
        rl.addWidget(self._section_label)

        self._song_table = self._create_song_table()
        rl.addWidget(self._song_table, 1)

        self._splitter.addWidget(right)
        self._splitter.setSizes([240, 860])
        main_layout.addWidget(self._splitter, 1)
        main_layout.addWidget(self._create_status_bar())

    def _create_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(36)
        bar.mousePressEvent = self._title_mouse_press
        bar.mouseMoveEvent = self._title_mouse_move
        bar.mouseReleaseEvent = self._title_mouse_release
        bar.mouseDoubleClickEvent = self._title_double_click

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        icon_lbl = QLabel("  🎵")
        icon_lbl.setStyleSheet("font-size: 16px; background: transparent;")
        layout.addWidget(icon_lbl)

        title_lbl = QLabel("  MusicPlayer")
        title_lbl.setObjectName("titleLabel")
        layout.addWidget(title_lbl)
        layout.addStretch()

        for obj_name, text in [("btnMin", "−"), ("btnMax", "□"), ("btnClose", "×")]:
            btn = QPushButton(text)
            btn.setObjectName(obj_name)
            btn.setFixedSize(44, 36)
            layout.addWidget(btn)
            if obj_name == "btnMin":
                btn.clicked.connect(self.showMinimized)
            elif obj_name == "btnMax":
                btn.clicked.connect(self._toggle_maximize)
            elif obj_name == "btnClose":
                btn.clicked.connect(self.close)

        return bar

    def _create_search_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(52)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("searchBar")
        self._search_input.setPlaceholderText("搜索歌曲、歌手...")
        self._search_input.returnPressed.connect(self._on_search)
        layout.addWidget(self._search_input, 1)

        self._btn_search = QPushButton("🔍 搜索")
        self._btn_search.setObjectName("btnSearch")
        self._btn_search.clicked.connect(self._on_search)
        layout.addWidget(self._btn_search)

        self._btn_import = QPushButton("📁 导入")
        self._btn_import.setToolTip("导入本地音乐文件")
        self._btn_import.clicked.connect(self._on_import_local)
        layout.addWidget(self._btn_import)

        return bar

    def _create_left_panel(self) -> QWidget:
        """Left panel with accordion-style playlist tree."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 4, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel("🎶 我的歌单")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        header.addWidget(title)
        header.addStretch()
        btn_add = QPushButton("＋")
        btn_add.setFixedSize(28, 28)
        btn_add.setToolTip("新建歌单")
        btn_add.clicked.connect(self._on_create_playlist)
        header.addWidget(btn_add)
        layout.addLayout(header)

        self._left_tree = QTreeWidget()
        self._left_tree.setHeaderHidden(True)
        self._left_tree.setIndentation(16)
        self._left_tree.setRootIsDecorated(True)
        self._left_tree.setAnimated(True)
        self._left_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._left_tree.customContextMenuRequested.connect(self._on_playlist_context_menu)
        self._left_tree.itemClicked.connect(self._on_left_item_clicked)

        layout.addWidget(self._left_tree, 1)

        # Download task list (below playlists)
        dl_header = QLabel("⬇ 下载任务")
        dl_header.setStyleSheet(
            "font-size: 12px; font-weight: bold; color: #a0a0b0; "
            "padding: 4px 0 2px 0; background: transparent;"
        )
        layout.addWidget(dl_header)

        self._download_list = QTreeWidget()
        self._download_list.setHeaderHidden(True)
        self._download_list.setIndentation(0)
        self._download_list.setRootIsDecorated(False)
        self._download_list.setFixedHeight(160)
        self._download_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._download_list.customContextMenuRequested.connect(self._on_download_context_menu)
        self._download_list.setStyleSheet(
            "QTreeWidget { background-color: #16162a; border: 1px solid #2a2a4a; border-radius: 4px; }"
        )
        layout.addWidget(self._download_list)

        return panel

    def _create_now_playing(self) -> QWidget:
        widget = QWidget()
        widget.setObjectName("nowPlaying")
        widget.setFixedHeight(170)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(16)

        # Cover art
        self._cover_label = QLabel("🎵")
        self._cover_label.setFixedSize(130, 130)
        self._cover_label.setAlignment(Qt.AlignCenter)
        self._cover_label.setFont(QFont("Microsoft YaHei", 36))
        self._cover_label.setStyleSheet("background-color: #222240; border-radius: 8px;")
        layout.addWidget(self._cover_label)

        # Right side: info + progress + controls
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 6, 0, 2)
        rl.setSpacing(4)

        self._song_title_label = QLabel("未在播放")
        self._song_title_label.setObjectName("songTitle")
        rl.addWidget(self._song_title_label)

        self._song_artist_label = QLabel("选择一首歌曲开始播放")
        self._song_artist_label.setObjectName("songArtist")
        rl.addWidget(self._song_artist_label)

        rl.addStretch()

        # Progress
        prog = QHBoxLayout()
        self._time_cur = QLabel("0:00")
        self._time_cur.setObjectName("timeLabel")
        self._time_cur.setFixedWidth(44)
        prog.addWidget(self._time_cur)

        self._progress_slider = SeekSlider(Qt.Horizontal)
        self._progress_slider.setRange(0, 1000)
        self._progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self._progress_slider.sliderMoved.connect(self._on_slider_moved)
        self._progress_slider.sliderReleased.connect(self._on_slider_released)
        prog.addWidget(self._progress_slider, 1)

        self._time_total = QLabel("0:00")
        self._time_total.setObjectName("timeLabel")
        self._time_total.setFixedWidth(44)
        self._time_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        prog.addWidget(self._time_total)
        rl.addLayout(prog)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.setSpacing(6)

        ctrl.addStretch()

        # Mode
        self._mode_btn = QPushButton("🔁")
        self._mode_btn.setToolTip("顺序播放")
        self._mode_btn.setObjectName("btnControl")
        self._mode_btn.clicked.connect(self._on_cycle_mode)
        ctrl.addWidget(self._mode_btn)

        # Prev
        btn_prev = QPushButton("⏮")
        btn_prev.setObjectName("btnControl")
        btn_prev.clicked.connect(self._player.previous)
        ctrl.addWidget(btn_prev)

        # Play/Pause
        self._btn_play = QPushButton("▶")
        self._btn_play.setObjectName("btnPlay")
        self._btn_play.clicked.connect(self._on_play_pause)
        ctrl.addWidget(self._btn_play)

        # Next
        btn_next = QPushButton("⏭")
        btn_next.setObjectName("btnControl")
        btn_next.clicked.connect(self._player.next)
        ctrl.addWidget(btn_next)

        # Lyrics toggle
        self._lyrics_btn = QPushButton("📝")
        self._lyrics_btn.setToolTip("桌面歌词")
        self._lyrics_btn.setObjectName("btnControl")
        self._lyrics_btn.setCheckable(True)
        self._lyrics_btn.toggled.connect(self._on_toggle_lyrics)
        ctrl.addWidget(self._lyrics_btn)

        ctrl.addStretch()

        # Volume
        vol_label = QLabel("🔊")
        vol_label.setStyleSheet("font-size: 14px; background: transparent;")
        ctrl.addWidget(vol_label)

        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setObjectName("volumeSlider")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(70)
        self._volume_slider.setFixedWidth(100)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        ctrl.addWidget(self._volume_slider)

        rl.addLayout(ctrl)
        layout.addWidget(right, 1)
        return widget

    def _create_song_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["歌曲", "歌手", "专辑", "时长"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        table.setColumnWidth(3, 60)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.doubleClicked.connect(self._on_table_double_click)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self._on_table_context_menu)
        return table

    def _create_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(26)
        bar.setStyleSheet("background-color: #16162a; border-top: 1px solid #2a2a4a;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        self._status_label = QLabel("就绪")
        self._status_label.setStyleSheet("font-size: 11px; color: #808090; background: transparent;")
        layout.addWidget(self._status_label)
        layout.addStretch()
        return bar

    def _apply_style(self):
        self.setStyleSheet(DARK_THEME)

    def _connect_signals(self):
        self._player.position_changed.connect(self._on_position_changed)
        self._player.state_changed.connect(self._on_state_changed)
        self._player.song_changed.connect(self._on_song_changed)
        self._player.mode_changed.connect(self._on_mode_changed)
        self._player.error_occurred.connect(self._on_player_error)

        self._search_engine.result_found.connect(self._on_result_found)
        self._search_engine.search_finished.connect(self._on_search_finished)
        self._search_engine.search_error.connect(self._on_search_error)
        self._search_engine.search_progress.connect(self._on_search_progress)

        self._lyrics_fetcher.lyrics_ready.connect(self._on_lyrics_ready)
        self._lyrics_fetcher.lyrics_error.connect(self._on_lyrics_error)

        # Download task signals
        self._download_manager.task_added.connect(self._on_task_added)
        self._download_manager.task_progress.connect(self._on_task_progress)
        self._download_manager.task_finished.connect(self._on_task_finished)
        self._download_manager.task_error.connect(self._on_task_error)

    # ============================================================
    #  Load / Refresh
    # ============================================================

    def _load_user_state(self):
        self._rebuild_left_panel()
        songs = self._playlist_mgr.get_all_songs()
        if songs:
            self._populate_table(songs)
        vol = float(self._playlist_mgr.get_setting("volume", "0.7"))
        self._volume_slider.setValue(int(vol * 100))
        self._player.set_volume(vol)

    def _rebuild_left_panel(self):
        self._left_tree.clear()

        # "全部歌曲"
        all_item = QTreeWidgetItem(["📀 全部歌曲"])
        all_item.setData(0, ROLE_TYPE, "all")
        all_item.setData(0, ROLE_ID, -1)
        self._left_tree.addTopLevelItem(all_item)

        # "我的下载" with children
        dl_item = QTreeWidgetItem(["⬇ 我的下载"])
        dl_item.setData(0, ROLE_TYPE, "downloads")
        dl_item.setData(0, ROLE_ID, -2)
        dl_songs = [s for s in self._playlist_mgr.get_all_songs()
                    if s.file_path]
        for s in dl_songs:
            label = s.title[:30]
            if not os.path.exists(s.file_path):
                label += " [无效]"
            child = QTreeWidgetItem([f"  {label}"])
            child.setData(0, ROLE_TYPE, "song")
            child.setData(0, ROLE_SONG, s.to_dict())
            dl_item.addChild(child)
        self._left_tree.addTopLevelItem(dl_item)

        # Playlists
        for pl in self._playlist_mgr.get_all_playlists():
            pl_item = QTreeWidgetItem([f"📋 {pl['name']}"])
            pl_item.setData(0, ROLE_TYPE, "playlist")
            pl_item.setData(0, ROLE_ID, pl["id"])
            songs = self._playlist_mgr.get_playlist_songs(pl["id"])
            for s in songs:
                label = s.title[:30]
                if s.file_path and not os.path.exists(s.file_path):
                    label += " [无效]"
                child = QTreeWidgetItem([f"  {label}"])
                child.setData(0, ROLE_TYPE, "song")
                child.setData(0, ROLE_SONG, s.to_dict())
                pl_item.addChild(child)
            self._left_tree.addTopLevelItem(pl_item)

        # Select "全部歌曲" by default
        if self._left_tree.topLevelItemCount() > 0:
            self._left_tree.setCurrentItem(self._left_tree.topLevelItem(0))

    def _refresh_after_download(self):
        """Rebuild left panel and refresh current view."""
        self._rebuild_left_panel()
        if self._current_view == "downloads":
            songs = [s for s in self._playlist_mgr.get_all_songs()
                     if s.file_path and os.path.exists(s.file_path)]
            self._populate_table(songs)
            self._section_label.setText("  我的下载")

    # ============================================================
    #  Left panel interaction
    # ============================================================

    def _on_left_item_clicked(self, item: QTreeWidgetItem, column: int):
        typ = item.data(0, ROLE_TYPE)
        pid = item.data(0, ROLE_ID)

        if typ == "song":
            # Clicked a child song item — play it
            song_dict = item.data(0, ROLE_SONG)
            if song_dict:
                song = Song.from_dict(song_dict)
                if song.file_path and os.path.exists(song.file_path):
                    songs = self._get_current_song_list()
                    try:
                        idx = songs.index(song)
                        self._player.set_playlist(songs, idx)
                        self._player.play(idx)
                    except ValueError:
                        self._player.set_playlist([song], 0)
                        self._player.play(0)
            return

        if typ == "all":
            self._current_view = "all"
            self._current_playlist_id = -1
            songs = self._playlist_mgr.get_all_songs()
            self._populate_table(songs)
            self._section_label.setText("  全部歌曲")
            self._status_label.setText(f"全部歌曲 - {len(songs)} 首")

        elif typ == "downloads":
            songs = [s for s in self._playlist_mgr.get_all_songs()
                     if s.file_path]
            self._current_view = "downloads"
            self._current_playlist_id = -2
            self._populate_table(songs)
            valid = sum(1 for s in songs if os.path.exists(s.file_path))
            self._section_label.setText("  我的下载")
            self._status_label.setText(f"我的下载 - {valid} 首有效 / {len(songs)} 首总计")

        elif typ == "playlist":
            pl = self._playlist_mgr.get_playlist(pid)
            songs = self._playlist_mgr.get_playlist_songs(pid)
            self._current_view = "playlist"
            self._current_playlist_id = pid
            self._populate_table(songs)
            self._section_label.setText(f"  歌单: {pl['name'] if pl else ''}")
            self._status_label.setText(f"歌单: {pl['name']} - {len(songs)} 首" if pl else "")

    def _get_current_song_list(self) -> list[Song]:
        if self._current_view == "all":
            return self._playlist_mgr.get_all_songs()
        elif self._current_view == "downloads":
            return [s for s in self._playlist_mgr.get_all_songs()
                    if s.file_path]
        elif self._current_view == "playlist" and self._current_playlist_id > 0:
            return self._playlist_mgr.get_playlist_songs(self._current_playlist_id)
        return self._player.playlist

    # ============================================================
    #  Search
    # ============================================================

    def _on_search(self):
        query = self._search_input.text().strip()
        if not query:
            return
        self._search_results = []
        self._populate_table([])
        self._section_label.setText("  搜索结果")
        self._status_label.setText(f"正在搜索: {query}...")
        self._btn_search.setEnabled(False)
        self._btn_search.setText("搜索中...")
        self._search_engine.search(query)

    def _on_result_found(self, song: Song):
        self._search_results.append(song)
        row = len(self._search_results) - 1
        self._song_table.setRowCount(row + 1)
        self._add_song_row(self._song_table, row, song)
        self._status_label.setText(f"已找到 {len(self._search_results)} 首...")
        self._section_label.setText(f"  搜索结果 ({len(self._search_results)})")

    def _on_search_finished(self):
        self._btn_search.setEnabled(True)
        self._btn_search.setText("🔍 搜索")
        if not self._search_results:
            self._status_label.setText("未找到可播放的歌曲")

    def _on_search_progress(self, text: str):
        self._status_label.setText(text)

    def _on_search_error(self, error: str):
        self._btn_search.setEnabled(True)
        self._btn_search.setText("🔍 搜索")
        self._status_label.setText(error)

    # ============================================================
    #  Import
    # ============================================================

    def _on_import_local(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "导入本地音乐",
            os.path.expanduser("~\\Music"),
            "音频文件 (*.mp3 *.wav *.ogg *.flac *.m4a *.wma);;所有文件 (*.*)"
        )
        if not files:
            return

        songs = []
        for fp in files:
            try:
                from mutagen import File as MutagenFile
                audio = MutagenFile(fp)
                if audio is None:
                    name = os.path.splitext(os.path.basename(fp))[0]
                    song = Song(title=name, file_path=fp, source_id=fp,
                                duration=0.0)
                else:
                    tags = audio.tags or {}
                    title = str(tags.get("title", os.path.splitext(os.path.basename(fp))[0]))
                    artist = str(tags.get("artist", tags.get("TPE1", "")))
                    album = str(tags.get("album", tags.get("TALB", "")))
                    dur = audio.info.length if hasattr(audio.info, 'length') else 0.0
                    song = Song(title=title, artist=artist, album=album,
                                duration=dur, file_path=fp, source_id=fp)
                song_id = self._playlist_mgr.add_song(song)
                song.song_id = song_id
                songs.append(song)
            except Exception as e:
                QMessageBox.warning(self, "导入失败", f"无法读取文件: {os.path.basename(fp)}\n{str(e)}")

        if songs:
            self._rebuild_left_panel()
            self._current_view = "all"
            all_songs = self._playlist_mgr.get_all_songs()
            self._populate_table(all_songs)
            self._section_label.setText("  全部歌曲")
            self._status_label.setText(f"已导入 {len(songs)} 首歌曲")

    # ============================================================
    #  Playback
    # ============================================================

    def _on_play_pause(self):
        if self._player.state == PlayerState.PLAYING:
            self._player.pause()
        elif self._player.state == PlayerState.PAUSED:
            self._player.resume()
        else:
            self._player.play()

    def _on_position_changed(self, position: float):
        if not self._is_seeking:
            dur = self._player.duration
            if dur > 0:
                self._progress_slider.setValue(int(position / dur * 1000))
            self._time_cur.setText(format_time(position))
            if self._lyrics_window.isVisible():
                self._lyrics_window.set_position(position)

    def _on_state_changed(self, state: PlayerState):
        self._btn_play.setText("⏸" if state == PlayerState.PLAYING else "▶")

    def _on_song_changed(self, song: Song):
        self._song_title_label.setText(song.title)
        self._song_artist_label.setText(song.artist or "未知艺术家")

        # Read actual duration from file
        dur = song.duration
        if dur <= 0 and song.file_path and os.path.exists(song.file_path):
            try:
                from mutagen import File as MutagenFile
                audio = MutagenFile(song.file_path)
                if audio and hasattr(audio.info, 'length'):
                    dur = audio.info.length
                    song.duration = dur
            except Exception:
                pass
        self._player.set_duration(dur)
        self._time_total.setText(format_time(dur))
        self._progress_slider.setValue(0)

        # Fetch lyrics — track which song this is for
        self._lyrics_fetch_for_song_id = song.source_id or song.file_path
        if song.lrc_url:
            try:
                r = requests.get(song.lrc_url, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://s.myhkw.cn/",
                }, timeout=5)
                if r.status_code == 200 and r.text.strip():
                    song.lyrics = r.text
                    self._on_lyrics_ready(r.text)
                    return
            except Exception:
                pass
        if song.title:
            self._lyrics_fetcher.fetch(song.title, song.artist, song.duration)

    def _on_mode_changed(self, mode: PlayMode):
        self._mode_btn.setToolTip(MODE_LABELS.get(mode, "顺序"))
        labels_short = {
            PlayMode.SEQUENTIAL: "🔁",
            PlayMode.RANDOM: "🔀",
            PlayMode.LOOP_ONE: "🔂",
            PlayMode.LOOP_ALL: "🔄",
        }
        self._mode_btn.setText(labels_short.get(mode, "🔁"))

    def _on_player_error(self, error: str):
        self._status_label.setText(error)

    def _on_cycle_mode(self):
        self._player.cycle_mode()

    def _on_slider_pressed(self):
        self._is_seeking = True

    def _on_slider_moved(self, value: int):
        dur = self._player.duration
        if dur > 0:
            pos = value / 1000.0 * dur
            self._time_cur.setText(format_time(pos))

    def _on_slider_released(self):
        self._is_seeking = False
        dur = self._player.duration
        if dur > 0:
            pos = self._progress_slider.value() / 1000.0 * dur
            self._player.seek(pos)

    def _on_volume_changed(self, value: int):
        vol = value / 100.0
        self._player.set_volume(vol)
        self._playlist_mgr.set_setting("volume", str(vol))

    # ============================================================
    #  Lyrics
    # ============================================================

    def _on_lyrics_ready(self, lrc_text: str):
        song = self._player.current_song
        if song and lrc_text:
            song.lyrics = lrc_text
            if song.song_id > 0:
                self._playlist_mgr.update_song_lyrics(song.song_id, lrc_text)
        if self._lyrics_window.isVisible():
            self._lyrics_window.set_lyrics(lrc_text)

    def _on_lyrics_error(self, error: str):
        pass

    def _on_toggle_lyrics(self, checked: bool):
        if checked:
            song = self._player.current_song
            if song and song.lyrics:
                self._lyrics_window.set_lyrics(song.lyrics)
            self._lyrics_window.show()
        else:
            self._lyrics_window.hide()

    # ============================================================
    #  Table helpers
    # ============================================================

    def _add_song_row(self, table: QTableWidget, row: int, song: Song):
        # Show "无效" if file is missing
        title = song.title
        if song.file_path and not os.path.exists(song.file_path):
            title = song.title + " [无效]"
        table.setItem(row, 0, QTableWidgetItem(title))
        table.setItem(row, 1, QTableWidgetItem(song.artist))
        table.setItem(row, 2, QTableWidgetItem(song.album))
        table.setItem(row, 3, QTableWidgetItem(format_time(song.duration)))
        item = table.item(row, 0)
        if item:
            item.setData(ROLE_TYPE, song.song_id)
            item.setData(ROLE_SONG, song.to_dict())

    def _populate_table(self, songs: list[Song]):
        self._song_table.setRowCount(len(songs))
        for i, song in enumerate(songs):
            self._add_song_row(self._song_table, i, song)

    def _get_song_from_table_row(self, row: int) -> Song | None:
        if row < 0 or row >= self._song_table.rowCount():
            return None
        item = self._song_table.item(row, 0)
        if item:
            data = item.data(ROLE_SONG)
            if data:
                return Song.from_dict(data)
        return None

    # ============================================================
    #  Table double-click → play
    # ============================================================

    def _on_table_double_click(self, index):
        row = index.row()
        song = self._get_song_from_table_row(row)
        if not song:
            return

        # Check if this is a search result (no local file)
        is_search = bool(self._search_results and
                         row < len(self._search_results) and
                         self._search_results[row].source_id == song.source_id)

        source_list = self._search_results if is_search else self._get_current_song_list()

        if not song.file_path and song.source_url:
            # Download first, then play
            self._status_label.setText(f"正在下载: {song.display_name}...")
            try:
                path = MyHKWAPI.download(song)
                song.file_path = path
                song_id = self._playlist_mgr.add_song(song)
                song.song_id = song_id
                self._playlist_mgr.update_song_path(song_id, path)
                self._refresh_after_download()
                # Re-read duration
                try:
                    from mutagen import File as MutagenFile
                    audio = MutagenFile(path)
                    if audio and hasattr(audio.info, 'length'):
                        song.duration = audio.info.length
                except Exception:
                    pass
            except Exception as e:
                self._status_label.setText(f"下载失败: {e}")
                return

        self._player.set_playlist(list(source_list), row)
        self._player.play(row)
        self._status_label.setText(f"正在播放: {song.display_name}")

    # ============================================================
    #  Table context menu
    # ============================================================

    def _on_table_context_menu(self, pos):
        table = self._song_table
        item = table.itemAt(pos)
        if not item:
            return
        row = item.row()
        song = self._get_song_from_table_row(row)
        if not song:
            return

        file_missing = song.file_path and not os.path.exists(song.file_path)

        menu = QMenu(self)

        play_action = menu.addAction("▶ 播放")
        play_action.triggered.connect(lambda: self._play_song_from_menu(song))

        menu.addSeparator()

        # Download or re-download
        if file_missing and song.source_url:
            redl_action = menu.addAction("🔄 重新下载")
            redl_action.triggered.connect(lambda: self._redownload_song(song))
        else:
            download_action = menu.addAction("⬇ 下载")
            download_action.triggered.connect(lambda: self._on_download_song(song))

        # Add to playlist submenu
        playlists = self._playlist_mgr.get_all_playlists()
        if playlists:
            add_menu = menu.addMenu("➕ 添加到歌单")
            for pl in playlists:
                pl_action = add_menu.addAction(f"📋 {pl['name']}")
                pl_action.triggered.connect(
                    lambda checked, pid=pl["id"], s=song: self._add_song_to_playlist_id(pid, s)
                )

        menu.addSeparator()

        delete_action = menu.addAction("🗑 彻底删除")
        delete_action.triggered.connect(lambda: self._on_delete_song(song))

        menu.exec_(table.viewport().mapToGlobal(pos))

    def _play_song_from_menu(self, song: Song):
        if not song.file_path and song.source_url:
            self._status_label.setText(f"正在下载: {song.display_name}...")
            try:
                path = MyHKWAPI.download(song)
                song.file_path = path
                song_id = self._playlist_mgr.add_song(song)
                song.song_id = song_id
                self._playlist_mgr.update_song_path(song_id, path)
                self._refresh_after_download()
                try:
                    from mutagen import File as MutagenFile
                    audio = MutagenFile(path)
                    if audio and hasattr(audio.info, 'length'):
                        song.duration = audio.info.length
                except Exception:
                    pass
            except Exception as e:
                self._status_label.setText(f"下载失败: {e}")
                return

        songs = self._get_current_song_list()
        # Find song in current list
        try:
            idx = next(i for i, s in enumerate(songs) if s.source_id == song.source_id)
        except StopIteration:
            songs = [song]
            idx = 0
        self._player.set_playlist(songs, idx)
        self._player.play(idx)
        self._populate_table(songs)

    # ============================================================
    #  Download (direct, no dialog)
    # ============================================================

    def _on_download_song(self, song: Song):
        if not song.source_url and not song.source_id:
            QMessageBox.warning(self, "无法下载", "该歌曲没有可用的下载链接。")
            return
        # Direct enqueue — no dialog
        self._download_manager.enqueue(song)

    def _on_task_added(self, song: Song, idx: int):
        """A download task was added to the queue."""
        task = {"song": song, "pct": 0, "status": "queued",
                "speed": "", "elapsed": "", "remaining": ""}
        self._download_tasks.insert(idx, task)
        self._refresh_download_list()
        self._status_label.setText(f"已加入下载队列: {song.display_name}")

    def _on_task_progress(self, idx: int, pct: float, speed: str, elapsed: str, remaining: str):
        """Update download progress."""
        if 0 <= idx < len(self._download_tasks):
            t = self._download_tasks[idx]
            t["pct"] = pct
            t["status"] = "downloading"
            t["speed"] = speed
            t["elapsed"] = elapsed
            t["remaining"] = remaining
            # Update status bar
            song = t["song"]
            self._status_label.setText(
                f"⬇ {song.display_name[:25]}  {pct:.0f}%  {speed}  "
                f"已用{elapsed}  剩余{remaining}"
            )
            self._refresh_download_list()

    def _on_task_finished(self, idx: int, path: str):
        """Download completed."""
        if 0 <= idx < len(self._download_tasks):
            t = self._download_tasks[idx]
            t["status"] = "completed"
            t["pct"] = 100
            song = t["song"]
            song.file_path = path
            sid = self._playlist_mgr.add_song(song)
            song.song_id = sid
            self._playlist_mgr.update_song_path(sid, path)
            # Read duration
            try:
                from mutagen import File as MutagenFile
                audio = MutagenFile(path)
                if audio and hasattr(audio.info, 'length'):
                    song.duration = audio.info.length
            except Exception:
                pass
            self._refresh_download_list()
            self._refresh_after_download()
            self._status_label.setText(f"下载完成: {song.display_name}")

    def _on_task_error(self, idx: int, error: str):
        """Download failed."""
        if 0 <= idx < len(self._download_tasks):
            t = self._download_tasks[idx]
            t["status"] = "failed"
            self._refresh_download_list()
            self._status_label.setText(f"下载失败: {error}")

    def _refresh_download_list(self):
        """Rebuild the download task list widget."""
        self._download_list.clear()
        for i, t in enumerate(self._download_tasks):
            song = t["song"]
            pct = t["pct"]
            status = t["status"]
            if status == "completed":
                text = f"✓ {song.display_name[:35]} — 已完成"
            elif status == "failed":
                text = f"✗ {song.display_name[:35]} — 失败"
            elif status == "downloading":
                bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
                text = f"⬇ {song.display_name[:25]}  [{bar}] {pct:.0f}%"
            else:
                text = f"⏳ {song.display_name[:35]} — 排队中"
            item = QTreeWidgetItem([text])
            item.setData(0, Qt.UserRole, i)        # task index
            item.setData(0, ROLE_SONG, song.to_dict())  # song data
            self._download_list.addTopLevelItem(item)

    def _on_download_context_menu(self, pos):
        """Right-click context menu for download task list items."""
        item = self._download_list.itemAt(pos)
        if not item:
            return
        idx = item.data(0, Qt.UserRole)
        song_dict = item.data(0, ROLE_SONG)
        if idx is None or not song_dict:
            return
        song = Song.from_dict(song_dict)

        menu = QMenu(self)

        add_menu = menu.addMenu("➕ 添加到歌单")
        for pl in self._playlist_mgr.get_all_playlists():
            pl_action = add_menu.addAction(f"📋 {pl['name']}")
            pl_action.triggered.connect(
                lambda checked, plid=pl["id"], s=song: self._add_song_to_playlist_id(plid, s)
            )

        menu.addSeparator()

        redl_action = menu.addAction("🔄 重新下载")
        redl_action.triggered.connect(lambda: self._redownload_song(song))

        menu.addSeparator()

        delete_action = menu.addAction("🗑 彻底删除")
        delete_action.triggered.connect(lambda: self._on_delete_song(song))

        menu.exec_(self._download_list.viewport().mapToGlobal(pos))

    # ============================================================
    #  Playlist management
    # ============================================================

    def _add_song_to_playlist_id(self, playlist_id: int, song: Song):
        song_id = song.song_id
        if song_id < 0:
            song_id = self._playlist_mgr.add_song(song)
            song.song_id = song_id
        self._playlist_mgr.add_song_to_playlist(playlist_id, song_id)
        pl = self._playlist_mgr.get_playlist(playlist_id)
        pl_name = pl['name'] if pl else '歌单'
        self._status_label.setText(f"已添加到「{pl_name}」: {song.display_name}")
        self._rebuild_left_panel()

    def _on_create_playlist(self):
        dlg = InputDialog(self, "新建歌单", "请输入歌单名称:")
        if dlg.exec_() == InputDialog.Accepted and dlg.value.strip():
            name = dlg.value.strip()
            pl_id = self._playlist_mgr.create_playlist(name)
            if pl_id > 0:
                self._rebuild_left_panel()
                self._status_label.setText(f"已创建歌单: {name}")

    def _on_playlist_context_menu(self, pos):
        item = self._left_tree.itemAt(pos)
        if not item:
            return
        typ = item.data(0, ROLE_TYPE)
        pid = item.data(0, ROLE_ID)

        if typ == "song":
            song_dict = item.data(0, ROLE_SONG)
            if not song_dict:
                return
            song = Song.from_dict(song_dict)
            menu = QMenu(self)

            parent = item.parent()
            parent_type = parent.data(0, ROLE_TYPE) if parent else ""
            file_missing = song.file_path and not os.path.exists(song.file_path)

            add_menu = menu.addMenu("➕ 添加到歌单")
            for pl in self._playlist_mgr.get_all_playlists():
                pl_action = add_menu.addAction(f"📋 {pl['name']}")
                pl_action.triggered.connect(
                    lambda checked, plid=pl["id"], s=song: self._add_song_to_playlist_id(plid, s)
                )

            # Re-download option for missing or download items
            if parent_type == "downloads" or (file_missing and song.source_url):
                redl_action = menu.addAction("🔄 重新下载")
                redl_action.triggered.connect(lambda: self._redownload_song(song))

            menu.addSeparator()

            if parent_type == "playlist":
                parent_pl_id = parent.data(0, ROLE_ID) if parent else -1

                remove_action = menu.addAction("❌ 移除歌曲")
                remove_action.triggered.connect(
                    lambda checked=False, plid=parent_pl_id, s=song:
                    self._remove_song_from_playlist(plid, s)
                )

                move_menu = menu.addMenu("📋 移动到歌单")
                for pl in self._playlist_mgr.get_all_playlists():
                    if pl["id"] != parent_pl_id:
                        pl_action = move_menu.addAction(f"{pl['name']}")
                        pl_action.triggered.connect(
                            lambda checked=False, plid=pl["id"], s=song, cur=parent_pl_id:
                            self._move_song_between_playlists(cur, plid, s)
                        )

            menu.addSeparator()

            delete_action = menu.addAction("🗑 彻底删除")
            delete_action.triggered.connect(lambda: self._on_delete_song(song))

            menu.exec_(self._left_tree.viewport().mapToGlobal(pos))
            return

        if typ != "playlist":
            return

        menu = QMenu(self)

        # "播放歌单" option
        play_action = menu.addAction("▶ 播放歌单")
        play_action.triggered.connect(lambda: self._play_playlist(pid))

        menu.addSeparator()

        rename_action = menu.addAction("✏ 重命名")
        delete_action = menu.addAction("🗑 删除")
        action = menu.exec_(self._left_tree.viewport().mapToGlobal(pos))

        if action == rename_action:
            dlg = InputDialog(self, "重命名歌单", "请输入新名称:")
            if dlg.exec_() == InputDialog.Accepted and dlg.value.strip():
                self._playlist_mgr.rename_playlist(pid, dlg.value.strip())
                self._rebuild_left_panel()
        elif action == delete_action:
            dlg = ConfirmDialog(self, "确认删除", "确定要删除这个歌单吗？")
            if dlg.exec_() == ConfirmDialog.Accepted and dlg.confirmed:
                self._playlist_mgr.delete_playlist(pid)
                self._rebuild_left_panel()
                self._status_label.setText("歌单已删除")

    def _play_playlist(self, playlist_id: int):
        """Start playing all songs in a playlist."""
        songs = self._playlist_mgr.get_playlist_songs(playlist_id)
        if not songs:
            self._status_label.setText("歌单为空")
            return
        self._player.set_playlist(songs, 0)
        self._player.play(0)
        self._populate_table(songs)
        self._section_label.setText(
            f"  歌单: {self._playlist_mgr.get_playlist(playlist_id)['name']}"
        )
        self._status_label.setText(f"正在播放歌单 - {len(songs)} 首")

    def _remove_song_from_playlist(self, playlist_id: int, song: Song):
        """Remove a song from a playlist (doesn't delete the file)."""
        if song.song_id > 0:
            self._playlist_mgr.remove_song_from_playlist(playlist_id, song.song_id)
        self._rebuild_left_panel()
        if self._current_playlist_id == playlist_id:
            songs = self._playlist_mgr.get_playlist_songs(playlist_id)
            self._populate_table(songs)
        self._status_label.setText(f"已从歌单移除: {song.display_name}")

    def _move_song_between_playlists(self, from_pl: int, to_pl: int, song: Song):
        """Move a song from one playlist to another."""
        song_id = song.song_id
        if song_id < 0:
            song_id = self._playlist_mgr.add_song(song)
        self._playlist_mgr.add_song_to_playlist(to_pl, song_id)
        self._playlist_mgr.remove_song_from_playlist(from_pl, song_id)
        self._rebuild_left_panel()
        self._status_label.setText(f"已移动: {song.display_name}")

    def _redownload_song(self, song: Song):
        """Delete existing file/record and re-download via queue."""
        if not song.source_url:
            self._status_label.setText("该歌曲没有可用的下载链接")
            return

        # If currently playing, stop first
        current = self._player.current_song
        if current and (current.song_id == song.song_id or current.file_path == song.file_path):
            self._player.stop()

        # Delete old file
        if song.file_path and os.path.exists(song.file_path):
            try:
                os.remove(song.file_path)
            except Exception:
                pass

        # Remove old DB record
        if song.song_id > 0:
            self._playlist_mgr.delete_song(song.song_id)
            song.song_id = -1

        # Re-enqueue for download
        self._download_manager.enqueue(song)

    def _on_delete_song(self, song: Song):
        dlg = ConfirmDialog(
            self, "确认删除",
            f"确定要彻底删除「{song.display_name}」吗？\n\n"
            "这将同时删除：\n"
            "  • 本地文件（从硬盘抹除）\n"
            "  • 数据库记录\n"
            "  • 所有歌单中的关联"
        )
        if dlg.exec_() != ConfirmDialog.Accepted:
            return

        # Resolve song_id if missing (e.g. stale cached data)
        sid = song.song_id
        if sid <= 0 and song.file_path:
            # Try to find by file path in all songs
            for s in self._playlist_mgr.get_all_songs():
                if s.file_path == song.file_path:
                    sid = s.song_id
                    break
        if sid <= 0 and song.source_id:
            for s in self._playlist_mgr.get_all_songs():
                if s.source_id == song.source_id:
                    sid = s.song_id
                    break

        # 0. If currently playing, stop first to release file lock
        current = self._player.current_song
        if current and (current.song_id == sid or current.file_path == song.file_path):
            self._player.stop()
            pl = self._player.playlist
            pl = [s for s in pl if s.song_id != sid]
            self._player.set_playlist(pl)

        # 1. Delete physical file
        if song.file_path and os.path.exists(song.file_path):
            try:
                os.remove(song.file_path)
            except Exception as e:
                self._status_label.setText(f"文件删除失败: {e}")

        # 2. Remove from ALL playlists
        if sid > 0:
            for pl in self._playlist_mgr.get_all_playlists():
                try:
                    self._playlist_mgr.remove_song_from_playlist(pl["id"], sid)
                except Exception:
                    pass

        # 3. Delete DB record
        if sid > 0:
            self._playlist_mgr.delete_song(sid)

        # 4. Refresh
        self._rebuild_left_panel()
        self._search_results = [s for s in self._search_results if s.song_id != sid]
        songs = self._get_current_song_list()
        songs = [s for s in songs if s.song_id != sid]
        self._populate_table(songs)
        self._status_label.setText(f"已彻底删除: {song.display_name}")

    # ============================================================
    #  Title bar drag
    # ============================================================

    def _title_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging_title = True
            self._drag_start_pos = event.globalPos()

    def _title_mouse_move(self, event):
        if self._is_dragging_title and self._drag_start_pos:
            delta = event.globalPos() - self._drag_start_pos
            self.move(self.pos() + delta)
            self._drag_start_pos = event.globalPos()

    def _title_mouse_release(self, event):
        self._is_dragging_title = False
        self._drag_start_pos = None

    def _title_double_click(self, event):
        self._toggle_maximize()

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _on_ui_tick(self):
        self._progress_slider.setEnabled(self._player.duration > 0)

    def closeEvent(self, event):
        self._player.stop()
        self._lyrics_window.close()
        self._playlist_mgr.set_setting("volume", str(self._player.volume))
        super().closeEvent(event)
