"""
MyHKW (明月浩空) music API client — free, no-key, multi-source aggregator.

Aggregates NetEase, Kugou, QQ Music.  All returned songs are playable/downloadable.

Search:  POST https://s.myhkw.cn/
Download: GET  https://s.myhkw.cn/api.php?get=url&type=wy&id=...&sign=...
Lyrics:   GET  https://s.myhkw.cn/api.php?get=lrc&type=wy&id=...&sign=...
"""
import os

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from models.song import Song
from utils.helpers import get_data_dir, sanitize_filename

BASE_URL = "https://s.myhkw.cn"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Referer": f"{BASE_URL}/",
    "X-Requested-With": "XMLHttpRequest",
}

SOURCE_TYPES = {
    "netease": "wy",
    "kugou": "kg",
    "qq": "qq",
}

QUALITY_OPTIONS = {
    "128kbps": "128kbps - 标准音质",
    "192kbps": "192kbps - 高音质",
    "320kbps": "320kbps - 极高音质",
    "lossless": "无损 - 最佳音质",
}


class MyHKWAPI:
    """Synchronous API calls (run inside QThread workers)."""

    @staticmethod
    def search(query: str, source: str = "netease", page: int = 1) -> list[Song]:
        """Search songs. source can be 'netease', 'kugou', or 'qq'."""
        resp = requests.post(
            BASE_URL + "/",
            data={
                "input": query,
                "filter": "name",
                "type": source,
                "page": page,
            },
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", [])
        results = []
        for item in items:
            url_path = item.get("url", "")
            lrc_path = item.get("lrc", "")
            song = Song(
                title=item.get("name", "未知"),
                artist=item.get("artist", "未知"),
                album="",
                duration=0.0,
                cover_url=item.get("pic", ""),
                source_url=BASE_URL + "/" + url_path if url_path else "",
                lrc_url=BASE_URL + "/" + lrc_path if lrc_path else "",
                source_id=f"mhk_{source}_{item.get('songid', '')}",
            )
            results.append(song)
        return results

    @staticmethod
    def fetch_lyrics(song: Song) -> str | None:
        """Fetch LRC lyrics. Returns None if unavailable."""
        if not getattr(song, "lrc_url", ""):
            return None
        try:
            resp = requests.get(song.lrc_url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            text = resp.text.strip()
            return text if text else None
        except Exception:
            return None

    @staticmethod
    def download(song: Song, save_dir: str = None, progress_callback=None) -> str:
        """Download via MyHKW proxy. Returns local file path."""
        url = song.source_url
        resp = requests.get(url, headers=HEADERS, stream=True, timeout=60)
        resp.raise_for_status()

        ct = resp.headers.get("content-type", "")
        if "text/html" in ct:
            raise Exception("该歌曲下载链接已失效")

        save_dir = save_dir or get_data_dir("downloads")
        artist = sanitize_filename(song.artist or "未知")
        title = sanitize_filename(song.title or "未知")
        filename = f"{artist} - {title}.mp3"
        save_path = os.path.join(save_dir, filename)
        os.makedirs(save_dir, exist_ok=True)

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total > 0:
                        progress_callback(downloaded, total)
        return save_path


# ---- QThread workers ----

class MyHKWSearchWorker(QThread):
    """Search worker — fetches from up to 3 sources, emits incrementally."""
    result_found = pyqtSignal(Song)
    progress_text = pyqtSignal(str)
    finished = pyqtSignal()
    search_error = pyqtSignal(str)

    def __init__(self, query: str, max_results: int = 30):
        super().__init__()
        self._query = query
        self._max_results = max_results
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            # Try netease first (best Chinese library), then fallback to others
            sources = ["netease", "kugou", "qq"]
            count = 0

            for src in sources:
                if self._cancelled:
                    break
                self.progress_text.emit(f"正在搜索 {src}...")
                try:
                    songs = MyHKWAPI.search(self._query, src, page=1)
                    for song in songs:
                        if self._cancelled:
                            break
                        self.result_found.emit(song)
                        count += 1
                        if count >= self._max_results:
                            break
                except Exception:
                    continue  # source might be down, try next

            self.progress_text.emit(f"搜索完成，找到 {count} 首可播放歌曲")
            self.finished.emit()
        except Exception as e:
            self.search_error.emit(f"搜索失败: {e}")


class MyHKWDownloadWorker(QThread):
    progress = pyqtSignal(float, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, song: Song):
        super().__init__()
        self._song = song
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self.progress.emit(0, "正在下载...")

            # Fetch lyrics in parallel (best-effort)
            try:
                lrc = MyHKWAPI.fetch_lyrics(self._song)
                if lrc:
                    self._song.lyrics = lrc
            except Exception:
                pass

            def progress_cb(downloaded, total):
                if self._cancelled:
                    raise Exception("下载已取消")
                pct = downloaded / total * 100
                self.progress.emit(
                    pct,
                    f"下载中 {downloaded/1024/1024:.1f}/{total/1024/1024:.1f}MB",
                )

            save_path = MyHKWAPI.download(self._song, progress_callback=progress_cb)
            self.progress.emit(100, "下载完成")
            self.finished.emit(save_path)

        except Exception as e:
            msg = str(e)
            if "下载已取消" in msg:
                self.error.emit("下载已取消")
            elif "失效" in msg:
                self.error.emit("该歌曲下载链接已失效，请重新搜索")
            else:
                self.error.emit(f"下载失败: {msg[:200]}")
