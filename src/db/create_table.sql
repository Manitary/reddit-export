CREATE TABLE IF NOT EXISTS comment_votes (
    id TEXT PRIMARY KEY,
    permalink TEXT UNIQUE,
    direction TEXT,
    archived INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS post_votes (
    id TEXT PRIMARY KEY,
    permalink TEXT UNIQUE,
    direction TEXT,
    archived INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS saved_comments (
    id TEXT PRIMARY KEY,
    permalink TEXT UNIQUE,
    archived INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS saved_posts (
    id TEXT PRIMARY KEY,
    permalink TEXT UNIQUE,
    archived INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS archive_errors (
    id TEXT PRIMARY KEY,
    permalink TEXT UNIQUE,
    error TEXT
);
