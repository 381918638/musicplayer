from dataclasses import dataclass, field


@dataclass
class Song:
    title: str = ""
    artist: str = ""
    album: str = ""
    duration: float = 0.0
    file_path: str = ""
    cover_url: str = ""
    cover_path: str = ""
    lyrics: str = ""
    source_url: str = ""
    source_id: str = ""
    lrc_url: str = ""  # MyHKW lyrics endpoint URL (transient, not persisted)
    song_id: int = -1

    @property
    def display_name(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "duration": self.duration,
            "file_path": self.file_path,
            "cover_url": self.cover_url,
            "cover_path": self.cover_path,
            "lyrics": self.lyrics,
            "source_url": self.source_url,
            "source_id": self.source_id,
            "song_id": self.song_id,
        }

    @staticmethod
    def from_dict(data: dict) -> "Song":
        return Song(
            title=data.get("title", ""),
            artist=data.get("artist", ""),
            album=data.get("album", ""),
            duration=data.get("duration", 0.0),
            file_path=data.get("file_path", ""),
            cover_url=data.get("cover_url", ""),
            cover_path=data.get("cover_path", ""),
            lyrics=data.get("lyrics", ""),
            source_url=data.get("source_url", ""),
            source_id=data.get("source_id", ""),
            song_id=data.get("song_id", -1),
        )
