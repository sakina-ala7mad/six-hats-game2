"""
ws_manager.py
Tracks live WebSocket connections per game room and broadcasts state.
This is what gives "no refresh needed, instant updates" — a Streamlit app
re-running top-to-bottom on each interaction cannot push updates to OTHER
connected players the way a websocket broadcast can.
"""
from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self.connections: dict[str, dict[str, WebSocket]] = {}  # game_id -> {player_name: ws}

    async def connect(self, game_id: str, player_name: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(game_id, {})[player_name] = ws

    def disconnect(self, game_id: str, player_name: str):
        room_conns = self.connections.get(game_id, {})
        room_conns.pop(player_name, None)
        if not room_conns:
            self.connections.pop(game_id, None)

    async def broadcast(self, game_id: str, message: dict):
        for ws in list(self.connections.get(game_id, {}).values()):
            try:
                await ws.send_json(message)
            except Exception:
                pass


ws_manager = WSManager()
