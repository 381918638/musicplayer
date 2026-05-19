"""
Download manager with task queue — processes downloads one at a time.
Signals: progress(percent, speed_str, task_index), finished(path, task_index), error(msg, task_index)
"""
import time

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from engine.myhkw_api import MyHKWAPI
from models.song import Song

QUALITY_OPTIONS = {
    "128kbps": "128kbps - 标准音质",
    "192kbps": "192kbps - 高音质",
    "320kbps": "320kbps - 极高音质",
    "lossless": "无损 - 最佳音质",
}


class DownloadWorker(QThread):
    """Downloads a single song in a background thread."""
    progress = pyqtSignal(float, str, str, str)  # pct, speed, elapsed, remaining
    finished = pyqtSignal(str)    # file path
    error = pyqtSignal(str)

    def __init__(self, song: Song):
        super().__init__()
        self._song = song
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            start_time = time.time()

            def progress_cb(downloaded, total):
                if self._cancelled:
                    raise Exception("下载已取消")
                if total <= 0:
                    return
                pct = downloaded / total * 100
                elapsed = time.time() - start_time
                speed = downloaded / elapsed if elapsed > 0 else 0
                remaining = (total - downloaded) / speed if speed > 0 else 0

                # Format strings
                if speed > 1024 * 1024:
                    speed_str = f"{speed/1024/1024:.1f}MB/s"
                elif speed > 1024:
                    speed_str = f"{speed/1024:.0f}KB/s"
                else:
                    speed_str = f"{speed:.0f}B/s"

                elapsed_str = f"{int(elapsed//60)}:{int(elapsed%60):02d}"
                remaining_str = f"{int(remaining//60)}:{int(remaining%60):02d}" if remaining > 0 else "..."

                self.progress.emit(pct, speed_str, elapsed_str, remaining_str)

            # Fetch lyrics
            try:
                lrc = MyHKWAPI.fetch_lyrics(self._song)
                if lrc:
                    self._song.lyrics = lrc
            except Exception:
                pass

            path = MyHKWAPI.download(self._song, progress_callback=progress_cb)
            self.finished.emit(path)

        except Exception as e:
            msg = str(e)
            if "下载已取消" in msg:
                self.error.emit("下载已取消")
            else:
                self.error.emit(f"下载失败: {msg[:200]}")


class DownloadManager(QObject):
    """Manages a download queue — one active download at a time."""

    # Per-task signals
    task_added = pyqtSignal(Song, int)       # song, queue_index
    task_progress = pyqtSignal(int, float, str, str, str)  # idx, pct, speed, elapsed, remaining
    task_finished = pyqtSignal(int, str)     # idx, path
    task_error = pyqtSignal(int, str)         # idx, error

    QUALITY_OPTIONS = QUALITY_OPTIONS

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: list[Song] = []
        self._worker: DownloadWorker | None = None
        self._current_idx: int = -1

    def enqueue(self, song: Song):
        """Add song to download queue. Starts immediately if idle."""
        idx = len(self._queue)
        self._queue.append(song)
        self.task_added.emit(song, idx)
        if self._worker is None:
            self._process_next()

    def cancel(self, idx: int = -1):
        """Cancel download at queue index. -1 cancels current."""
        if idx < 0 or idx == self._current_idx:
            if self._worker and self._worker.isRunning():
                self._worker.cancel()
                self._worker.wait()
            self._worker = None
            self._current_idx = -1
        elif idx < len(self._queue):
            self._queue.pop(idx)
            self.task_error.emit(idx, "已取消")

    def _process_next(self):
        """Start downloading the next song in the queue."""
        # Find first queued (not downloading, not completed) item
        for i in range(len(self._queue)):
            if self._queue[i] is not None:
                song = self._queue[i]
                self._queue[i] = None  # mark as in-progress
                self._current_idx = i
                self._start_download(song, i)
                return
        # Queue empty
        self._worker = None
        self._current_idx = -1

    def _start_download(self, song: Song, idx: int):
        self._worker = DownloadWorker(song)
        self._worker.progress.connect(
            lambda pct, speed, elapsed, remaining, i=idx:
            self.task_progress.emit(i, pct, speed, elapsed, remaining)
        )
        self._worker.finished.connect(lambda path, i=idx: self._on_finished(i, path))
        self._worker.error.connect(lambda err, i=idx: self._on_error(i, err))
        self._worker.start()

    def _on_finished(self, idx: int, path: str):
        self._worker = None
        self._current_idx = -1
        self.task_finished.emit(idx, path)
        self._process_next()

    def _on_error(self, idx: int, error: str):
        self._worker = None
        self._current_idx = -1
        self.task_error.emit(idx, error)
        self._process_next()

    @property
    def active_count(self) -> int:
        return 1 if self._worker and self._worker.isRunning() else 0

    @property
    def queue_length(self) -> int:
        return len(self._queue)

    def download(self, song: Song, quality: str = "320kbps"):
        """Legacy interface — delegates to enqueue."""
        self.enqueue(song)
