from dataclasses import dataclass
from pathlib import Path

PATH_DATA = Path().resolve() / "data"


@dataclass
class Table:
    name: str
    get_query: str
    path: Path

    @property
    def success_query(self) -> str:
        return f"UPDATE {self.name} SET archived = 1 WHERE id = :id"

    @property
    def fail_query(self) -> str:
        return f"UPDATE {self.name} SET archived = :fail_code WHERE id = :id"


TABLES = {
    "post_votes": Table(
        name="post_votes",
        get_query="SELECT id, permalink FROM post_votes WHERE direction = 'up' AND archived = 0",
        path=PATH_DATA / "upvoted" / "posts",
    ),
    "saved_posts": Table(
        name="saved_posts",
        get_query="SELECT id, permalink FROM saved_posts WHERE archived = 0",
        path=PATH_DATA / "saved" / "posts",
    ),
}
