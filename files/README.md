# 🎩 Six Hats Arena

A mobile-friendly team game based on Edward de Bono's **Six Thinking Hats**, built with
Streamlit. Employees log in, join or create a team, and play either a fast **Puzzle Mode**
(match a sentence to the right hat) or a deeper **Scenario Mode** (respond to a real
workplace scenario from your assigned hat's point of view — solo or as a team).

---

## What's included right now

- **Persistent accounts** — SQLite database (`data/game.db`) stores players, teams, XP,
  and round history, so scores survive app restarts and new logins with the same name.
- **Puzzle Mode** — colored hat buttons (not a dropdown), a per-question timer, speed
  bonus XP, and a results screen that reveals the correct hat for every sentence.
- **Scenario Mode**
  - *Individual*: instant start, no lobby, one random hat, one scenario, free-text answer.
  - *Team (2–6 players)*: host creates the game, teammates join a live lobby with colored
    face avatars, hats are assigned randomly once the host starts the round, everyone
    answers under a shared countdown, and a **debrief screen** groups every hat's answer
    side-by-side at the end — the actual point of the Six Hats method.
- **XP & levels** — Easy (0–500 XP) → Medium (500–1500) → Hard (1500–3000), with the exact
  XP math from the spec (team base XP per round, individual speed bonus, creativity
  penalty).
- **Leaderboard** — weekly, with individuals and teams shown as two separate sections on
  one dashboard.
- **Dark/light mode toggle** with a CSS layer that forces text color from a theme
  variable, so nothing ever renders white-on-white or black-on-black.
- **Hardcoded scenario dataset** (`data/scenarios.json`) — 30 puzzle sentences and 15 team
  scenarios across 3 difficulty levels, loosely themed around a staffing/HR consultancy
  (recruitment, attendance, employee relations) plus general office-life humor, so it's
  usable today without any AI model.

## What's intentionally a placeholder (for now)

- **Scenario answer scoring** (`src/evaluation.py::evaluate_scenario_answer`) uses simple
  keyword matching against each hat's theme, not a real model. This mirrors the "ML
  decides the evaluation" requirement from the spec — the function signature is designed
  so you can swap in your Six-Hats agent / ML model later without touching any UI code.
- **"Teammate is typing…" indicator** and true push-based real-time updates aren't
  possible in vanilla Streamlit (it's a request/response framework, not websockets). The
  app instead **polls every 1.5–2 seconds** via `streamlit-autorefresh`, which gets very
  close to real-time for a small team game. If you outgrow this, the natural next step is
  a small FastAPI + WebSocket backend with Streamlit (or a JS frontend) as the client.

## Project structure

```
six_hats_game/
├── app.py                 # main Streamlit app (all pages / state machine)
├── requirements.txt
├── data/
│   ├── scenarios.json      # hardcoded puzzle + scenario dataset
│   └── game.db              # created automatically on first run (SQLite)
└── src/
    ├── db.py                # persistence layer (players, teams, games, xp_log)
    ├── xp_engine.py          # XP/level tiers and scoring constants
    ├── evaluation.py         # answer evaluation (placeholder for the ML model)
    ├── theme.py              # dark/light CSS injection
    └── avatars.py             # SVG face-avatar generator for the lobby
```

## Run it locally

```bash
cd six_hats_game
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL Streamlit prints (usually `http://localhost:8501`).

## Publish it on a public link (Streamlit Community Cloud — free)

1. Push this folder to a **public GitHub repo** (Community Cloud needs to read it from
   GitHub). Make sure `data/scenarios.json` is committed; `data/game.db` can be excluded
   via `.gitignore` since it's generated at first run.
2. Go to **https://share.streamlit.io** and sign in with GitHub.
3. Click **"New app"** → pick the repo, branch, and set the main file path to `app.py`.
4. Click **Deploy**. Community Cloud installs `requirements.txt` automatically.
5. You'll get a public URL like `https://your-app-name.streamlit.app` — anyone with the
   link can open it, create their name, and play.

### A note on the database on Community Cloud

Community Cloud's filesystem is **ephemeral on redeploy** — if you push a new commit, the
app container restarts and `data/game.db` resets. For a one-off internal event this is
usually fine (everyone plays within the same live session). If you need scores to survive
across redeploys long-term, swap `DB_PATH` in `src/db.py` for a hosted database (e.g. a
free tier of Supabase/Postgres, or a Turso/LibSQL SQLite-compatible cloud DB) — the rest
of the code doesn't need to change since all DB access goes through `src/db.py`.

## Known simplifications worth knowing about

- Hat assignment for teams smaller than 6 lets the **host pick which hats are active**
  before starting, per the design decision in the spec; with exactly 6 players every hat
  is used automatically.
- If the host leaves or exits, host duties automatically transfer to the next active
  player already in the game — no one else can *become* host by choice, matching the spec.
- A round ends the moment every active player has either submitted or left, or the shared
  120-second timer runs out — whichever happens first.
- Puzzle mode uses a 12-second per-question timer (not specified in the original spec —
  chosen to keep "puzzle mode" feeling snappy; easy to change in `app.py`,
  `page_puzzle_play`, variable `time_limit`).
