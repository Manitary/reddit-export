from pathlib import Path
from typing import Generator

import pandas as pd
import pangres
import sqlalchemy as sql

BASE_PATH = Path().resolve()
DB_NAME = "reddit-export.sqlite"
DB_PATH = BASE_PATH / "data" / DB_NAME
QUERY_PATH = BASE_PATH / "src" / "db"
CSV_PATH = BASE_PATH / "csv"

TABLES = {
    "comment_headers",
    "comment_votes",
    "hidden_posts",
    "message_headers",
    "messages",
    "poll_votes",
    "post_headers",
    "post_votes",
    "posts",
    "saved_comments",
    "saved_posts",
}


def get_query(query_name: str) -> Generator[sql.TextClause, None, None]:
    path = QUERY_PATH / f"{query_name}.sql"
    with path.open() as f:
        queries = f.read()
    for query in queries.split(";"):
        yield sql.sql.text(query)


def populate_table(engine: sql.Engine, table: str) -> None:
    # The relevant CSV files have the first column as the index
    df = pd.read_csv(CSV_PATH / f"{table}.csv", index_col=0)  # type: ignore

    with engine.connect() as db:
        # pandas' ``to_sql`` cannot do upserts, so we use pangres
        pangres.upsert(  # type: ignore
            con=db, df=df, table_name=table, if_row_exists="update", chunksize=2000
        )
        db.commit()


def populate_all_tables(engine: sql.Engine) -> None:
    for table in TABLES:
        populate_table(engine, table)


def test(db_path: str | Path = DB_PATH) -> None:
    engine = sql.create_engine(rf"sqlite:///{db_path}")
    populate_all_tables(engine)


if __name__ == "__main__":
    test()
