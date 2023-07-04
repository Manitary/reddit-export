import re
from pathlib import Path
import shutil

import requests

from utils import fix_file_path

FILE_EXT = re.compile(r".*\.(\w+)$")
DEFAULT_TIMEOUT = 60


def download_image(url: str, path: Path, name: str, ext: str = "jpg") -> None:
    if not ext:
        match = FILE_EXT.match(url)
        if not match:
            raise ValueError(f"Invalid image URL: {url}")
        ext = match.group(1)
    file_path = path / f"{name}.{ext}"
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
