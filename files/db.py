"""
Persistence layer for the Six Hats game.
Uses SQLite so player accounts, team membership, and XP survive across
browser sessions and app restarts (file lives at data/game.db).
"""
import sqlite3
import uuid
import datetime as dt
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "game.db"


def _now():
    return dt.datetime.utcnow().isoformat()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS players (
                name_key TEXT PRIMARY KEY,      -- lowercased, used for uniqueness
                display_name TEXT NOT NULL,
                password TEXT,
                total_xp INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id TEXT PRIMARY KEY,
                name_key TEXT UNIQUE NOT NULL,  -- lowercased team name
                display_name TEXT NOT NULL,
                team_xp INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS team_members (
                team_id TEXT,
                player_key TEXT,
                joined_at TEXT,
                PRIMARY KEY (team_id, player_key)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                team_id TEXT,                    -- NULL for individual games
                host_key TEXT,
                mode TEXT,                        -- 'scenario'
                level TEXT,                       -- easy/medium/hard
                scenario_id TEXT,
                status TEXT,                       -- lobby / active / debrief / ended
                round_seconds INTEGER,
                round_start_at TEXT,
                created_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS game_players (
                game_id TEXT,
                player_key TEXT,
                display_name TEXT,
                hat TEXT,
                active INTEGER DEFAULT 1,
                submitted INTEGER DEFAULT 0,
                joined_at TEXT,
                PRIMARY KEY (game_id, player_key)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                game_id TEXT,
                player_key TEXT,
                display_name TEXT,
                hat TEXT,
                answer TEXT,
                is_correct INTEGER,
                correction TEXT,
                speed_bonus INTEGER,
                creativity_score INTEGER,
                submitted_at TEXT,
                PRIMARY KEY (game_id, player_key)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS xp_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_key TEXT,
                team_id TEXT,
                mode TEXT,          -- individual_puzzle / individual_scenario / team_puzzle / team_scenario
                xp INTEGER,
                timestamp TEXT
            )
        """)


# ---------- players ----------

def create_player(display_name: str, password: str):
    key = display_name.strip().lower()
    with get_conn() as conn:
        existing = conn.execute("SELECT 1 FROM players WHERE name_key=?", (key,)).fetchone()
        if existing:
            return False, "This name already exists, please use another name."
        conn.execute(
            "INSERT INTO players (name_key, display_name, password, total_xp, created_at) VALUES (?,?,?,?,?)",
            (key, display_name.strip(), password, 0, _now()),
        )
    return True, "created"


def get_player(display_name: str):
    key = display_name.strip().lower()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM players WHERE name_key=?", (key,)).fetchone()
        return dict(row) if row else None


def login_or_create_player(display_name: str, password: str):
    """Returns (player_dict, message, is_new)."""
    key = display_name.strip().lower()
    existing = get_player(display_name)
    if existing:
        if existing["password"] and existing["password"] != password:
            return None, "Wrong password for this name.", False
        return existing, "welcome back", False
    ok, msg = create_player(display_name, password)
    if not ok:
        return None, msg, False
    return get_player(display_name), "account created", True


def add_player_xp(display_name: str, xp: int, team_id: str, mode: str):
    key = display_name.strip().lower()
    with get_conn() as conn:
        conn.execute("UPDATE players SET total_xp = total_xp + ? WHERE name_key=?", (xp, key))
        conn.execute(
            "INSERT INTO xp_log (player_key, team_id, mode, xp, timestamp) VALUES (?,?,?,?,?)",
            (key, team_id, mode, xp, _now()),
        )


def get_player_current_team(display_name: str):
    key = display_name.strip().lower()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT t.* FROM teams t JOIN team_members m ON t.team_id = m.team_id
               WHERE m.player_key = ?""",
            (key,),
        ).fetchone()
        return dict(row) if row else None


# ---------- teams ----------

def create_team(team_name: str, creator_display_name: str):
    key = team_name.strip().lower()
    with get_conn() as conn:
        existing = conn.execute("SELECT 1 FROM teams WHERE name_key=?", (key,)).fetchone()
        if existing:
            return False, "This team name already exists, use another name.", None
        # a player can't be in two teams at once
        existing_team = get_player_current_team(creator_display_name)
        if existing_team:
            return False, f"You're already in team '{existing_team['display_name']}'.", None
        team_id = str(uuid.uuid4())[:8]
        conn.execute(
            "INSERT INTO teams (team_id, name_key, display_name, team_xp, created_at) VALUES (?,?,?,?,?)",
            (team_id, key, team_name.strip(), 0, _now()),
        )
        conn.execute(
            "INSERT INTO team_members (team_id, player_key, joined_at) VALUES (?,?,?)",
            (team_id, creator_display_name.strip().lower(), _now()),
        )
    return True, "created", team_id


def join_team(team_id: str, display_name: str):
    key = display_name.strip().lower()
    with get_conn() as conn:
        team = conn.execute("SELECT * FROM teams WHERE team_id=?", (team_id,)).fetchone()
        if not team:
            return False, "Team not found."
        existing_team = get_player_current_team(display_name)
        if existing_team:
            return False, f"You're already in team '{existing_team['display_name']}'."
        count = conn.execute(
            "SELECT COUNT(*) c FROM team_members WHERE team_id=?", (team_id,)
        ).fetchone()["c"]
        if count >= 6:
            return False, "This team is full. Please try to join another team or create one."
        conn.execute(
            "INSERT OR IGNORE INTO team_members (team_id, player_key, joined_at) VALUES (?,?,?)",
            (team_id, key, _now()),
        )
    return True, "joined"


def list_teams():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM teams").fetchall()
        teams = []
        for r in rows:
            members = conn.execute(
                "SELECT player_key FROM team_members WHERE team_id=?", (r["team_id"],)
            ).fetchall()
            teams.append({**dict(r), "member_count": len(members)})
        return teams


def get_team_members(team_id: str):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT m.player_key, p.display_name, p.total_xp FROM team_members m
               JOIN players p ON p.name_key = m.player_key
               WHERE m.team_id=? ORDER BY m.joined_at""",
            (team_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def add_team_xp(team_id: str, xp: int):
    with get_conn() as conn:
        conn.execute("UPDATE teams SET team_xp = team_xp + ? WHERE team_id=?", (xp, team_id))


def leave_team(team_id: str, display_name: str):
    key = display_name.strip().lower()
    with get_conn() as conn:
        conn.execute("DELETE FROM team_members WHERE team_id=? AND player_key=?", (team_id, key))


# ---------- games (scenario mode) ----------

def create_game(team_id, host_display_name, level, scenario_id, round_seconds=120):
    game_id = str(uuid.uuid4())[:8]
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO games (game_id, team_id, host_key, mode, level, scenario_id, status,
               round_seconds, round_start_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (game_id, team_id, host_display_name.strip().lower(), "scenario", level,
             scenario_id, "lobby", round_seconds, None, _now()),
        )
    return game_id


def get_game(game_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM games WHERE game_id=?", (game_id,)).fetchone()
        return dict(row) if row else None


def join_game(game_id, display_name, hat=None):
    key = display_name.strip().lower()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO game_players (game_id, player_key, display_name, hat, active, submitted, joined_at)
               VALUES (?,?,?,?,1,0,?)
               ON CONFLICT(game_id, player_key) DO UPDATE SET active=1""",
            (game_id, key, display_name.strip(), hat, _now()),
        )


