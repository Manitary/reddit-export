from pathlib import Path

import yt_dlp

from exceptions import VideoDownloadError
from utils import MAX_PATH_LEN, fix_file_path


def download_video(url: str, path: Path, name: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    full_path = path / f"{name}.mp4"
    full_path = fix_file_path(full_path)
    ytdlp_options = {"outtmpl": f"{str(path / full_path.stem)}.%(ext)s"}
    try:
        with yt_dlp.YoutubeDL(params=ytdlp_options) as ytdlp:
            ytdlp.download([url])
    except yt_dlp.DownloadError as e:
        raise VideoDownloadError(url=url) from e


def download_youtube_playlist(url: str, path: Path, name: str) -> None:
    path = path / name
    max_file_len = MAX_PATH_LEN - len(str(path)) - 10

    ytdlp_options = {
        "outtmpl": f"{str(path)}\\%(playlist_index)s - %(title)s.%(ext)s",
        "trim_file_name": max_file_len,
    }
    try:
        with yt_dlp.YoutubeDL(params=ytdlp_options) as ytdlp:
            ytdlp.download([url])
    except yt_dlp.DownloadError as e:
        raise VideoDownloadError(url=url) from e
