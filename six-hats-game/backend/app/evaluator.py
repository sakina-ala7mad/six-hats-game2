"""
evaluator.py
Scores a free-text scenario-mode answer against the hardcoded hat_guides.
This is a PLACEHOLDER (keyword overlap) — swap `evaluate_answer()` for a
real model call (Gemini / your ADK six-hats agent / an LLM judge) later.
The function signature is the contract the rest of the app relies on, so
the swap is a one-file change.
"""
import re


def _tokenize(text: str) -> set:
    return set(re.findall(r"[a-zA-Z']+", text.lower()))


def evaluate_answer(scenario: dict, hat: str, answer_text: str) -> dict:
    """
    Returns:
      {
        "correct": bool,          # good-faith attempt that fits the hat's lens
        "score": float 0-1,       # keyword overlap ratio, used as a creativity proxy
        "correction": str,        # shown to the player after the round
        "sample_answer": str,
      }
    """
    guide = scenario["hat_guides"][hat]
    keywords = [k.lower() for k in guide["keywords"]]
    tokens = _tokenize(answer_text)

    hits = sum(1 for kw in keywords if any(word in tokens for word in kw.split()))
    score = hits / max(1, len(keywords))
    correct = len(answer_text.strip()) >= 10 and score >= 0.15  # lenient placeholder threshold

    if correct:
        correction = f"Good {hat}-hat thinking — this stayed in the '{guide['keywords'][0]}' lane."
    else:
        correction = (
            f"This drifted outside the {hat} hat's lens. A {hat}-hat answer here would focus on: "
            f"{guide['sample_answer']}"
        )

    return {
        "correct": correct,
        "score": round(score, 2),
        "correction": correction,
        "sample_answer": guide["sample_answer"],
    }
