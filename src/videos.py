from pathlib import Path

import yt_dlp

from utils import fix_file_path


def download_video(url: str, path: Path, name: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    full_path = path / f"{name}.mp4"
    full_path = fix_file_path(full_path)
    ytdlp_options = {"outtmpl": f"{str(path / full_path.stem)}.%(ext)s"}
    with yt_dlp.YoutubeDL(params=ytdlp_options) as ytdlp:
        ytdlp.download([url])
