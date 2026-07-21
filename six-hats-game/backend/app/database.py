"""
database.py
Persistent storage (SQLite) for players, teams, and XP history.
Player and team names are matched CASE-INSENSITIVELY (COLLATE NOCASE),
so "Sara" and "sara" are the same account, but the original casing
typed at signup is preserved for display.
"""
import sqlite3
import uuid
import time
from contextlib import contextmanager
from pathlib import Path
from passlib.hash import bcrypt

DB_PATH = Path(__file__).parent.parent / "data" / "sixhats.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    name            TEXT PRIMARY KEY COLLATE NOCASE,
    display_name    TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    xp              INTEGER NOT NULL DEFAULT 0,
    team_id         TEXT,
    created_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS teams (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name    TEXT NOT NULL,
    xp              INTEGER NOT NULL DEFAULT 0,
    created_at      REAL NOT NULL
);

-- one row per XP-earning event, used to compute the WEEKLY leaderboard
CREATE TABLE IF NOT EXISTS xp_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type    TEXT NOT NULL,   -- 'player' | 'team'
    subject_id      TEXT NOT NULL,   -- player name or team id
    amount          INTEGER NOT NULL,
    reason          TEXT,
    created_at      REAL NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---------- players ----------

def create_player(name: str, password: str) -> dict:
    with get_conn() as conn:
        existing = conn.execute("SELECT name FROM players WHERE name = ?", (name,)).fetchone()
        if existing:
            raise ValueError("NAME_TAKEN")
        conn.execute(
            "INSERT INTO players (name, display_name, password_hash, xp, created_at) VALUES (?,?,?,0,?)",
            (name, name, bcrypt.hash(password), time.time()),
        )
        row = conn.execute("SELECT * FROM players WHERE name = ?", (name,)).fetchone()
        return dict(row)


def get_player(name: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM players WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None


def verify_player(name: str, password: str) -> dict | None:
    player = get_player(name)
    if not player:
        return None
    if not bcrypt.verify(password, player["password_hash"]):
        return None
    return player


def add_player_xp(name: str, amount: int, reason: str = ""):
    with get_conn() as conn:
        conn.execute("UPDATE players SET xp = MAX(0, xp + ?) WHERE name = ?", (amount, name))
        conn.execute(
            "INSERT INTO xp_log (subject_type, subject_id, amount, reason, created_at) VALUES ('player',?,?,?,?)",
            (name, amount, reason, time.time()),
        )


def set_player_team(name: str, team_id: str | None):
    with get_conn() as conn:
        conn.execute("UPDATE players SET team_id = ? WHERE name = ?", (team_id, name))


# ---------- teams ----------

def create_team(name: str, creator_name: str) -> dict:
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM teams WHERE name = ?", (name,)).fetchone()
        if existing:
            raise ValueError("TEAM_NAME_TAKEN")
        team_id = uuid.uuid4().hex[:8]
        conn.execute(
            "INSERT INTO teams (id, name, display_name, xp, created_at) VALUES (?,?,?,0,?)",
            (team_id, name, name, time.time()),
        )
        conn.execute("UPDATE players SET team_id = ? WHERE name = ?", (team_id, creator_name))
        row = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        return dict(row)


def get_team(team_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
        return dict(row) if row else None


def list_open_teams() -> list[dict]:
    """Teams with < 6 members, for the join screen."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.name, t.xp, COUNT(p.name) AS member_count
            FROM teams t LEFT JOIN players p ON p.team_id = t.id
            GROUP BY t.id
            ORDER BY t.created_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def team_members(team_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT name, xp FROM players WHERE team_id = ?", (team_id,)).fetchall()
        return [dict(r) for r in rows]


def join_team(player_name: str, team_id: str) -> dict:
    members = team_members(team_id)
    if len(members) >= 6:
        raise ValueError("TEAM_FULL")
    set_player_team(player_name, team_id)
    return get_team(team_id)


def add_team_xp(team_id: str, amount: int, reason: str = ""):
    with get_conn() as conn:
        conn.execute("UPDATE teams SET xp = MAX(0, xp + ?) WHERE id = ?", (amount, team_id))
        conn.execute(
            "INSERT INTO xp_log (subject_type, subject_id, amount, reason, created_at) VALUES ('team',?,?,?,?)",
            (team_id, amount, reason, time.time()),
        )


# ---------- dashboard ----------

WEEK_SECONDS = 7 * 24 * 3600


def weekly_individual_leaderboard(limit: int = 50) -> list[dict]:
    cutoff = time.time() - WEEK_SECONDS
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.name, p.xp AS total_xp, COALESCE(SUM(x.amount), 0) AS weekly_xp
            FROM players p
            LEFT JOIN xp_log x ON x.subject_type='player' AND x.subject_id = p.name AND x.created_at >= ?
            GROUP BY p.name
            ORDER BY weekly_xp DESC, total_xp DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def weekly_team_leaderboard(limit: int = 50) -> list[dict]:
    cutoff = time.time() - WEEK_SECONDS
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.name, t.xp AS total_xp, COALESCE(SUM(x.amount), 0) AS weekly_xp
            FROM teams t
            LEFT JOIN xp_log x ON x.subject_type='team' AND x.subject_id = t.id AND x.created_at >= ?
            GROUP BY t.id
            ORDER BY weekly_xp DESC, total_xp DESC
            LIMIT ?
            """,
            (cutoff, limit),
        ).fetchall()
        return [dict(r) for r in rows]
