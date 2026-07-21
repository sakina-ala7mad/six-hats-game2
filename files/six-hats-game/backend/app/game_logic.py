"""
game_logic.py
Pure game-rule functions — no I/O, no websockets, easy to unit test.
Encodes the XP / leveling / hat-assignment rules from the design doc.
"""
import random

HATS = ["white", "red", "black", "yellow", "green", "blue"]

LEVELS = [
    ("easy", 0, 500),
    ("medium", 500, 1500),
    ("hard", 1500, 3000),
]

BASELINE_TEAM_XP = {"easy": 100, "medium": 150, "hard": 200}
PUZZLE_XP_PER_QUESTION = {"easy": 10, "medium": 20, "hard": 30}
SPEED_BONUS_PER_SECOND_LEFT = 2       # xp per second remaining, individual
CREATIVITY_PENALTY = -5               # scenario-mode wrong/low-effort answer, individual
ROUND_SECONDS = 120                   # 2-minute shared timer


def level_for_xp(xp: int) -> str:
    for level, lo, hi in LEVELS:
        if lo <= xp < hi:
            return level
    return "hard"  # 3000+ stays at hard (cap can be raised later)


def puzzle_question_xp(level: str, correct: bool, seconds_left: int) -> int:
    """XP for a single puzzle-mode match (hat -> sentence)."""
    if not correct:
        return 0
    base = PUZZLE_XP_PER_QUESTION[level]
    speed_bonus = max(0, seconds_left) * SPEED_BONUS_PER_SECOND_LEFT
    return base + speed_bonus


def scenario_round_team_xp(level: str) -> int:
    """Flat XP the whole team gets for completing a scenario round, regardless of who's left."""
    return BASELINE_TEAM_XP[level]


def scenario_individual_bonus(seconds_left: int, creativity_ok: bool, first_submitter: bool) -> int:
    """
    Per-player bonus on top of the team's baseline XP.
    - speed bonus: 2xp per second remaining when they submitted
    - first submitter gets the speed bonus counted (already reflected by seconds_left being highest)
    - creativity: ML model scores the answer; if judged weak, apply the penalty
    """
    bonus = max(0, seconds_left) * SPEED_BONUS_PER_SECOND_LEFT
    if not creativity_ok:
        bonus += CREATIVITY_PENALTY
    return bonus


def assign_hats(player_names: list[str], host_selected_hats: list[str] | None = None) -> dict:
    """
    Random hat assignment, no repeats, no host override of WHO gets what.
    - 6 players  -> all 6 hats auto-assigned, one each.
    - 2-5 players -> host pre-selects which hats are "in play" (host_selected_hats);
                     those are shuffled and assigned 1:1. If the host hasn't chosen,
                     we auto-pick a random subset of the right size so the game is
                     never blocked waiting on host input.
    Returns {player_name: hat}.
    """
    n = len(player_names)
    if n == 0:
        return {}
    n = min(n, 6)
    if n == 6:
        pool = HATS[:]
    else:
        if host_selected_hats and len(host_selected_hats) == n:
            pool = host_selected_hats[:]
        else:
            pool = random.sample(HATS, n)
    random.shuffle(pool)
    return {player_names[i]: pool[i] for i in range(n)}


def reassign_host(current_host: str, remaining_players: list[str]) -> str | None:
    """If the host leaves, hand hosting to the next remaining player (join order)."""
    others = [p for p in remaining_players if p != current_host]
    return others[0] if others else None


def should_end_round(submitted: set, active_players: set) -> bool:
    """Round ends when everyone still active has submitted (leavers don't block it)."""
    return active_players.issubset(submitted) or len(active_players) == 0


def should_end_game(active_players: set) -> bool:
    return len(active_players) == 0
