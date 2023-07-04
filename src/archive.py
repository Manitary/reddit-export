import os
import re
import sqlite3
from functools import partial
from pathlib import Path

import praw
from dotenv import load_dotenv
from praw.models import Submission
from prawcore.exceptions import Forbidden, NotFound
from ratelimit import limits, sleep_and_retry
from yt_dlp import DownloadError

import videos
import images
import youtube
import imgur
import reddit
from db.db import DB_PATH
from utils import fix_file_path, slugify

load_dotenv()

PATH_BASE = Path().resolve()
PATH_DATA = PATH_BASE / "data"
PATH_SAVED = PATH_DATA / "saved"
PATH_UPVOTED = PATH_DATA / "upvoted"
PATH_SAVED_POST = PATH_SAVED / "posts"
PATH_UPVOTED_POST = PATH_UPVOTED / "posts"
PATH_SAVED_COMMENT = PATH_SAVED / "comments"
PATH_UPVOTED_COMMENT = PATH_UPVOTED / "comments"

IMGUR_LINK = re.compile(r"imgur\.com")
REDDIT_IMG_LINK = re.compile(r"i\.redd\.it")
REDDIT_VIDEO_LINK = re.compile(r"v\.redd\.it")
REDDIT_GALLERY_LINK = re.compile(r"reddit\.com/gallery/")
YOUTUBE_LINK = re.compile(r"(?:youtube\.com|youtu\.be)")
YOUTUBE_PLAYLIST_LINK = re.compile(r"youtube\.com/watch\?(.*)list=\w(.*)")
IMAGE_GENERAL_LINK = re.compile(r".*\.(jpg|png|jpeg|gif)(?:\?.*)?$")
STREAMABLE_LINK = re.compile(r"streamable\.com")
GFYCAT_LINK = re.compile(r"gfycat\.com")
MAL_IMAGE = re.compile(r"image\.myanimelist\.net")
PIXIV_IMAGE = re.compile(r"pixiv\.net|i\.pximg\.net")
TWITTER_IMAGE = re.compile(r"pbs.twimg.com")


class DeletedPostError(Exception):
    ...


class PixivError(Exception):
    ...


class MissingLinkError(Exception):
    ...


class NotMediaError(Exception):
    ...


@sleep_and_retry
@limits(calls=60, period=60)
def get_submission(r: praw.Reddit, post_id: str) -> Submission:
    return r.submission(post_id)


def save_post(r: praw.Reddit, post_id: str, path: Path) -> bool:
    post: Submission = get_submission(r, post_id)
    try:
        post: Submission = get_submission(r, post.crosspost_parent[3:])
    except (AttributeError, NotFound):
        # The post is not a crosspost
        pass
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
    raise NotMediaError(f"Unrecognised media URL: {url}")


def save_link_post(post: Submission, path: Path, name: str) -> bool:
    link: str = post.url
    if not link:
        raise MissingLinkError()
    if IMGUR_LINK.search(link):
        imgur.download_imgur_link(url=link, path=path, file_name=name)
        return True
    if REDDIT_IMG_LINK.search(link):
        reddit.download_reddit_image(url=link, path=path, name=name)
        return True
    if REDDIT_VIDEO_LINK.search(link):
        reddit.download_reddit_video(url=link, path=path, name=name)
        return True
    if REDDIT_GALLERY_LINK.search(link):
        reddit.download_reddit_gallery(post=post, path=path, name=name)
        return True
    if YOUTUBE_LINK.search(link):
        if YOUTUBE_PLAYLIST_LINK.search(link):
            youtube.download_youtube_playlist(url=link, path=path, name=name)
        else:
            youtube.download_youtube_video(url=link, path=path, name=name)
        return True
    if PIXIV_IMAGE.search(link):
        raise PixivError("Require Pixiv login")
    if GFYCAT_LINK.search(link) or STREAMABLE_LINK.search(link):
        videos.download_video(url=link, path=path, name=name)
        return True
    if MAL_IMAGE.search(link) or TWITTER_IMAGE.search(link):
        images.download_image(url=link, path=path, name=name)
        return True
    if ext := IMAGE_GENERAL_LINK.match(link):
        images.download_image(url=link, path=path, name=name, ext=ext.group(1))
        return True
    print(link)
    save_not_media_post(url=link, path=path, name=name)


