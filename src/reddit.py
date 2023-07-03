import re
import shutil
from pathlib import Path
from typing import Any

from praw.models import Submission
import requests
import yt_dlp

from utils import fix_file_path

DEFAULT_TIMEOUT = 60
FILE_EXT = re.compile(r".*\.(\w+)$")
FILE_TYPE = re.compile(r"\w+\/(\w+)")
GALLERY_IMG = "https://i.redd.it/{img}.{ext}"


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


def download_reddit_gallery(post: Submission, path: Path, name: str) -> None:
    gallery_items: list[dict[str, str]] = post.gallery_data["items"]
    metadata: dict[str, dict[str, Any]] = post.media_metadata
    for num, item in enumerate(gallery_items, 1):
        item_id = item["media_id"]
        match = FILE_TYPE.search(metadata[item_id]["m"])
        if not match:
            raise ValueError(
                f"Invalid file type in Reddit gallery {post.id}: {item_id}"
            )
        ext: str = match.group(1)
        url = GALLERY_IMG.format(img=item_id, ext=ext)
        r = requests.get(url, timeout=DEFAULT_TIMEOUT, stream=True)
        if not r.ok:
            raise ConnectionError(
                f"Failed retrieving Reddit gallery {post.id} image {item_id}"
            )
        file_path = path / name / f"{num}.{ext}"
        file_path = fix_file_path(file_path)
        if file_path.is_file():
            print("The picture already exists")
            continue
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("wb") as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)
