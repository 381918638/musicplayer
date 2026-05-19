import os
import re
import sys

if getattr(sys, "frozen", False):
    # Packaged exe — data lives next to the executable
    _exe_dir = os.path.dirname(sys.executable)
    DATA_DIR = os.path.join(_exe_dir, "data")
else:
    # Running from source
    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def get_data_dir(*subdirs: str) -> str:
    path = os.path.join(DATA_DIR, *subdirs)
    os.makedirs(path, exist_ok=True)
    return path


def format_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_duration(seconds: float) -> str:
    return format_time(seconds)


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = name.strip().strip(".")
    return name or "unknown"
