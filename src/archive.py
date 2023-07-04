import os
import re
import sqlite3
from pathlib import Path

import praw
from dotenv import load_dotenv
from praw.models import Submission
from prawcore.exceptions import Forbidden
from ratelimit import limits, sleep_and_retry

from db.db import DB_PATH, update_db
from download import images, imgur, reddit, videos
from exceptions import (
    ArchiveError,
    DeletedPostError,
    MissingLinkError,
    NotMediaError,
    PixivError,
    PrivatePostError,
)
from utils import fix_file_path, slugify

load_dotenv()

PATH_DATA = Path().resolve() / "data"
PATH_TABLE = {
    "post_votes": PATH_DATA / "upvoted" / "posts",
    "saved_posts": PATH_DATA / "saved" / "posts",
    "comment_votes": PATH_DATA / "upvoted" / "comments",
    "saved_comments": PATH_DATA / "saved" / "comments",
}

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


@sleep_and_retry
@limits(calls=60, period=60)
def get_submission(r: praw.Reddit, post_id: str) -> Submission:
    return r.submission(post_id)


def save_post(r: praw.Reddit, post_id: str, path: Path) -> bool:
    try:
        post: Submission = get_submission(r, post_id)
        try:
            post: Submission = get_submission(r, post.crosspost_parent[3:])
        except AttributeError:
            # The post is not a crosspost
            pass
    except Forbidden as e:
        raise PrivatePostError() from e
    sub_name: str = post.subreddit_name_prefixed[2:]
    # text post
    full_title = f"[{post_id}] - {slugify(post.title)}"
    if post.is_self:
        save_text_post(post=post, path=path / sub_name, name=full_title)
        return True
    # link post
    if save_link_post(post=post, path=path / sub_name, name=full_title):
        return True
    return False


def save_text_post(post: Submission, path: Path, name: str) -> None:
    body: str = post.selftext
    if body == "[removed]":
        raise DeletedPostError()
    file_path = path / f"{name}.txt"
    file_path = fix_file_path(file_path)
    if file_path.is_file():
        print("Text post already archived")
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        f.write(body)


def save_not_media_post(url: str, path: Path, name: str) -> None:
    file_path = path / f"{name}.txt"
    file_path = fix_file_path(file_path)
    if file_path.is_file():
        print("Post URL already archived")
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        f.write(url)
    raise NotMediaError(url)


def save_link_post(post: Submission, path: Path, name: str) -> None:
    link: str = post.url
    if not link:
        raise MissingLinkError()
    if PIXIV_IMAGE.search(link):
        raise PixivError(link)
    if IMGUR_LINK.search(link):
        imgur.download_imgur_link(url=link, path=path, file_name=name)
        return
    if REDDIT_IMG_LINK.search(link):
        images.download_image(url=link, path=path, name=name)
        return
    if REDDIT_GALLERY_LINK.search(link):
        reddit.download_reddit_gallery(post=post, path=path, name=name)
        return
    if YOUTUBE_PLAYLIST_LINK.search(link):
        videos.download_youtube_playlist(url=link, path=path, name=name)
        return
    if (
        REDDIT_VIDEO_LINK.search(link)
        or YOUTUBE_LINK.search(link)
        or GFYCAT_LINK.search(link)
        or STREAMABLE_LINK.search(link)
    ):
        videos.download_video(url=link, path=path, name=name)
        return
    if MAL_IMAGE.search(link) or TWITTER_IMAGE.search(link):
        images.download_image(url=link, path=path, name=name, ext="jpg")
        return
    if ext := IMAGE_GENERAL_LINK.match(link):
        images.download_image(url=link, path=path, name=name, ext=ext.group(1))
        return
    print(link)
    save_not_media_post(url=link, path=path, name=name)


def archive_table(r: praw.Reddit, table: str, db_path: str | Path = DB_PATH) -> None:
    if table not in PATH_TABLE:
        raise ValueError("Invalid table name")
    with sqlite3.connect(db_path) as db:
        entries = db.execute(
            f"SELECT id, permalink FROM {table} WHERE direction = 'up' AND archived = 0",
        ).fetchall()
        for entry in entries:
            post_id, post_link = entry
            print(f"Processing {post_id}")
            try:
                save_post(r=r, post_id=post_id, path=PATH_TABLE[table])
                db.execute(
                    f"UPDATE {table} SET archived = 1 WHERE id = ?",
                    (post_id,),
                )
                db.commit()
                print("Archive successful")
            except ArchiveError as e:
                db.execute(
                    f"UPDATE {table} SET archived = ? WHERE id = ?",
                    (e.code, post_id),
                )
                db.execute(
                    """INSERT INTO archive_errors (id, permalink, error, link)
                    VALUES (?, ?, ?, ?) ON CONFLICT DO UPDATE SET error = ?""",
                    (post_id, post_link, e.error, e.url, e.error),
                )
                db.commit()
                print(f"Download failed: {e.__class__}")


def main(update: bool = False) -> None:
    if update:
        update_db()
    r = praw.Reddit(
        client_id=os.environ.get("REDDIT_CLIENT_ID"),
        client_secret=os.environ.get("REDDIT_SECRET"),
        user_agent=os.environ.get("REDDIT_USER_AGENT"),
        username=os.environ.get("REDDIT_USERNAME"),
        password=os.environ.get("REDDIT_USER_PASSWORD"),
    )
    archive_table(r, table="post_votes")


if __name__ == "__main__":
    main(update=False)
