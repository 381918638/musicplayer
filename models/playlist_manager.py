from models.database import Database
from models.song import Song
from typing import Optional


class PlaylistManager:
    def __init__(self):
        self.db = Database()

    # ---- song CRUD ----

    def add_song(self, song: Song) -> int:
        existing = self.db.fetchone(
            "SELECT id FROM songs WHERE source_id = ? AND source_id != ''",
            (song.source_id,),
        )
        if existing:
            return existing["id"]

        cursor = self.db.execute(
            """INSERT INTO songs (title, artist, album, duration, file_path,
               cover_url, cover_path, lyrics, source_url, source_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (song.title, song.artist, song.album, song.duration,
             song.file_path, song.cover_url, song.cover_path,
             song.lyrics, song.source_url, song.source_id),
        )
        self.db.commit()
        return cursor.lastrowid

    def get_song(self, song_id: int) -> Optional[Song]:
        row = self.db.fetchone("SELECT * FROM songs WHERE id = ?", (song_id,))
        if row:
            row["song_id"] = row.pop("id")
            return Song.from_dict(row)
        return None

    def get_all_songs(self) -> list[Song]:
        rows = self.db.fetchall("SELECT * FROM songs ORDER BY title")
        result = []
        for r in rows:
            r["song_id"] = r.pop("id")
            result.append(Song.from_dict(r))
        return result

    def update_song_lyrics(self, song_id: int, lyrics: str):
        self.db.execute("UPDATE songs SET lyrics = ? WHERE id = ?", (lyrics, song_id))
        self.db.commit()

    def update_song_path(self, song_id: int, file_path: str):
        self.db.execute("UPDATE songs SET file_path = ? WHERE id = ?", (file_path, song_id))
        self.db.commit()

    def delete_song(self, song_id: int):
        self.db.execute("DELETE FROM songs WHERE id = ?", (song_id,))
        self.db.commit()

    # ---- playlist CRUD ----

    def create_playlist(self, name: str) -> int:
        try:
            cursor = self.db.execute(
                "INSERT INTO playlists (name) VALUES (?)", (name,)
            )
            self.db.commit()
            return cursor.lastrowid
        except Exception:
            return -1

    def delete_playlist(self, playlist_id: int):
        self.db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        self.db.commit()

    def rename_playlist(self, playlist_id: int, new_name: str):
        self.db.execute(
            "UPDATE playlists SET name = ? WHERE id = ?", (new_name, playlist_id)
        )
        self.db.commit()

    def get_all_playlists(self) -> list[dict]:
        return self.db.fetchall("SELECT * FROM playlists ORDER BY created_at")

    def get_playlist(self, playlist_id: int) -> Optional[dict]:
        return self.db.fetchone("SELECT * FROM playlists WHERE id = ?", (playlist_id,))

    def add_song_to_playlist(self, playlist_id: int, song_id: int):
        existing = self.db.fetchone(
            "SELECT id FROM playlist_songs WHERE playlist_id = ? AND song_id = ?",
            (playlist_id, song_id),
        )
        if existing:
            return
        max_pos = self.db.fetchone(
            "SELECT COALESCE(MAX(position), -1) AS pos FROM playlist_songs WHERE playlist_id = ?",
            (playlist_id,),
        )
        pos = (max_pos["pos"] if max_pos else -1) + 1
        self.db.execute(
            "INSERT INTO playlist_songs (playlist_id, song_id, position) VALUES (?, ?, ?)",
            (playlist_id, song_id, pos),
        )
        self.db.commit()

    def remove_song_from_playlist(self, playlist_id: int, song_id: int):
        self.db.execute(
            "DELETE FROM playlist_songs WHERE playlist_id = ? AND song_id = ?",
            (playlist_id, song_id),
        )
        self.db.commit()

    def get_playlist_songs(self, playlist_id: int) -> list[Song]:
        rows = self.db.fetchall(
            """SELECT s.* FROM songs s
               JOIN playlist_songs ps ON s.id = ps.song_id
               WHERE ps.playlist_id = ?
               ORDER BY ps.position""",
            (playlist_id,),
        )
        result = []
        for r in rows:
            r["song_id"] = r.pop("id")
            result.append(Song.from_dict(r))
        return result

    def reorder_playlist_song(self, playlist_id: int, song_id: int, new_position: int):
        self.db.execute(
            "UPDATE playlist_songs SET position = ? WHERE playlist_id = ? AND song_id = ?",
            (new_position, playlist_id, song_id),
        )
        self.db.commit()

    # ---- settings ----

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.db.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        self.db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        self.db.commit()
