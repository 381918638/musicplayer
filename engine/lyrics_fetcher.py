import re

import requests
from PyQt5.QtCore import QObject, QThread, pyqtSignal


class LyricsWorker(QThread):
    lyrics_ready = pyqtSignal(str)  # LRC format lyrics string
    lyrics_error = pyqtSignal(str)

    def __init__(self, title: str, artist: str, duration: float = 0):
        super().__init__()
        self._title = self._clean(title)
        self._artist = self._clean(artist)
        self._duration = duration

    @staticmethod
    def _clean(s: str) -> str:
        s = re.sub(r"[\(\[（【].*?[\)\]）】]", "", s)
        s = re.sub(r"feat\.|ft\.|Feat\.|Ft\.|官方版|MV|Official|Audio|Lyrics|歌词版", "", s, flags=re.IGNORECASE)
        return s.strip()

    def run(self):
        try:
            lrc = self._fetch_lrclib()
            if lrc:
                self.lyrics_ready.emit(lrc)
                return

            lrc = self._fetch_netease_ish()
            if lrc:
                self.lyrics_ready.emit(lrc)
                return

            self.lyrics_ready.emit("[00:00.00]未找到歌词\n[00:05.00]—— 请欣赏音乐 ——")
        except Exception as e:
            self.lyrics_error.emit(f"歌词获取失败: {e}")

    def _fetch_lrclib(self) -> str | None:
        try:
            params = {"track_name": self._title}
            if self._artist:
                params["artist_name"] = self._artist
            if self._duration > 0:
                params["duration"] = int(self._duration)

            resp = requests.get(
                "https://lrclib.net/api/get",
                params=params,
                timeout=10,
                headers={"User-Agent": "MusicPlayer/1.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                synced = data.get("syncedLyrics") or data.get("plainLyrics")
                if synced:
                    return synced

            # Try search endpoint
            resp2 = requests.get(
                "https://lrclib.net/api/search",
                params=params,
                timeout=10,
                headers={"User-Agent": "MusicPlayer/1.0"},
            )
            if resp2.status_code == 200:
                results = resp2.json()
                if results:
                    synced = results[0].get("syncedLyrics") or results[0].get("plainLyrics")
                    if synced:
                        return synced
        except Exception:
            pass
        return None

    def _fetch_netease_ish(self) -> str | None:
        try:
            resp = requests.get(
                "https://music.163.com/api/search/get",
                params={"s": f"{self._artist} {self._title}", "type": 1, "limit": 3},
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                songs = data.get("result", {}).get("songs", [])
                if songs:
                    song_id = songs[0]["id"]
                    lrc_resp = requests.get(
                        "https://music.163.com/api/song/lyric",
                        params={"id": song_id, "lv": 1},
                        timeout=10,
                        headers={"User-Agent": "Mozilla/5.0"},
                    )
                    if lrc_resp.status_code == 200:
                        lrc_data = lrc_resp.json()
                        lrc = lrc_data.get("lrc", {}).get("lyric", "")
                        tlyric = lrc_data.get("tlyric", {}).get("lyric", "")
                        if lrc:
                            return lrc + ("\n" + tlyric if tlyric else "")
        except Exception:
            pass
        return None


class LyricsFetcher(QObject):
    lyrics_ready = pyqtSignal(str)
    lyrics_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: LyricsWorker | None = None

    def fetch(self, title: str, artist: str, duration: float = 0):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()
        self._worker = LyricsWorker(title, artist, duration)
        self._worker.lyrics_ready.connect(self.lyrics_ready)
        self._worker.lyrics_error.connect(self.lyrics_error)
        self._worker.start()
