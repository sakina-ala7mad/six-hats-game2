"""
XP, level, and scoring rules for the Six Hats game.
All numbers here come directly from the game design spec.
"""

LEVEL_TIERS = [
    ("Easy", 0, 500),
    ("Medium", 500, 1500),
    ("Hard", 1500, 3000),
]

# baseline XP awarded to the WHOLE TEAM per scenario round, by difficulty
SCENARIO_TEAM_BASE_XP = {"easy": 100, "medium": 150, "hard": 200}

# XP per correct puzzle-mode question, by difficulty (individual)
PUZZLE_XP_PER_QUESTION = {"easy": 10, "medium": 20, "hard": 30}

SPEED_BONUS_PER_SECOND = 2      # xp per second remaining on the clock, individual
CREATIVITY_PENALTY = 5          # xp lost for a wrong/low-creativity puzzle answer
ROUND_SECONDS = 120              # 2 minute shared round timer for scenario mode
ANSWER_CHAR_LIMIT = 280           # free-text cap in scenario mode


def get_level_info(total_xp: int):
    """Returns (tier_name, xp_into_tier, xp_needed_for_tier, progress_fraction)."""
    for name, lo, hi in LEVEL_TIERS:
        if total_xp < hi or name == LEVEL_TIERS[-1][0]:
            span = hi - lo
            into = max(0, total_xp - lo)
            frac = min(1.0, into / span) if span else 1.0
            return name, into, span, frac
    name, lo, hi = LEVEL_TIERS[-1]
    return name, total_xp - lo, hi - lo, 1.0


def scenario_team_base_xp(level: str) -> int:
    return SCENARIO_TEAM_BASE_XP.get(level, 100)


def puzzle_question_xp(level: str) -> int:
    return PUZZLE_XP_PER_QUESTION.get(level, 10)


def speed_bonus(seconds_remaining: int) -> int:
    return max(0, int(seconds_remaining)) * SPEED_BONUS_PER_SECOND
