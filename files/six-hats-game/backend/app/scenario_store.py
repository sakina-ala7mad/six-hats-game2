"""
scenario_store.py
Loads dataset/scenarios.json once at startup and serves scenarios by level.
This is the ONLY file you need to touch to grow the dataset later, or to
swap in the real ML-generated scenario pipeline mentioned in the design doc
(replace load_scenarios() with a call to your model/agent).
"""
import json
import random
from pathlib import Path
from functools import lru_cache

DATASET_PATH = Path(__file__).parent.parent.parent / "dataset" / "scenarios.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(DATASET_PATH, encoding="utf-8") as f:
        return json.load(f)


def hat_meta() -> dict:
    return _load()["meta"]["hats"]


def all_scenarios() -> list[dict]:
    return _load()["scenarios"]


def scenarios_by_level(level: str) -> list[dict]:
    return [s for s in all_scenarios() if s["level"] == level]


def random_scenario(level: str, exclude_ids: list[str] | None = None) -> dict:
    pool = scenarios_by_level(level)
    exclude_ids = exclude_ids or []
    filtered = [s for s in pool if s["id"] not in exclude_ids] or pool
    return random.choice(filtered)


def puzzle_payload(scenario: dict) -> dict:
    """Shuffled sentences (hat hidden) for the player to match — puzzle mode."""
    sentences = [{"sentence_id": i, "text": s["sentence"]} for i, s in enumerate(scenario["puzzle_sentences"])]
    random.shuffle(sentences)
    answer_key = {i: s["hat"] for i, s in enumerate(scenario["puzzle_sentences"])}
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "level": scenario["level"],
        "sentences": sentences,
        "_answer_key": answer_key,  # server-side only, stripped before sending to client
    }


def scenario_payload_for_hat(scenario: dict, hat: str) -> dict:
    """What a single player sees in scenario mode: the scenario + their assigned hat's role card."""
    guide = scenario["hat_guides"][hat]
    return {
        "id": scenario["id"],
        "title": scenario["title"],
        "level": scenario["level"],
        "scenario_text": scenario["scenario_text"],
        "your_hat": hat,
        "role_card": {
            **hat_meta()[hat],
            "example_sentence": next(
                (s["sentence"] for s in scenario["puzzle_sentences"] if s["hat"] == hat), ""
            ),
        },
        "char_limit": 280,
    }
