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


class DeletedPostError(Exception):
    ...


@sleep_and_retry
@limits(calls=60, period=60)
def get_submission(reddit: praw.Reddit, post_id: str) -> Submission:
    return reddit.submission(post_id)


def save_post(reddit: praw.Reddit, post_id: str, path: Path) -> bool:
    post: Submission = get_submission(reddit, post_id)
    try:
        post: Submission = get_submission(reddit, post.crosspost_parent[3:])
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
    try:
        if save_link_post(post=post, path=path / sub_name, name=full_title):
            return True
    except (ConnectionError, ValueError) as e:
        print(e)
    return False


def save_text_post(post: Submission, path: Path, name: str) -> None:
    body: str = post.selftext
    if body == "[removed]":
        raise DeletedPostError
    file_path = path / f"{name}.txt"
    file_path = fix_file_path(file_path)
    if file_path.is_file():
        print("Text post already archived")
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        f.write(body)


def save_link_post(post: Submission, path: Path, name: str) -> bool:
    link: str = post.url
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
    return False


save_post_saved = partial(save_post, path=PATH_SAVED_POST)
save_post_upvoted = partial(save_post, path=PATH_UPVOTED_POST)


def archive_post_upvoted(reddit: praw.Reddit, db_path: str | Path = DB_PATH) -> None:
    with sqlite3.connect(db_path) as db:
        ids = db.execute(
            "SELECT id, permalink FROM post_votes WHERE direction = 'up' AND archived = 0"
        )
        while ids:
            post_id, post_link = ids.fetchone()
            print(f"Processing {post_id}")
            try:
                if save_post_upvoted(reddit=reddit, post_id=post_id):
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
                db.execute(
                    "UPDATE post_votes SET archived = 2 WHERE id = ?", (post_id,)
                )
                db.execute(
                    """INSERT INTO archive_errors (id, permalink, error)
                        VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET error = 'deleted'""",
                    (post_id, post_link, "deleted"),
                )
                db.commit()
            except Forbidden:
                # failed archival - private post
                db.execute(
                    "UPDATE post_votes SET archived = 2 WHERE id = ?", (post_id,)
                )
                db.execute(
                    """INSERT INTO archive_errors (id, permalink, error)
                        VALUES (?, ?, ?) ON CONFLICT DO UPDATE SET error = '403'""",
                    (post_id, post_link, "403"),
                )
                db.commit()


def main() -> None:
    reddit = praw.Reddit(
        client_id=os.environ.get("REDDIT_CLIENT_ID"),
        client_secret=os.environ.get("REDDIT_SECRET"),
        user_agent=os.environ.get("REDDIT_USER_AGENT"),
        username=os.environ.get("REDDIT_USERNAME"),
        password=os.environ.get("REDDIT_USER_PASSWORD"),
    )
    archive_post_upvoted(reddit)


if __name__ == "__main__":
    main()