save_post_saved = partial(save_post, path=PATH_SAVED_POST)
save_post_upvoted = partial(save_post, path=PATH_UPVOTED_POST)


def archive_post_upvoted(r: praw.Reddit, db_path: str | Path = DB_PATH) -> None:
    with sqlite3.connect(db_path) as db:
        ids = db.execute(
            "SELECT id, permalink FROM post_votes WHERE direction = 'up' AND archived = 0"
        )
        while True:
            try:
                post_id, post_link = ids.fetchone()
            except TypeError:
                print("Finished")
                break
            print(f"Processing {post_id}")
            try:
                if save_post_upvoted(r=r, post_id=post_id):
                    # successfully archived
                    db.execute(
                        "UPDATE post_votes SET archived = 1 WHERE id = ?",
                        (post_id,),
                    )
                else:
                    # need re-check
                    db.execute(
                        "UPDATE post_votes SET archived = 10 WHERE id = ?",
                        (post_id,),
                    )
                db.commit()
            except DeletedPostError:
                # failed archival - deleted post
                error = "'deleted'"
                db.execute(
                    "UPDATE post_votes SET archived = 2 WHERE id = ?", (post_id,)
                )
                db.execute(
                    """INSERT INTO archive_errors (id, permalink, error)
                        VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET error = ?""",
                    (post_id, post_link, error, error),
                )
                db.commit()
            except Forbidden:
                # failed archival - private post
                error = "403"
                db.execute(
                    "UPDATE post_votes SET archived = 2 WHERE id = ?", (post_id,)
                )
                db.execute(
                    """INSERT INTO archive_errors (id, permalink, error)
                        VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET error = ?""",
                    (post_id, post_link, error, error),
                )
                db.commit()
            except DownloadError:
                # failed Youtube download
                error = "Youtube video deleted"
                db.execute(
                    "UPDATE post_votes SET archived = 2 WHERE id = ?", (post_id,)
                )
                db.execute(
                    """INSERT INTO archive_errors (id, permalink, error)
                    VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET error = ?""",
                    (post_id, post_link, error, error),
                )
                db.commit()
            except PixivError:
                # requires to implement Pixiv login
                error = "Pixiv login required"
                db.execute(
                    "UPDATE post_votes SET archived = 2 WHERE id = ?", (post_id,)
                )
                db.execute(
                    """INSERT INTO archive_errors (id, permalink, error)
                    VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET error = ?""",
                    (post_id, post_link, error, error),
                )
                db.commit()
            except MissingLinkError:
                # link post without an URL attached
                error = "Missing link"
                db.execute(
                    "UPDATE post_votes SET archived = 2 WHERE id = ?", (post_id,)
                )
                db.execute(
                    """INSERT INTO archive_errors (id, permalink, error)
                    VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET error = ?""",
                    (post_id, post_link, error, error),
                )
                db.commit()
            except ConnectionError as e:
                # failed to retrieve contents
                error = e.args[0]
                db.execute(
                    "UPDATE post_votes SET archived = 2 WHERE id = ?", (post_id,)
                )
                db.execute(
                    """INSERT INTO archive_errors (id, permalink, error)
                    VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET error = ?""",
                    (post_id, post_link, error, error),
                )
                db.commit()
            except NotMediaError as e:
                # unrecognised media type (e.g. URL pointing to a news article)
                error = e.args[0]
                db.execute(
                    "UPDATE post_votes SET archived = 3 WHERE id = ?", (post_id,)
                )
                db.execute(
                    """INSERT INTO archive_errors (id, permalink, error)
                    VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET error = ?""",
                    (post_id, post_link, error, error),
                )
                db.commit()


def main() -> None:
    r = praw.Reddit(
        client_id=os.environ.get("REDDIT_CLIENT_ID"),
        client_secret=os.environ.get("REDDIT_SECRET"),
        user_agent=os.environ.get("REDDIT_USER_AGENT"),
        username=os.environ.get("REDDIT_USERNAME"),
        password=os.environ.get("REDDIT_USER_PASSWORD"),
    )
    archive_post_upvoted(r)


if __name__ == "__main__":
    main()
