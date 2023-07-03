import re
import shutil
from pathlib import Path

import requests
import yt_dlp

from utils import fix_file_path

FILE_EXT = re.compile(r".*\.(\w+)$")
DEFAULT_TIMEOUT = 60


def download_reddit_image(url: str, path: Path, name: str) -> None:
    ext = FILE_EXT.match(url)
    if not ext:
        raise ValueError(f"Invalid URL: {url}")
    file_path = path / f"{name}.{ext.group(1)}"
    file_path = fix_file_path(file_path)
    if file_path.is_file():
        print("The image already exists")
        return
    r = requests.get(url=url, timeout=DEFAULT_TIMEOUT, stream=True)
    if not r.ok:
        raise ConnectionError(f"Image {url} failed. Status code: {r.status_code}")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("wb") as f:
        r.raw.decode_content = True
        shutil.copyfileobj(r.raw, f)


def download_reddit_video(url: str, path: Path, name: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    full_path = path / f"{name}.mp4"
    full_path = fix_file_path(full_path)
    ytdlp_options = {"outtmpl": f"{str(path / full_path.stem)}.%(ext)s"}
    with yt_dlp.YoutubeDL(params=ytdlp_options) as ytdlp:
        ytdlp.download([url])
