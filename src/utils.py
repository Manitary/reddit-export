from pathlib import Path

MAX_PATH_LEN = 256

INVALID_CHARS = {
    "<": "[",
    ">": "]",
    ":": " -",
    '"': "'",
    "/": "-",
    "\\": "-",
    "|": "--",
    "?": "",
    "*": " ",
}


def slugify(string: str) -> str:
    for char, sub in INVALID_CHARS.items():
        string = string.replace(char, sub)
    while string.endswith("."):
        string = string[:-1]
    return string


def fix_file_path(path: Path) -> Path:
    length = len(str(path.resolve()))
    if length > MAX_PATH_LEN:
        name = path.stem[: MAX_PATH_LEN - length]
        path = path.parent / f"{name}{path.suffix}"
    return path
