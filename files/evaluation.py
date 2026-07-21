"""
Answer evaluation.

Puzzle mode: exact match against the hardcoded correct hat -> deterministic,
no ML needed.

Scenario mode: real evaluation is meant to be an ML model (per the project's
Six-Hats agent capstone). That model is "in progress" per the design notes,
so this module is a clearly-labeled placeholder: it scores free-text answers
by how well they match the expected hat's keyword focus, so the game is
fully playable today and the ML model can be dropped in later by replacing
`evaluate_scenario_answer` without touching any UI code.
"""
import re

_HAT_KEYWORDS = {
    "white": ["data", "fact", "number", "know", "information", "report", "evidence", "stat"],
    "red": ["feel", "feels", "felt", "emotion", "gut", "worried", "excited", "uneasy", "anxious"],
    "black": ["risk", "fail", "wrong", "problem", "danger", "downside", "concern", "could go wrong"],
    "yellow": ["benefit", "opportunity", "upside", "positive", "could help", "gain", "value", "improve"],
    "green": ["what if", "idea", "creative", "alternative", "different", "imagine", "instead"],
    "blue": ["plan", "process", "next step", "agenda", "summarize", "organize", "decide", "timeline"],
}


def evaluate_puzzle_answer(chosen_hat: str, correct_hat: str):
    is_correct = chosen_hat == correct_hat
    return is_correct


def evaluate_scenario_answer(answer_text: str, hat: str, hat_prompt: str):
    """
    Placeholder evaluator. Returns (is_correct: bool, creativity_score: 0-100,
    correction: str explaining what a strong answer for this hat looks like).
    Swap this function's body for a real ML call when the model is ready —
    signature stays the same so nothing else in the app needs to change.
    """
    text = (answer_text or "").lower().strip()
    keywords = _HAT_KEYWORDS.get(hat, [])
    hits = sum(1 for kw in keywords if kw in text)
    length_ok = len(text) >= 15

    creativity_score = min(100, hits * 20 + (15 if length_ok else 0) + min(len(text), 60))
    is_correct = hits >= 1 and length_ok

    if is_correct:
        correction = f"Good {hat} hat thinking — that lines up with: \"{hat_prompt}\""
    else:
        correction = (
            f"This answer doesn't quite stay in the {hat} hat lane yet. "
            f"A {hat} hat response should address: \"{hat_prompt}\""
        )
    return is_correct, creativity_score, correction
