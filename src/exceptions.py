from typing import Any


class ArchiveError(Exception):
    _error: str = ""
    _code: int = 2
    _url: str = ""

    @property
    def error(self) -> str:
        return self._error

    @property
    def code(self) -> int:
        return self._code

    @property
    def url(self) -> str:
        return self._url


class DeletedPostError(ArchiveError):
    _error = "Deleted selftext post"


class PrivatePostError(ArchiveError):
    _error = "403 - Forbidden post"


class VideoDownloadError(ArchiveError):
    def __init__(self, url: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._url = url
        self._error = "Failed to download video"


class PixivError(ArchiveError):
    def __init__(self, url: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._url = url
        self._error = "Pixiv login required"


class MissingLinkError(ArchiveError):
    _error = "Missing link"


class FailedDownloadError(ArchiveError):
    def __init__(self, url: str, code: int, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._url = url
        self._error = f"{code} - Failed to retrieve URL"


class NotMediaError(ArchiveError):
    _code = 3

    def __init__(self, url: str, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._url = url
        self._error = "Unrecognised media URL"
