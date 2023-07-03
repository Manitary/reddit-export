"""Handle download of imgur links.

Imgur groups together GIFs and MP4s (it converts GIFs to MP4s when uploading, and makes either link available).
Since it is not possible to distinguish the origin of the file, MP4 is set by default, since GIFs will not always play correctly (based on empirical test)."""

import os
import re
import shutil
from pathlib import Path

import ratelimit
import requests
from dotenv import load_dotenv

from utils import fix_file_path

load_dotenv()

CLIENT_ID = os.getenv("IMGUR_CLIENT_ID")
DEFAULT_TIMEOUT = 60

IMAGE_API = "https://api.imgur.com/3/image/{id}"
ALBUM_API = "https://api.imgur.com/3/album/{id}"
IMAGE_ID = re.compile(r"imgur\.com\/(\w+)(?:\.\w+)?")
ALBUM_ID = re.compile(r"imgur\.com\/a\/(\w+)")
GALLERY_ID = re.compile(r"imgur\.com\/gallery\/(\w+)")
STACK_ID = re.compile(r"i\.stack\.imgur\.com\/\w+\.(\w+)")
FILE_TYPE = re.compile(r"\w+\/(\w+)")


def download_imgur_link(url: str, path: Path, file_name: str) -> None:
    """Download the given imgur link.

    Distinguish behaviour between image link and album link,
    as well as 'deprecated' link types (e.g. i.stacks.imgur.com)."""
    # Edge cases links
    if file_extension := STACK_ID.search(url):
        file_path = path / f"{file_name}.{file_extension.group(1)}"
        download_special(image_url=url, path=file_path)
        return
    if gallery_id := GALLERY_ID.search(url):
        download_gallery(gallery_id=gallery_id.group(1), path=path, file_name=file_name)
        return
    # Album link
    if album_id := ALBUM_ID.search(url):
        album_path = path / file_name
        download_album(album_id=album_id.group(1), path=album_path)
        return
    # Image link
    if image_id := IMAGE_ID.search(url):
        image_url, image_ext = download_image_data(image_id.group(1))
        file_path = path / f"{file_name}.{image_ext}"
        download_image(image_url=image_url, file_path=file_path)
        return
    raise ValueError("Invalid URL")


def download_special(image_url: str, path: Path) -> None:
    """Special imgur downloads that do not follow usual rules.

    Used for i.stack.imgur.com links."""
    if path.is_file():
        print("The image already exists")
        return
    if not image_url.startswith("http"):
        image_url = f"https://{image_url}"
    r = requests.get(url=image_url, timeout=DEFAULT_TIMEOUT, stream=True)
    if not r.ok:
        raise ConnectionError(f"Image {image_url} failed. Status code: {r.status_code}")
    path = fix_file_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        r.raw.decode_content = True
        shutil.copyfileobj(r.raw, f)


def download_image_data(image_id: str) -> tuple[str, str]:
    """Download image URL and file type from its id."""
    r = requests.get(
        url := IMAGE_API.format(id=image_id),
        headers={"Authorization": f"Client-ID {CLIENT_ID}"},
        timeout=DEFAULT_TIMEOUT,
    )
    if not r.ok:
        raise ConnectionError(f"Image {url} failed. Status code: {r.status_code}")
    data = r.json()["data"]
    url: str = data["link"]
    match = FILE_TYPE.search(data["type"])
    if not match:
        raise ValueError("Could not retrieve file type")
    ext: str = match.group(1)
    if ext == "gif":
        ext = "mp4"
        url: str = data["mp4"]

    return url, ext


@ratelimit.sleep_and_retry
@ratelimit.limits(calls=1, period=1)
def download_image(image_url: str, file_path: Path) -> None:
    """Download a single imgur image."""
    if file_path.is_file():
        print("The image already exists")
        return
    r = requests.get(url=image_url, timeout=DEFAULT_TIMEOUT, stream=True)
    if not r.ok:
        raise ConnectionError(f"Image {image_url} failed. Status code: {r.status_code}")
    file_path = fix_file_path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("wb") as f:
        r.raw.decode_content = True
        shutil.copyfileobj(r.raw, f)


def download_album(album_id: str, path: Path) -> None:
    """Download an imgur album."""
    r = requests.get(
        url := ALBUM_API.format(id=album_id),
        headers={"Authorization": f"Client-ID {CLIENT_ID}"},
        timeout=DEFAULT_TIMEOUT,
    )
    if not r.ok:
        raise ConnectionError(f"Album {url} failed. Status code: {r.status_code}")

    album_data = r.json()["data"]
    for num, image in enumerate(album_data["images"], 1):
        image_url: str = image["link"]
        image_title: str = image["title"] or ""
        match = FILE_TYPE.search(image["type"])
        if not match:
            raise ValueError(
                f"Error in album {album_id} when checking type of image {image_url}"
            )
        image_type: str = match.group(1)
        if image_type == "gif":
            image_type = "mp4"
            image_url: str = image["mp4"]
        file_path = (
            path / f"{num}{' - ' if image_title else ''}{image_title}.{image_type}"
        )
        try:
            download_image(image_url=image_url, file_path=file_path)
        except ConnectionError as e:
            raise ConnectionError from e
        except ValueError as e:
            raise ValueError from e


def download_gallery(gallery_id: str, path: Path, file_name: str) -> None:
    """Attempt to download an imgur gallery link.

    Imgur gallery IDs (usually) may behave as either regular image IDs
    or as regular album IDs.

    Raise ConnectionError if neither works."""
    try:
        url, ext = download_image_data(gallery_id)
        file_path = path / f"{file_name}.{ext}"
        download_image(url, file_path)
        return
    except ConnectionError:
        pass
    try:
        album_path = path / file_name
        download_album(gallery_id, album_path)
        return
    except ConnectionError:
        pass
    raise ConnectionError
