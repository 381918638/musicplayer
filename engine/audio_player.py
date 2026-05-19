import random
from enum import Enum

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from models.song import Song

_mixer = None  # lazy-loaded pygame.mixer


def _get_mixer():
    global _mixer
    if _mixer is None:
        import pygame.mixer
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)
        _mixer = pygame.mixer
    return _mixer


class PlayMode(Enum):
    SEQUENTIAL = 0
    RANDOM = 1
    LOOP_ONE = 2
    LOOP_ALL = 3


class PlayerState(Enum):
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2


class AudioPlayer(QObject):
    position_changed = pyqtSignal(float)  # seconds
    state_changed = pyqtSignal(PlayerState)
    song_changed = pyqtSignal(Song)
    mode_changed = pyqtSignal(PlayMode)
    volume_changed = pyqtSignal(float)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._playlist: list[Song] = []
        self._current_index: int = -1
        self._current_song: Song | None = None
        self._state = PlayerState.STOPPED
        self._mode = PlayMode.SEQUENTIAL
        self._volume: float = 0.7
        self._position: float = 0.0
        self._base_position: float = 0.0  # seek offset for accurate get_pos() tracking
        self._duration: float = 0.0
        self._shuffle_history: list[int] = []
        self._idle_ticks: int = 0  # consecutive "not busy" ticks for end-of-song detection

        self._init_pygame()

        self._timer = QTimer(self)
        self._timer.setInterval(50)  # 20 updates/sec for smooth lyrics
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _init_pygame(self):
        try:
            _get_mixer()  # lazy-init pygame on first use
        except Exception as e:
            self.error_occurred.emit(f"音频初始化失败: {e}")

    def _tick(self):
        if self._state == PlayerState.PLAYING:
            try:
                pos_ms = _get_mixer().music.get_pos()
                if pos_ms >= 0:
                    self._position = self._base_position + pos_ms / 1000.0
                    self.position_changed.emit(self._position)
            except Exception:
                pass

            # Require multiple consecutive "not busy" ticks to prevent false positives
            # pygame.mixer can briefly report not-busy during buffering
            if not _get_mixer().music.get_busy() and self._position > 0.5:
                self._idle_ticks += 1
                if self._idle_ticks >= 4:  # ~1 second of silence
                    self._on_song_end()
            else:
                self._idle_ticks = 0

    def _on_song_end(self):
        if self._mode == PlayMode.LOOP_ONE:
            self._position = 0.0
            self._play_current()
        else:
            self.next()

    def _play_current(self):
        if not self._current_song or not self._current_song.file_path:
            return
        try:
            _get_mixer().music.load(self._current_song.file_path)
            _get_mixer().music.play()
            _get_mixer().music.set_volume(self._volume)
            self._position = 0.0
            self._base_position = 0.0
            self._idle_ticks = 0
            self._state = PlayerState.PLAYING
            self.state_changed.emit(self._state)
            self.song_changed.emit(self._current_song)
            self.position_changed.emit(0.0)
        except Exception as e:
            self.error_occurred.emit(f"播放失败: {e}")

    # ---- public API ----

    def set_playlist(self, songs: list[Song], start_index: int = 0):
        self._playlist = list(songs)
        self._shuffle_history = []
        if self._playlist:
            self._current_index = max(0, min(start_index, len(self._playlist) - 1))
            self._current_song = self._playlist[self._current_index]
        else:
            self._current_index = -1
            self._current_song = None

    def play(self, index: int | None = None):
        if index is not None and 0 <= index < len(self._playlist):
            self._current_index = index
            self._current_song = self._playlist[self._current_index]
        if self._current_song is None:
            return
        self._play_current()

    def pause(self):
        if self._state == PlayerState.PLAYING:
            _get_mixer().music.pause()
            self._state = PlayerState.PAUSED
            self.state_changed.emit(self._state)

    def resume(self):
        if self._state == PlayerState.PAUSED:
            _get_mixer().music.unpause()
            self._state = PlayerState.PLAYING
            self.state_changed.emit(self._state)

    def stop(self):
        _get_mixer().music.stop()
        self._state = PlayerState.STOPPED
        self._position = 0.0
        self.state_changed.emit(self._state)
        self.position_changed.emit(0.0)

    def next(self):
        if not self._playlist:
            return
        if self._mode == PlayMode.RANDOM:
            self._shuffle_history.append(self._current_index)
            remaining = [i for i in range(len(self._playlist)) if i not in self._shuffle_history]
            if not remaining:
                self._shuffle_history = [self._current_index]
                remaining = [i for i in range(len(self._playlist)) if i != self._current_index]
            self._current_index = random.choice(remaining) if remaining else 0
        elif self._mode in (PlayMode.SEQUENTIAL, PlayMode.LOOP_ALL):
            self._current_index += 1
            if self._current_index >= len(self._playlist):
                if self._mode == PlayMode.LOOP_ALL:
                    self._current_index = 0
                else:
                    self._current_index = len(self._playlist) - 1
                    self.stop()
                    return
        self._current_song = self._playlist[self._current_index]
        self._play_current()

    def previous(self):
        if not self._playlist:
            return
        if self._position > 3.0:
            self._position = 0.0
            self._play_current()
            return
        if self._mode == PlayMode.RANDOM and self._shuffle_history:
            self._current_index = self._shuffle_history.pop()
        else:
            self._current_index -= 1
            if self._current_index < 0:
                self._current_index = len(self._playlist) - 1 if self._mode == PlayMode.LOOP_ALL else 0
        self._current_song = self._playlist[self._current_index]
        self._play_current()

    def seek(self, seconds: float):
        if self._current_song and self._current_song.file_path:
            pos = max(0, min(seconds, self._duration))
            self._position = pos
            self._base_position = pos
            try:
                _get_mixer().music.play(start=pos)
                if self._state == PlayerState.PAUSED:
                    _get_mixer().music.pause()
                _get_mixer().music.set_volume(self._volume)
            except Exception:
                self._play_current()

    def set_volume(self, volume: float):
        self._volume = max(0.0, min(1.0, volume))
        try:
            _get_mixer().music.set_volume(self._volume)
        except Exception:
            pass
        self.volume_changed.emit(self._volume)

    def set_mode(self, mode: PlayMode):
        self._mode = mode
        self._shuffle_history = []
        self.mode_changed.emit(self._mode)

    def cycle_mode(self):
        modes = list(PlayMode)
        idx = modes.index(self._mode)
        self.set_mode(modes[(idx + 1) % len(modes)])

    # ---- properties ----

    @property
    def state(self) -> PlayerState:
        return self._state

    @property
    def mode(self) -> PlayMode:
        return self._mode

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def current_song(self) -> Song | None:
        return self._current_song

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def playlist(self) -> list[Song]:
        return list(self._playlist)

    @property
    def position(self) -> float:
        return self._position

    @property
    def duration(self) -> float:
        return self._duration

    def set_duration(self, duration: float):
        self._duration = duration
