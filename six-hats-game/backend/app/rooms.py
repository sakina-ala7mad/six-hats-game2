"""
rooms.py
In-memory live game rooms. One GameRoom = one running game (team or solo,
puzzle or scenario). State lives in memory for zero-delay updates and is
flushed to SQLite (XP only) at round/game end — matches the "no refresh,
instant updates" requirement, which a plain Streamlit rerun model can't do.

A process restart loses in-flight rounds but never loses XP, since XP is
only committed to the DB once a round actually finishes.
"""
import time
import uuid
from dataclasses import dataclass, field

from . import database, game_logic, scenario_store, evaluator


@dataclass
class PlayerState:
    name: str
    hat: str | None = None
    submitted: bool = False
    answer: str | None = None
    seconds_left_on_submit: int | None = None
    connected: bool = True


@dataclass
class GameRoom:
    game_id: str
    mode: str                 # 'puzzle' | 'scenario'
    is_team: bool
    level: str                # 'easy' | 'medium' | 'hard'
    team_id: str | None
    host: str
    players: dict = field(default_factory=dict)   # name -> PlayerState
    status: str = "lobby"      # lobby | active | round_result | ended
    scenario: dict | None = None
    puzzle: dict | None = None
    round_started_at: float | None = None
    round_seconds: int = game_logic.ROUND_SECONDS
    last_round_result: dict | None = None
    created_at: float = field(default_factory=time.time)

    # ---- lobby ----
    def add_player(self, name: str):
        if name not in self.players:
            self.players[name] = PlayerState(name=name)
        else:
            self.players[name].connected = True

    def remove_player(self, name: str):
        """Player leaves/disconnects mid-game: never pause the game for it."""
        if name in self.players:
            self.players[name].connected = False
        if name == self.host:
            remaining = [p for p, s in self.players.items() if s.connected]
            new_host = game_logic.reassign_host(self.host, remaining)
            if new_host:
                self.host = new_host
            else:
                self.status = "ended"

    def active_player_names(self) -> set:
        return {p for p, s in self.players.items() if s.connected}

    # ---- round lifecycle ----
    def start_round(self):
        names = list(self.active_player_names())
        assigned = game_logic.assign_hats(names)
        for name, hat in assigned.items():
            self.players[name].hat = hat
            self.players[name].submitted = False
            self.players[name].answer = None

        scenario = scenario_store.random_scenario(self.level)
        self.scenario = scenario
        if self.mode == "puzzle":
            self.puzzle = scenario_store.puzzle_payload(scenario)
        self.status = "active"
        self.round_started_at = time.time()
        self.last_round_result = None

    def seconds_left(self) -> int:
        if not self.round_started_at:
            return self.round_seconds
        elapsed = time.time() - self.round_started_at
        return max(0, int(self.round_seconds - elapsed))

    def submit_answer(self, player_name: str, payload: dict) -> bool:
        state = self.players.get(player_name)
        if not state or state.submitted or not state.connected:
            return False
        state.submitted = True
        state.answer = payload
        state.seconds_left_on_submit = self.seconds_left()
        if game_logic.should_end_round(
            {p for p, s in self.players.items() if s.submitted},
            self.active_player_names(),
        ):
            self.finish_round()
        return True

    def finish_round(self):
        self.status = "round_result"
        results = {}
        team_xp_total = 0

        if self.mode == "scenario":
            baseline = game_logic.scenario_round_team_xp(self.level)
            team_xp_total += baseline
            for name, state in self.players.items():
                if not state.hat or state.answer is None:
                    continue
                eval_result = evaluator.evaluate_answer(self.scenario, state.hat, state.answer.get("text", ""))
                first = self._is_fastest(name)
                bonus = game_logic.scenario_individual_bonus(
                    state.seconds_left_on_submit or 0, eval_result["correct"], first
                )
                results[name] = {
                    "hat": state.hat,
                    "answer": state.answer.get("text", ""),
                    **eval_result,
                    "individual_bonus_xp": bonus,
                    "first_submitter": first,
                }
                self._award_player(name, bonus, "scenario_bonus")
            if self.is_team and self.team_id:
                database.add_team_xp(self.team_id, team_xp_total, "scenario_round")
            elif not self.is_team:
                # solo scenario mode: baseline goes to the player instead of a team
                for name in self.players:
                    self._award_player(name, team_xp_total, "scenario_round_solo")

        else:  # puzzle mode
            for name, state in self.players.items():
                if state.answer is None:
                    continue
                answers = state.answer.get("matches", {})  # {sentence_id: hat}
                key = self.puzzle["_answer_key"]
                per_q = []
                total = 0
                for sid_str, chosen_hat in answers.items():
                    sid = int(sid_str)
                    correct = key.get(sid) == chosen_hat
                    xp = game_logic.puzzle_question_xp(
                        self.level, correct, state.seconds_left_on_submit or 0
                    )
                    total += xp
                    per_q.append({
                        "sentence_id": sid,
                        "chosen_hat": chosen_hat,
                        "correct_hat": key.get(sid),
                        "correct": correct,
                    })
                results[name] = {"per_question": per_q, "xp": total}
                self._award_player(name, total, "puzzle_round")

        self.last_round_result = {
            "mode": self.mode,
            "scenario_title": self.scenario["title"],
            "scenario_text": self.scenario["scenario_text"],
            "results": results,
            "team_xp": team_xp_total if self.mode == "scenario" else None,
        }

    def _is_fastest(self, player_name: str) -> bool:
        times = [
            (n, s.seconds_left_on_submit)
            for n, s in self.players.items()
            if s.submitted and s.seconds_left_on_submit is not None
        ]
        if not times:
            return False
        fastest = max(times, key=lambda t: t[1])[0]  # more seconds left = submitted first
        return fastest == player_name

    def _award_player(self, name: str, amount: int, reason: str):
        database.add_player_xp(name, amount, reason)

    def debrief(self) -> dict | None:
        """Side-by-side answers grouped by hat — the post-round discussion artifact."""
        if not self.last_round_result or self.mode != "scenario":
            return None
        by_hat = {}
        for name, r in self.last_round_result["results"].items():
            by_hat[r["hat"]] = {"player": name, "answer": r["answer"], "correct": r["correct"]}
        return {
            "scenario_text": self.last_round_result["scenario_text"],
            "by_hat": by_hat,
        }

    def public_state(self) -> dict:
        return {
            "game_id": self.game_id,
            "mode": self.mode,
            "is_team": self.is_team,
            "level": self.level,
            "host": self.host,
            "status": self.status,
            "seconds_left": self.seconds_left() if self.status == "active" else None,
            "scenario_text": self.scenario["scenario_text"] if self.scenario and self.status != "lobby" else None,
            "players": [
                {
                    "name": p.name,
                    "hat": p.hat if self.status != "lobby" else None,
                    "submitted": p.submitted,
                    "connected": p.connected,
                }
                for p in self.players.values()
            ],
            "last_round_result": self.last_round_result,
        }


class GameManager:
    def __init__(self):
        self.rooms: dict[str, GameRoom] = {}

    def create_room(self, host: str, mode: str, is_team: bool, level: str, team_id: str | None) -> GameRoom:
        game_id = uuid.uuid4().hex[:6]
        room = GameRoom(game_id=game_id, mode=mode, is_team=is_team, level=level, team_id=team_id, host=host)
        room.add_player(host)
        self.rooms[game_id] = room
        return room

    def get(self, game_id: str) -> GameRoom | None:
        return self.rooms.get(game_id)

    def remove_if_ended(self, game_id: str):
        room = self.rooms.get(game_id)
        if room and room.status == "ended":
            del self.rooms[game_id]

    def find_active_by_team(self, team_id: str) -> "GameRoom | None":
        for room in self.rooms.values():
            if room.team_id == team_id and room.status != "ended":
                return room
        return None


manager = GameManager()