def set_player_hat(game_id, player_key, hat):
    with get_conn() as conn:
        conn.execute(
            "UPDATE game_players SET hat=? WHERE game_id=? AND player_key=?", (hat, game_id, player_key)
        )


def get_game_players(game_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM game_players WHERE game_id=? ORDER BY joined_at", (game_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def set_player_active(game_id, player_key, active: bool):
    with get_conn() as conn:
        conn.execute(
            "UPDATE game_players SET active=? WHERE game_id=? AND player_key=?",
            (1 if active else 0, game_id, player_key),
        )


def start_round(game_id, round_seconds=120):
    with get_conn() as conn:
        conn.execute(
            "UPDATE games SET status='active', round_start_at=?, round_seconds=? WHERE game_id=?",
            (_now(), round_seconds, game_id),
        )


def set_game_status(game_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE games SET status=? WHERE game_id=?", (status, game_id))


def set_game_host(game_id, new_host_key):
    with get_conn() as conn:
        conn.execute("UPDATE games SET host_key=? WHERE game_id=?", (new_host_key, game_id))


def submit_answer(game_id, display_name, hat, answer, is_correct, correction, speed_bonus, creativity_score):
    key = display_name.strip().lower()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO submissions (game_id, player_key, display_name, hat, answer, is_correct,
               correction, speed_bonus, creativity_score, submitted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(game_id, player_key) DO UPDATE SET answer=excluded.answer""",
            (game_id, key, display_name, hat, answer, int(is_correct), correction,
             speed_bonus, creativity_score, _now()),
        )
        conn.execute(
            "UPDATE game_players SET submitted=1 WHERE game_id=? AND player_key=?", (game_id, key)
        )


def get_submissions(game_id):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM submissions WHERE game_id=?", (game_id,)).fetchall()
        return [dict(r) for r in rows]


# ---------- leaderboards ----------

def week_start_iso():
    today = dt.datetime.utcnow()
    start = today - dt.timedelta(days=today.weekday())
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.isoformat()


def leaderboard_individual(limit=20):
    """Only counts XP earned in individual-mode play, this week."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT p.display_name, SUM(x.xp) as weekly_xp, p.total_xp
               FROM xp_log x JOIN players p ON p.name_key = x.player_key
               WHERE x.mode LIKE 'individual_%' AND x.timestamp >= ?
               GROUP BY x.player_key ORDER BY weekly_xp DESC LIMIT ?""",
            (week_start_iso(), limit),
        ).fetchall()
        return [dict(r) for r in rows]


def leaderboard_teams(limit=20):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT t.display_name, SUM(x.xp) as weekly_xp, t.team_xp
               FROM xp_log x JOIN teams t ON t.team_id = x.team_id
               WHERE x.mode LIKE 'team_%' AND x.timestamp >= ? AND x.team_id IS NOT NULL
               GROUP BY x.team_id ORDER BY weekly_xp DESC LIMIT ?""",
            (week_start_iso(), limit),
        ).fetchall()
        return [dict(r) for r in rows]
