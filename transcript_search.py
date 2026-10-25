"""Index YouTube transcripts in SQLite and search them with timestamped links.

    python transcript_search.py add URL [URL ...] [--lang en] [--max-calls N]
    python transcript_search.py search "query words" [--limit 5]

Needs SUPADATA_API_KEY for `add`. `search` is offline and costs nothing.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone

from supadata import Supadata
from supadata.errors import SupadataError

DB_PATH = os.environ.get("TRANSCRIPT_DB", "transcripts.db")
VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})")

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    video_id   TEXT PRIMARY KEY,
    url        TEXT NOT NULL,
    lang       TEXT,
    chunks     INTEGER NOT NULL,
    fetched_at TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
    text,
    video_id UNINDEXED,
    start_ms UNINDEXED,
    tokenize = 'porter unicode61'
);
"""


def connect(path: str = DB_PATH) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


def video_id_from(url: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    match = VIDEO_ID.search(url)
    if not match:
        raise ValueError(f"Not a YouTube video URL: {url}")
    return match.group(1)


def add_videos(urls: list[str], lang: str | None, max_calls: int) -> int:
    api_key = os.environ.get("SUPADATA_API_KEY")
    if not api_key:
        sys.exit("Set SUPADATA_API_KEY first.")
    client = Supadata(api_key=api_key)
    db = connect()
    calls = 0
    for url in urls:
        vid = video_id_from(url)
        if db.execute("SELECT 1 FROM videos WHERE video_id = ?", (vid,)).fetchone():
            print(f"skip     {vid} (already indexed)")
            continue
        if calls >= max_calls:
            print(f"stop     --max-calls {max_calls} reached before {vid}")
            break
        calls += 1
        try:
            result = client.transcript(
                url=f"https://www.youtube.com/watch?v={vid}",
                lang=lang,
                text=False,       # keep timestamped chunks
                chunk_size=300,   # merge short captions into ~300-char passages
                mode="native",    # existing captions only, no AI generation
            )
        except SupadataError as exc:
            print(f"error    {vid}: {exc.error}: {exc.message}")
            continue
        if not isinstance(result.content, list) or not result.content:
            print(f"error    {vid}: no inline transcript (job or empty)")
            continue
        with db:
            db.executemany(
                "INSERT INTO chunks (text, video_id, start_ms) VALUES (?, ?, ?)",
                [(c.text, vid, c.offset) for c in result.content if c.text.strip()],
            )
            db.execute(
                "INSERT INTO videos VALUES (?, ?, ?, ?, ?)",
                (
                    vid,
                    f"https://www.youtube.com/watch?v={vid}",
                    result.lang,
                    len(result.content),
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
        print(f"indexed  {vid} lang={result.lang} chunks={len(result.content)}")
    print(f"api_calls: {calls}")
    return calls


def search(query: str, limit: int) -> list[tuple]:
    db = connect()
    rows = db.execute(
        """
        SELECT video_id, start_ms,
               snippet(chunks, 0, '[', ']', ' ... ', 18) AS excerpt
        FROM chunks
        WHERE chunks MATCH ?
        ORDER BY bm25(chunks)
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()
    for vid, start_ms, excerpt in rows:
        seconds = int(start_ms) // 1000
        stamp = f"{seconds // 60}:{seconds % 60:02d}"
        print(f"{vid} @ {stamp}  https://youtu.be/{vid}?t={seconds}")
        print(f"    {' '.join(excerpt.split())}")
    if not rows:
        print("no matches")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="fetch transcripts and index them")
    add.add_argument("urls", nargs="+")
    add.add_argument("--lang", default="en")
    add.add_argument("--max-calls", type=int, default=5)
    find = sub.add_parser("search", help="full-text search, offline")
    find.add_argument("query")
    find.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    if args.command == "add":
        add_videos(args.urls, args.lang, args.max_calls)
    else:
        search(args.query, args.limit)


if __name__ == "__main__":
    main()
