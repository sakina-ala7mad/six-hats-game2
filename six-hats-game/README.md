# 🎩 Six Hats — Team Thinking Game

A mobile-friendly web game that teaches Edward de Bono's Six Thinking Hats
through two game modes (Puzzle + Scenario), solo or in teams of 2–6, with
XP, levels, a weekly leaderboard, and real-time lobbies.

## ⚠️ Important: why this is FastAPI + WebSockets, not Streamlit

The original ask was a Streamlit app. Streamlit is great for dashboards and
single-user tools, but this spec needs things Streamlit fundamentally can't
do well:
- **Instant, no-refresh updates to OTHER connected players** (a teammate's
  face turning into a smile the moment they submit — Streamlit reruns are
  per-session, they can't push to other users' browsers).
- **A persistent live game room** with a shared countdown, host migration,
  and "teammate is typing…" — this needs a real WebSocket connection.

So the stack is:
- **Backend: Python (FastAPI + WebSockets + SQLite)** — REST for
  auth/teams/dashboard, one WebSocket per active game for real-time state.
- **Frontend: HTML/CSS/vanilla JS** — no build step, one static bundle,
  works great on mobile, easy to reskin.
- **Dataset: JSON** — hardcoded scenarios, trivially swappable for the ML
  pipeline later (see `dataset/scenarios.json` and `backend/app/evaluator.py`).

This is still **one deployable service with one public URL** — the FastAPI
app serves the frontend's static files itself, so you don't need to host
frontend and backend separately.

## 📁 Project structure

```
six-hats-game/
├── README.md
├── dataset/
│   └── scenarios.json          # hardcoded scenarios (18: 6 easy/medium/hard)
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI app: REST + WebSocket + static hosting
│       ├── database.py         # SQLite persistence (players, teams, weekly XP log)
│       ├── game_logic.py       # pure rules: XP math, leveling, hat assignment
│       ├── rooms.py            # in-memory live GameRoom (lobby -> round -> result)
│       ├── ws_manager.py       # WebSocket connection registry + broadcast
│       ├── scenario_store.py   # loads dataset/scenarios.json, builds payloads
│       └── evaluator.py        # PLACEHOLDER scenario-answer scoring (swap for ML)
└── frontend/
    ├── index.html              # all screens (auth, home, lobby/game, dashboard)
    ├── css/style.css           # dark/light theme variables, hat colors, mobile UI
    └── js/app.js                # screen logic, REST calls, WebSocket client
```

## 🧠 How the game rules map to code

| Rule from the design doc | Where it lives |
|---|---|
| Easy 0–500xp / Medium 500–1500 / Hard 1500–3000 | `game_logic.LEVELS`, `level_for_xp()` |
| Scenario baseline 100/150/200 xp → whole team | `game_logic.scenario_round_team_xp()` |
| Puzzle 10/20/30 xp per Q, +2xp/sec speed bonus | `game_logic.puzzle_question_xp()` |
| -5xp creativity penalty | `game_logic.CREATIVITY_PENALTY` |
| Random hat assignment, no repeats, host can't assign | `game_logic.assign_hats()` |
| 2–5 players → host pre-selects active hats | `assign_hats(host_selected_hats=...)` |
| Round never pauses; ends when active players submit/leave | `game_logic.should_end_round()`, `rooms.GameRoom.submit_answer()` |
| Host leaves → hosting passes to next player | `game_logic.reassign_host()`, `rooms.GameRoom.remove_player()` |
| Shared 2-minute round timer (not per-player) | `rooms.GameRoom.round_seconds` / `seconds_left()` |
| Case-insensitive name matching, same account | SQLite `COLLATE NOCASE` in `database.py` |
| Duplicate name/team-name message | `409` responses in `main.py` |
| Team capacity 1–6, "team is full" popup | `database.join_team()` → `409 TEAM_FULL` |
| Weekly leaderboard, individuals & teams separate | `database.weekly_individual_leaderboard()` / `weekly_team_leaderboard()`, rendered as two lists in `app.js` |
| Debrief screen (all 6 hat answers side by side) | `rooms.GameRoom.debrief()` |
| "Your role" card on hat assignment | `scenario_store.scenario_payload_for_hat()` → `role-card` in UI |
| 280-char answer limit + typing indicator | `scenario_payload_for_hat()["char_limit"]`, `action: "typing"` in `main.py`/`app.js` |
| "Play again" button, same team | `action: "play_again"` WebSocket handler |
| Puzzle mode shows correct answer after round | `rooms.finish_round()` puzzle branch → `per_question` in result |
| Colored hat icons instead of a dropdown | `.hat-chip` picker in `app.js`/`style.css` |
| Dark/light mode, no invisible text | CSS variables in `style.css` — every color is theme-driven |

## ▶️ Run it locally

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** — the backend serves the frontend directly.

## 🌍 Deploy it publicly (free options)

Any host that runs a long-lived Python process + WebSockets works. Two easy
free-tier options:

### Option A — Render.com
1. Push this folder to a GitHub repo.
2. On Render: **New → Web Service**, connect the repo.
3. Root directory: `backend`
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Deploy. Render gives you a public `https://your-app.onrender.com` URL —
   share that link with your team.

### Option B — Fly.io
1. `fly launch` from the `backend/` folder (it auto-detects the FastAPI app).
2. `fly deploy`.
3. Fly gives you a public URL with WebSocket support out of the box.

> Both free tiers "sleep" after inactivity, which just means the first
> request after idle takes a few extra seconds to wake up — fine for a
> training session.

### Data persistence
Player/team XP lives in `backend/data/sixhats.db` (SQLite). On Render/Fly's
free tier, disk is ephemeral on redeploy — for a permanent public link that
never loses scores across deploys, mount a persistent volume (`fly volumes
create` / Render's Disks) pointed at `backend/data/`.

## 🧩 Growing the scenario dataset

Everything lives in `dataset/scenarios.json`, one object per scenario:
```json
{
  "id": "e07", "level": "easy", "category": "office-life",
  "title": "...", "scenario_text": "...",
  "puzzle_sentences": [ { "hat": "white", "sentence": "..." }, ... all 6 hats ... ],
  "hat_guides": { "white": { "keywords": [...], "sample_answer": "..." }, ... }
}
```
Add as many as you like — `scenario_store.py` picks a random one per round
per level automatically, no other code changes needed. When your ADK
six-hats agent / ML model is ready, either (a) have it write into this same
JSON schema, or (b) replace `scenario_store.random_scenario()` with a live
call to your agent, and replace `evaluator.evaluate_answer()` with a real
model-scored evaluation — both are single-file swaps.

## 🔐 Notes on what's stubbed vs. real

- **Real**: auth, teams, hat assignment, XP/leveling math, WebSocket
  real-time lobby + round flow, host migration, weekly leaderboard, dark/
  light theming, puzzle correct-answer reveal, scenario debrief screen.
- **Placeholder (by design, per your note)**: `evaluator.py` scores
  scenario answers via keyword overlap, not a real ML model — swap it when
  your model is ready.
- **Not yet wired**: a password-reset flow, admin tooling to edit the
  dataset from the UI, and profile pictures for the face avatars (currently
  hat-colored emoji faces per the "cute faces" spec).
