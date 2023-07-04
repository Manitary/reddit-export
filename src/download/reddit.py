import re
from pathlib import Path
from typing import Any

from praw.models import Submission

from .images import download_image

FILE_TYPE = re.compile(r"\w+\/(\w+)")
GALLERY_IMG = "https://i.redd.it/{img}.{ext}"


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
        download_image(url=url, path=path / name, name=str(num), ext=ext)
