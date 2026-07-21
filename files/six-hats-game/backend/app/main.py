"""
main.py
FastAPI entrypoint. REST for auth/teams/dashboard, WebSocket for live gameplay.
Run with:  uvicorn app.main:app --host 0.0.0.0 --port 8000
Serves the static frontend from /frontend so the whole thing is one
deployable service with one public URL.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import database, game_logic, scenario_store
from .rooms import manager
from .ws_manager import ws_manager

app = FastAPI(title="Six Hats Game")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

database.init_db()

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


# ---------------- schemas ----------------

class RegisterIn(BaseModel):
    name: str
    password: str


class LoginIn(BaseModel):
    name: str
    password: str


class CreateTeamIn(BaseModel):
    player_name: str
    team_name: str


class JoinTeamIn(BaseModel):
    player_name: str
    team_id: str


class CreateGameIn(BaseModel):
    host_name: str
    mode: str          # 'puzzle' | 'scenario'
    is_team: bool
    level: str = "easy"
    team_id: str | None = None


# ---------------- auth ----------------

@app.post("/api/players/register")
def register(body: RegisterIn):
    try:
        player = database.create_player(body.name.strip(), body.password)
    except ValueError:
        raise HTTPException(409, "This name already exists, please use another name.")
    return _player_out(player)


@app.post("/api/players/login")
def login(body: LoginIn):
    player = database.verify_player(body.name.strip(), body.password)
    if not player:
        raise HTTPException(401, "Name and password don't match, or the account doesn't exist.")
    return _player_out(player)


def _player_out(player: dict) -> dict:
    return {
        "name": player["display_name"],
        "xp": player["xp"],
        "level": game_logic.level_for_xp(player["xp"]),
        "team_id": player["team_id"],
    }


# ---------------- teams ----------------

@app.get("/api/teams")
def list_teams():
    return database.list_open_teams()


@app.post("/api/teams/create")
def create_team(body: CreateTeamIn):
    try:
        team = database.create_team(body.team_name.strip(), body.player_name.strip())
    except ValueError:
        raise HTTPException(409, "This team name already exists, please use another name.")
    return team


@app.post("/api/teams/join")
def join_team(body: JoinTeamIn):
    try:
        team = database.join_team(body.player_name.strip(), body.team_id)
    except ValueError:
        raise HTTPException(409, "This team is full, please try another team or create one.")
    return {"team": team, "members": database.team_members(body.team_id)}


@app.get("/api/teams/{team_id}/members")
def get_team_members(team_id: str):
    return database.team_members(team_id)


# ---------------- scenarios / intro ----------------

@app.get("/api/hats-intro")
def hats_intro():
    return scenario_store.hat_meta()


# ---------------- dashboard ----------------

@app.get("/api/dashboard")
def dashboard():
    return {
        "individuals": database.weekly_individual_leaderboard(),
        "teams": database.weekly_team_leaderboard(),
    }


# ---------------- game create/join (REST bootstraps the room, WS drives it) ----------------

@app.post("/api/games/create")
def create_game(body: CreateGameIn):
    room = manager.create_room(
        host=body.host_name.strip(),
        mode=body.mode,
        is_team=body.is_team,
        level=body.level,
        team_id=body.team_id,
    )
    return {"game_id": room.game_id}


@app.post("/api/games/{game_id}/join")
def join_game(game_id: str, player_name: str):
    room = manager.get(game_id)
    if not room:
        raise HTTPException(404, "Game not found.")
    if len(room.active_player_names()) >= 6:
        raise HTTPException(409, "This game's team is full.")
    room.add_player(player_name)
    return room.public_state()


@app.get("/api/teams/{team_id}/active-game")
def team_active_game(team_id: str):
    room = manager.find_active_by_team(team_id)
    return {"game_id": room.game_id} if room else {"game_id": None}


@app.get("/api/games/{game_id}")
def game_state(game_id: str):
    room = manager.get(game_id)
    if not room:
        raise HTTPException(404, "Game not found.")
    return room.public_state()


# ---------------- websocket: the live game loop ----------------

@app.websocket("/ws/game/{game_id}/{player_name}")
async def game_socket(websocket: WebSocket, game_id: str, player_name: str):
    room = manager.get(game_id)
    if not room:
        await websocket.close(code=4404)
        return

    await ws_manager.connect(game_id, player_name, websocket)
    room.add_player(player_name)
    await ws_manager.broadcast(game_id, {"type": "state", "state": room.public_state()})

    try:
        while True:
            msg = await websocket.receive_json()
            action = msg.get("action")

            if action == "start_round" and player_name == room.host and room.status in ("lobby", "round_result"):
                room.start_round()
                payload = {"type": "round_started", "state": room.public_state()}
                if room.mode == "puzzle":
                    for p in room.players:
                        payload_for_p = dict(payload)
                        payload_for_p["puzzle"] = {
                            k: v for k, v in room.puzzle.items() if k != "_answer_key"
                        }
                        ws = ws_manager.connections.get(game_id, {}).get(p)
                        if ws:
                            await ws.send_json(payload_for_p)
                else:
                    for p, state in room.players.items():
                        if not state.hat:
                            continue
                        card = scenario_store.scenario_payload_for_hat(room.scenario, state.hat)
                        ws = ws_manager.connections.get(game_id, {}).get(p)
                        if ws:
                            await ws.send_json({"type": "round_started", "state": room.public_state(), "your_view": card})

            elif action == "typing":
                await ws_manager.broadcast(game_id, {"type": "typing", "player": player_name})

            elif action == "submit_answer":
                room.submit_answer(player_name, msg.get("payload", {}))
                await ws_manager.broadcast(game_id, {
                    "type": "state",
                    "state": room.public_state(),
                    "debrief": room.debrief() if room.status == "round_result" else None,
                })

            elif action == "play_again" and player_name == room.host:
                room.start_round()
                await ws_manager.broadcast(game_id, {"type": "round_started", "state": room.public_state()})

            elif action == "leave":
                room.remove_player(player_name)
                await ws_manager.broadcast(game_id, {"type": "state", "state": room.public_state()})
                break

    except WebSocketDisconnect:
        room.remove_player(player_name)
        await ws_manager.broadcast(game_id, {"type": "state", "state": room.public_state()})
        manager.remove_if_ended(game_id)
    finally:
        ws_manager.disconnect(game_id, player_name)


# ---------------- static frontend ----------------

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
