import re
from pathlib import Path

from praw.models import Submission

from download import images, imgur, reddit, videos
from exceptions import PixivError

IMGUR_LINK = re.compile(r"imgur\.com")
REDDIT_IMG_LINK = re.compile(r"i\.redd\.it")
REDDIT_VIDEO_LINK = re.compile(r"v\.redd\.it")
REDDIT_GALLERY_LINK = re.compile(r"reddit\.com/gallery/")
YOUTUBE_LINK = re.compile(r"(?:youtube\.com|youtu\.be)")
YOUTUBE_PLAYLIST_LINK = re.compile(r"youtube\.com/watch\?.*list=\w.*")
IMAGE_GENERAL_LINK = re.compile(r".*\.(jpg|png|jpeg|gif)(?:\?.*)?$")
STREAMABLE_LINK = re.compile(r"streamable\.com")
GFYCAT_LINK = re.compile(r"gfycat\.com")
MAL_IMAGE = re.compile(r"image\.myanimelist\.net")
PIXIV_IMAGE = re.compile(r"pixiv\.net|i\.pximg\.net")
TWITTER_IMAGE = re.compile(r"pbs.twimg.com")


def save_link(post: Submission, path: Path, name: str, link: str) -> bool:
    if PIXIV_IMAGE.search(link):
        raise PixivError(link)
    if IMGUR_LINK.search(link):
        imgur.download_imgur_link(url=link, path=path, file_name=name)
        return True
    if REDDIT_IMG_LINK.search(link):
        images.download_image(url=link, path=path, name=name)
        return True
    if REDDIT_GALLERY_LINK.search(link):
        reddit.download_reddit_gallery(post=post, path=path, name=name)
        return True
    if YOUTUBE_PLAYLIST_LINK.search(link):
        videos.download_youtube_playlist(url=link, path=path, name=name)
        return True
    if (
        REDDIT_VIDEO_LINK.search(link)
        or YOUTUBE_LINK.search(link)
        or GFYCAT_LINK.search(link)
        or STREAMABLE_LINK.search(link)
    ):
        videos.download_video(url=link, path=path, name=name)
        return True
    if MAL_IMAGE.search(link) or TWITTER_IMAGE.search(link):
        images.download_image(url=link, path=path, name=name, ext="jpg")
        return True
    if ext := IMAGE_GENERAL_LINK.match(link):
        images.download_image(url=link, path=path, name=name, ext=ext.group(1))
        return True
    return False
