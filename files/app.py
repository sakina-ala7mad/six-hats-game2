import json
import random
import time
import datetime as dt
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from src import db, xp_engine, evaluation, avatars
from src.theme import inject_theme, card

# ---------------------------------------------------------------- setup ----
st.set_page_config(page_title="Six Hats Arena", page_icon="🎩", layout="centered")
db.init_db()

DATA_PATH = Path(__file__).resolve().parent / "data" / "scenarios.json"
DATA = json.loads(DATA_PATH.read_text())
HATS = DATA["hats"]
HAT_ORDER = ["white", "red", "black", "yellow", "green", "blue"]


def ss_default(key, value):
    if key not in st.session_state:
        st.session_state[key] = value


ss_default("dark_mode", False)
ss_default("player", None)
ss_default("seen_intro", False)
ss_default("show_intro_modal", False)
ss_default("page", "login")
ss_default("current_team_id", None)
ss_default("current_game_id", None)
ss_default("puzzle_run", None)
ss_default("scenario_role_ack", False)

theme_mode = "dark" if st.session_state.dark_mode else "light"
inject_theme(theme_mode)

# ---------------------------------------------------------- top chrome ----
top_l, top_r = st.columns([4, 1])
with top_r:
    st.session_state.dark_mode = st.toggle("🌙", value=st.session_state.dark_mode, help="Dark mode")


def hat_button_row(on_click_prefix, disabled=False):
    """Renders 6 colored hat buttons (replaces a dropdown) and returns the chosen hat, if any."""
    chosen = None
    cols = st.columns(6)
    for i, hat in enumerate(HAT_ORDER):
        h = HATS[hat]
        with cols[i]:
            label = f"{h['name'].split()[0]}"
            if st.button(label, key=f"{on_click_prefix}_{hat}", disabled=disabled, use_container_width=True):
                chosen = hat
    return chosen


def intro_modal():
    card(f"""
    <div class="sh-title">🎩 Welcome to Six Hats Arena</div>
    <div class="sh-subtitle">A quick primer before you play</div>
    <p>The <b>Six Thinking Hats</b> is a method for structured, parallel thinking. Each hat is a
    different lens for looking at the same problem:</p>
    <ul>
      <li><b>White Hat</b> — Facts & information, no opinions.</li>
      <li><b>Red Hat</b> — Feelings, gut reactions, no justification needed.</li>
      <li><b>Black Hat</b> — Caution, risks, what could go wrong.</li>
      <li><b>Yellow Hat</b> — Optimism, benefits, what could go right.</li>
      <li><b>Green Hat</b> — Creativity, new ideas, alternatives.</li>
      <li><b>Blue Hat</b> — Process, managing the thinking itself.</li>
    </ul>
    <p class="sh-muted">Why it helps: instead of arguing from mixed angles at once, everyone
    looks through <i>one</i> lens at a time — which reduces bias and speeds up good decisions.</p>
    """)
    if st.button("Got it, let's play →", key="skip_intro"):
        st.session_state.seen_intro = True
        st.session_state.show_intro_modal = False
        st.rerun()


# ============================================================== LOGIN =====
def page_login():
    card("""<div class="sh-title">🎩 Six Hats Arena</div>
    <div class="sh-subtitle">Log in with your name to start playing. Same name + password logs you back into your saved score.</div>""")
    with st.form("login_form"):
        name = st.text_input("Your name")
        pw = st.text_input("Password (used to protect your name)", type="password")
        submitted = st.form_submit_button("Play ▶")
    if submitted:
        if not name.strip():
            st.error("Please enter a name.")
        else:
            player, msg, is_new = db.login_or_create_player(name, pw)
            if player is None:
                st.error(msg)
            else:
                st.session_state.player = player["display_name"]
                st.session_state.page = "mode_select"
                if not st.session_state.seen_intro:
                    st.session_state.show_intro_modal = True
                st.rerun()


# ========================================================= MODE SELECT ====
def page_mode_select():
    player = db.get_player(st.session_state.player)
    tier, into, span, frac = xp_engine.get_level_info(player["total_xp"])
    team = db.get_player_current_team(st.session_state.player)

    card(f"""
    <div class="sh-title">Hi, {player['display_name']} 👋</div>
    <span class="sh-badge">{tier} tier</span>
    <div class="sh-muted" style="margin-top:8px;">{into} / {span} XP to next tier · Total XP: {player['total_xp']}</div>
    """)
    st.progress(frac)

    top1, top2 = st.columns(2)
    with top1:
        if st.button("❓ How to play (Six Hats primer)", use_container_width=True):
            st.session_state.show_intro_modal = True
    with top2:
        if st.button("🏆 Leaderboard", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()

    if st.session_state.show_intro_modal:
        intro_modal()
        return

    st.markdown("### Choose how you want to play")
    c1, c2 = st.columns(2)
    with c1:
        card(f"""<div class="sh-title">🧩 Puzzle Mode</div>
        <div class="sh-subtitle">Fast rounds — match the sentence to the right hat, beat the clock.</div>""")
        indiv = st.button("Play Puzzle · Individual", use_container_width=True, key="puzzle_indiv_btn")
        team_puzzle = st.button(
            f"Play Puzzle · Team ({team['display_name'] if team else 'join a team first'})",
            use_container_width=True, key="puzzle_team_btn", disabled=team is None,
        )
        if indiv:
            st.session_state.puzzle_team_mode = False
            st.session_state.page = "puzzle_level"
            st.rerun()
        if team_puzzle:
            st.session_state.puzzle_team_mode = True
            st.session_state.page = "puzzle_level"
            st.rerun()

    with c2:
        card(f"""<div class="sh-title">🎭 Scenario Mode</div>
        <div class="sh-subtitle">One real scenario, your hat decides your angle. Deeper, and better with a team.</div>""")
        indiv_s = st.button("Play Scenario · Individual", use_container_width=True, key="scenario_indiv_btn")
        team_s = st.button(
            f"Play Scenario · Team ({team['display_name'] if team else 'join a team first'})",
            use_container_width=True, key="scenario_team_btn", disabled=team is None,
        )
        if indiv_s:
            st.session_state.page = "scenario_indiv_level"
            st.rerun()
        if team_s:
            st.session_state.page = "team_game_setup"
            st.rerun()

    st.markdown("### Team")
    if team:
        members = db.get_team_members(team["team_id"])
        member_names = ", ".join(m["display_name"] for m in members)
        card(f"""<div class="sh-title">Your team: {team['display_name']}</div>
        <div class="sh-muted">Team XP: {team['team_xp']} · Members ({len(members)}/6): {member_names}</div>""")
        if st.button("Leave team"):
            db.leave_team(team["team_id"], st.session_state.player)
            st.rerun()
    else:
        st.session_state.page_team_browser = True
        page_team_browser()


def page_team_browser():
    teams = db.list_teams()
    tabs = st.tabs(["Join a team", "Create a team"])
    with tabs[0]:
        if not teams:
            st.info("No teams yet — create the first one!")
        for t in teams:
            full = t["member_count"] >= 6
            c1, c2 = st.columns([3, 1])
            with c1:
                card(f"""<b>{t['display_name']}</b>
                <div class="sh-muted">{t['member_count']}/6 members · Team XP: {t['team_xp']}</div>""")
            with c2:
                if st.button("Join" if not full else "Full", key=f"join_{t['team_id']}", disabled=full):
                    ok, msg = db.join_team(t["team_id"], st.session_state.player)
                    if not ok:
                        st.error(msg)
                    else:
                        st.rerun()
    with tabs[1]:
        with st.form("create_team_form"):
            tname = st.text_input("Team name")
            create = st.form_submit_button("Create team")
        if create:
            if not tname.strip():
                st.error("Please enter a team name.")
            else:
                ok, msg, team_id = db.create_team(tname, st.session_state.player)
                if not ok:
                    st.error(msg)
                else:
                    st.success(f"Team created! Share this ID so teammates can join: {team_id}")
                    st.rerun()


# ============================================================ PUZZLE ======
def page_puzzle_level():
    card('<div class="sh-title">Choose difficulty</div>')
    level = st.radio("Level", ["easy", "medium", "hard"], horizontal=True, label_visibility="collapsed")
    with st.expander("📖 Tutorial: how Puzzle Mode works", expanded=True):
        st.write(
            "You'll see a short sentence describing a situation. Tap the colored hat "
            "that best matches the thinking style behind it. Answer fast for a speed "
            "bonus — a countdown runs on every question. Wrong or slow guesses lose a "
            "little XP. After the round you'll see the correct hat for every sentence."
        )
    if st.button("Start Puzzle Round ▶"):
        pool = list(DATA["puzzle_mode"][level])
        random.shuffle(pool)
        questions = pool[:8] if len(pool) >= 8 else pool
        st.session_state.puzzle_run = {
            "level": level,
            "questions": questions,
            "index": 0,
            "xp_total": 0,
            "results": [],  # list of dicts: sentence, correct_hat, chosen_hat, correct, bonus
            "q_start": time.time(),
        }
        st.session_state.page = "puzzle_play"
        st.rerun()
    if st.button("← Back"):
        st.session_state.page = "mode_select"
        st.rerun()


def page_puzzle_play():
    run = st.session_state.puzzle_run
    qs = run["questions"]
    idx = run["index"]

    if idx >= len(qs):
        st.session_state.page = "puzzle_results"
        st.rerun()
        return

    q = qs[idx]
    elapsed = time.time() - run["q_start"]
    time_limit = 12
    remaining = max(0, time_limit - elapsed)

    card(f"""<span class="sh-badge">{run['level'].upper()} · Q{idx+1}/{len(qs)}</span>
    <div class="sh-title" style="margin-top:10px;">"{q['sentence']}"</div>
    <div class="sh-subtitle">Which hat is thinking this?</div>""")
    st.markdown(f"<div class='sh-timer'>⏱ {int(remaining)}s</div>", unsafe_allow_html=True)

    chosen = hat_button_row(f"puzzle_q{idx}", disabled=remaining <= 0)

    if remaining <= 0 and chosen is None:
        chosen = "__timeout__"

    if chosen is not None:
        level = run["level"]
        base_xp = xp_engine.puzzle_question_xp(level)
        if chosen == "__timeout__":
            correct = False
            xp_gain = -xp_engine.CREATIVITY_PENALTY
        else:
            correct = evaluation.evaluate_puzzle_answer(chosen, q["correct_hat"])
            bonus = xp_engine.speed_bonus(remaining) if correct else 0
            xp_gain = (base_xp + bonus) if correct else -xp_engine.CREATIVITY_PENALTY
        run["xp_total"] += xp_gain
        run["results"].append({
            "sentence": q["sentence"],
            "correct_hat": q["correct_hat"],
            "chosen_hat": None if chosen == "__timeout__" else chosen,
            "correct": correct,
            "xp": xp_gain,
        })
        run["index"] += 1
        run["q_start"] = time.time()
        st.rerun()
    else:
        st_autorefresh(interval=500, key=f"puzzle_timer_{idx}")


def page_puzzle_results():
    run = st.session_state.puzzle_run
    team_mode = st.session_state.get("puzzle_team_mode", False)
    team = db.get_player_current_team(st.session_state.player) if team_mode else None

    correct_n = sum(1 for r in run["results"] if r["correct"])
    card(f"""<div class="sh-title">Round complete! 🎉</div>
    <div class="sh-subtitle">{correct_n}/{len(run['results'])} correct · {run['xp_total']:+d} XP</div>""")

    for r in run["results"]:
        ch = HATS[r["correct_hat"]]
        mark = "✅" if r["correct"] else "❌"
        chosen_label = HATS[r["chosen_hat"]]["name"] if r["chosen_hat"] else "No answer (timed out)"
        card(f"""{mark} <b>"{r['sentence']}"</b><br/>
        <span class="sh-muted">Your answer: {chosen_label} · Correct answer: {ch['name']} · {r['xp']:+d} XP</span>""")

    mode_tag = "team_puzzle" if team_mode else "individual_puzzle"
    if not st.session_state.get("puzzle_xp_applied"):
        db.add_player_xp(st.session_state.player, run["xp_total"], team["team_id"] if team else None, mode_tag)
        if team_mode and team:
            db.add_team_xp(team["team_id"], run["xp_total"])
        st.session_state.puzzle_xp_applied = True

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Play again"):
            st.session_state.puzzle_xp_applied = False
            st.session_state.page = "puzzle_level"
            st.rerun()
    with c2:
        if st.button("Back to menu"):
            st.session_state.puzzle_xp_applied = False
            st.session_state.page = "mode_select"
            st.rerun()


# ==================================================== SCENARIO: INDIVIDUAL
def page_scenario_indiv_level():
    card('<div class="sh-title">Choose difficulty</div>')
    level = st.radio("Level", ["easy", "medium", "hard"], horizontal=True, label_visibility="collapsed")
    with st.expander("📖 Tutorial: how Scenario Mode works", expanded=True):
        st.write(
            "You'll get one real-world scenario and be randomly assigned a hat. "
            f"Write your response from that hat's point of view (max {xp_engine.ANSWER_CHAR_LIMIT} "
            "characters) before the timer runs out. You'll see feedback on how well your answer "
            "matched that hat's thinking style."
        )
    if st.button("Start ▶"):
        scenario = random.choice(DATA["scenario_mode"][level])
        hat = random.choice(HAT_ORDER)
        st.session_state.indiv_scenario_run = {
            "level": level, "scenario": scenario, "hat": hat,
            "start": time.time(), "answered": False,
        }
        st.session_state.page = "scenario_indiv_play"
        st.rerun()
    if st.button("← Back"):
        st.session_state.page = "mode_select"
        st.rerun()


def page_scenario_indiv_play():
    run = st.session_state.indiv_scenario_run
    scenario = run["scenario"]
    hat = run["hat"]
    h = HATS[hat]
    remaining = max(0, xp_engine.ROUND_SECONDS - (time.time() - run["start"]))

    card(f"""<div class="sh-title">{scenario['title']}</div>
    <div class="sh-subtitle">{scenario['scenario_text']}</div>""")

    card(f"""<span class="sh-badge" style="background:{h['color_hex']};color:{h['text_on_hat']} !important;">
    Your role: {h['name']}</span>
    <div class="sh-muted" style="margin-top:8px;">{h['description']}</div>
    <div class="sh-muted"><i>Example: {h['example']}</i></div>""")

    st.markdown(f"<div class='sh-timer'>⏱ {int(remaining)}s</div>", unsafe_allow_html=True)

    answer = st.text_area(
        f"Your {h['name']} response", max_chars=xp_engine.ANSWER_CHAR_LIMIT,
        key="indiv_answer_box", disabled=run["answered"],
    )
    submit = st.button("Submit answer", disabled=run["answered"] or remaining <= 0)

    if (submit or remaining <= 0) and not run["answered"]:
        run["answered"] = True
        prompt = scenario["hat_prompts"][hat]
        is_correct, creativity, correction = evaluation.evaluate_scenario_answer(answer, hat, prompt)
        base_xp = xp_engine.scenario_team_base_xp(run["level"])
        bonus = xp_engine.speed_bonus(remaining) if is_correct else 0
        penalty = 0 if is_correct else -xp_engine.CREATIVITY_PENALTY
        total_xp = base_xp + bonus + penalty
        db.add_player_xp(st.session_state.player, total_xp, None, "individual_scenario")
        run["result"] = {
            "answer": answer, "is_correct": is_correct, "creativity": creativity,
            "correction": correction, "xp": total_xp,
        }
        st.rerun()

    if run["answered"]:
        res = run["result"]
        mark = "✅" if res["is_correct"] else "⚠️"
        card(f"""{mark} <b>Your answer:</b> {res['answer'] or '(no answer submitted)'}
        <div class="sh-muted" style="margin-top:6px;">Creativity score: {res['creativity']}/100</div>
        <div class="sh-muted">{res['correction']}</div>
        <div class="sh-muted">XP earned: {res['xp']:+d}</div>""")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Play again"):
                st.session_state.page = "scenario_indiv_level"
                st.rerun()
        with c2:
            if st.button("Back to menu"):
                st.session_state.page = "mode_select"
                st.rerun()
    elif remaining > 0:
        st_autorefresh(interval=1000, key="indiv_scenario_timer")


# ========================================================== SCENARIO: TEAM
def page_team_game_setup():
    team = db.get_player_current_team(st.session_state.player)
    members = db.get_team_members(team["team_id"])
    card(f"""<div class="sh-title">Start a team round · {team['display_name']}</div>
    <div class="sh-muted">You'll be the host. Teammates join automatically once you create the game — no one else can host this game.</div>""")

    level = st.radio("Difficulty", ["easy", "medium", "hard"], horizontal=True)

    active_hats = HAT_ORDER
    if len(members) < 6:
        st.write("Your team has fewer than 6 players — pick which hats are in play:")
        active_hats = st.multiselect(
            "Active hats", HAT_ORDER, default=HAT_ORDER[: max(2, len(members))],
            format_func=lambda h: HATS[h]["name"],
        )

    with st.expander("📖 Tutorial: how team Scenario Mode works", expanded=True):
        st.write(
            "Everyone on the team sees the same scenario, but each player gets a different, "
            "randomly assigned hat. Work together, but each person submits their own answer — "
            "the round doesn't end until every active player has submitted or left. The fastest "
            "correct submitter gets an individual speed bonus; the base XP goes to the whole team."
        )

    if st.button("Create game & open lobby ▶", disabled=len(active_hats) == 0):
        scenario = random.choice(DATA["scenario_mode"][level])
        game_id = db.create_game(team["team_id"], st.session_state.player, level, scenario["id"],
                                  round_seconds=xp_engine.ROUND_SECONDS)
        st.session_state["scenario_" + game_id] = scenario
        st.session_state["active_hats_" + game_id] = active_hats
        db.join_game(game_id, st.session_state.player)
        st.session_state.current_game_id = game_id
        st.session_state.page = "team_lobby"
        st.rerun()

    if st.button("← Back"):
        st.session_state.page = "mode_select"
        st.rerun()


def _resolve_dropout_host(game):
    players = db.get_game_players(game["game_id"])
    active_players = [p for p in players if p["active"]]
    if not active_players:
        db.set_game_status(game["game_id"], "ended")
        return None
    host_still_active = any(p["player_key"] == game["host_key"] and p["active"] for p in players)
    if not host_still_active:
        new_host = active_players[0]
        db.set_game_host(game["game_id"], new_host["player_key"])
        game["host_key"] = new_host["player_key"]
    return game


def _lobby_or_active_faces(game_id, members, players_by_key, active_hats):
    """Renders the 6 face avatars, gray for empty/inactive slots, colored once game starts,
    smiling once submitted. Hats are hidden until the round actually starts."""
    game = db.get_game(game_id)
    started = game["status"] in ("active", "debrief", "ended")
    cols = st.columns(6)
    for i, hat in enumerate(HAT_ORDER):
        with cols[i]:
            if hat not in active_hats:
                st.markdown(avatars.face_block_html("", HATS[hat]["color_hex"], "off"), unsafe_allow_html=True)
                continue
            occupant = None
            for p in players_by_key.values():
                if p.get("hat") == hat:
                    occupant = p
            if occupant is None:
                st.markdown(avatars.face_block_html("", HATS[hat]["color_hex"], "off"), unsafe_allow_html=True)
            else:
                if not occupant["active"]:
                    state = "off"
                elif occupant["submitted"]:
                    state = "submitted"
                elif started:
                    state = "revealed"
                else:
                    state = "waiting"
                st.markdown(
                    avatars.face_block_html(occupant["display_name"], HATS[hat]["color_hex"], state),
                    unsafe_allow_html=True,
                )


def page_team_lobby_or_active():
    game_id = st.session_state.current_game_id
    game = db.get_game(game_id)
    if game is None:
        st.session_state.page = "mode_select"
        st.rerun()
        return

    my_key = st.session_state.player.strip().lower()
    if not any(p["player_key"] == my_key for p in db.get_game_players(game_id)):
        db.join_game(game_id, st.session_state.player)

    game = _resolve_dropout_host(game)
    if game is None:
        st.info("Everyone left — this game has ended.")
        if st.button("Back to menu"):
            st.session_state.page = "mode_select"
            st.rerun()
        return

    scenario = st.session_state.get("scenario_" + game_id) or next(
        s for s in DATA["scenario_mode"][game["level"]] if s["id"] == game["scenario_id"]
    )
    active_hats = st.session_state.get("active_hats_" + game_id, HAT_ORDER)

    is_host = game["host_key"] == my_key
    players = db.get_game_players(game_id)
    players_by_key = {p["player_key"]: p for p in players}

    st_autorefresh(interval=1500, key=f"lobby_refresh_{game_id}")

    card(f"""<span class="sh-badge">{game['level'].upper()} · {'HOST: ' + game['host_key'] if is_host else 'Waiting for host'}</span>
    <div class="sh-title" style="margin-top:8px;">{scenario['title']}</div>
    <div class="sh-subtitle">{scenario['scenario_text']}</div>""")

    if game["status"] == "active" and game["round_start_at"]:
        started_at = dt.datetime.fromisoformat(game["round_start_at"])
        elapsed = (dt.datetime.utcnow() - started_at).total_seconds()
        remaining = max(0, game["round_seconds"] - elapsed)
        st.markdown(f"<div class='sh-timer'>⏱ {int(remaining)}s</div>", unsafe_allow_html=True)
    else:
        remaining = None
        st.write("Waiting for the host to start the round…" if not is_host else "Ready when you are.")

    _lobby_or_active_faces(game_id, db.get_team_members(game["team_id"]), players_by_key, active_hats)

    submitted_n = sum(1 for p in players if p["submitted"])
    active_n = sum(1 for p in players if p["active"])
    st.caption(f"{submitted_n} of {active_n} submitted")

    my_player_row = players_by_key.get(my_key)

    if game["status"] == "lobby":
        if is_host:
            enough = sum(1 for h in active_hats) >= 1
            if st.button("▶ Start round now", disabled=not enough):
                unassigned_players = [p for p in players if p["active"] and not p["hat"]]
                available_hats = list(active_hats)
                random.shuffle(available_hats)
                for p, h in zip(unassigned_players, available_hats):
                    db.set_player_hat(game_id, p["player_key"], h)
                db.start_round(game_id, xp_engine.ROUND_SECONDS)
                st.rerun()
        if st.button("Leave lobby"):
            db.set_player_active(game_id, my_key, False)
            st.session_state.current_game_id = None
            st.session_state.page = "mode_select"
            st.rerun()

    elif game["status"] == "active":
        if my_player_row and my_player_row["hat"]:
            hat = my_player_row["hat"]
            h = HATS[hat]
            if not my_player_row["submitted"]:
                card(f"""<span class="sh-badge" style="background:{h['color_hex']};color:{h['text_on_hat']} !important;">
                Your role: {h['name']}</span>
                <div class="sh-muted" style="margin-top:6px;">{h['description']}</div>
                <div class="sh-muted"><i>Example: {h['example']}</i></div>""")
                answer = st.text_area(
                    f"Your {h['name']} response ({xp_engine.ANSWER_CHAR_LIMIT} char max)",
                    max_chars=xp_engine.ANSWER_CHAR_LIMIT, key=f"team_answer_{game_id}",
                )
                if st.button("Submit answer", disabled=(remaining is not None and remaining <= 0)):
                    prompt = scenario["hat_prompts"][hat]
                    is_correct, creativity, correction = evaluation.evaluate_scenario_answer(answer, hat, prompt)
                    bonus = xp_engine.speed_bonus(remaining or 0) if is_correct else 0
                    db.submit_answer(game_id, st.session_state.player, hat, answer, is_correct,
                                      correction, bonus, creativity)
                    st.rerun()
            else:
                st.success("Answer submitted — waiting for the rest of the team…")
        if st.button("Leave game", key="leave_active"):
            db.set_player_active(game_id, my_key, False)
            st.session_state.current_game_id = None
            st.session_state.page = "mode_select"
            st.rerun()

        players = db.get_game_players(game_id)
        active_unsubmitted = [p for p in players if p["active"] and not p["submitted"]]
        time_up = remaining is not None and remaining <= 0
        if not active_unsubmitted or time_up:
            db.set_game_status(game_id, "debrief")
            team_id = game["team_id"]
            base_xp = xp_engine.scenario_team_base_xp(game["level"])
            db.add_team_xp(team_id, base_xp)
            for p in players:
                if not p["active"]:
                    continue
                db.add_player_xp(p["display_name"], base_xp, team_id, "team_scenario")
            for sub in db.get_submissions(game_id):
                if sub["speed_bonus"]:
                    db.add_player_xp(sub["display_name"], sub["speed_bonus"], team_id, "team_scenario")
            st.rerun()

    elif game["status"] in ("debrief", "ended"):
        st.session_state.page = "team_debrief"
        st.rerun()


def page_team_debrief():
    game_id = st.session_state.current_game_id
    game = db.get_game(game_id)
    scenario = st.session_state.get("scenario_" + game_id) or next(
        s for s in DATA["scenario_mode"][game["level"]] if s["id"] == game["scenario_id"]
    )
    subs = {s["hat"]: s for s in db.get_submissions(game_id)}

    card(f"""<div class="sh-title">🧵 Debrief — {scenario['title']}</div>
    <div class="sh-subtitle">{scenario['scenario_text']}</div>""")

    for hat in HAT_ORDER:
        h = HATS[hat]
        sub = subs.get(hat)
        if not sub:
            continue
        mark = "✅" if sub["is_correct"] else "⚠️"
        card(f"""<span class="sh-badge" style="background:{h['color_hex']};color:{h['text_on_hat']} !important;">
        {h['name']} — {sub['display_name']}</span>
        <div style="margin-top:6px;">{mark} {sub['answer'] or '(no answer)'}</div>
        <div class="sh-muted">{sub['correction']} · creativity {sub['creativity_score']}/100</div>""")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔁 Play again, same team"):
            team = db.get_player_current_team(st.session_state.player)
            scenario2 = random.choice(DATA["scenario_mode"][game["level"]])
            new_game_id = db.create_game(team["team_id"], st.session_state.player, game["level"],
                                          scenario2["id"], round_seconds=xp_engine.ROUND_SECONDS)
            st.session_state["scenario_" + new_game_id] = scenario2
            st.session_state["active_hats_" + new_game_id] = st.session_state.get(
                "active_hats_" + game_id, HAT_ORDER
            )
            db.join_game(new_game_id, st.session_state.player)
            st.session_state.current_game_id = new_game_id
            st.session_state.page = "team_lobby"
            st.rerun()
    with c2:
        if st.button("Back to menu"):
            st.session_state.current_game_id = None
            st.session_state.page = "mode_select"
            st.rerun()


# ================================================================ DASHBOARD
def page_dashboard():
    card('<div class="sh-title">🏆 Weekly Leaderboard</div><div class="sh-subtitle">Resets every week</div>')
    st.markdown("#### 👤 Individuals")
    indiv = db.leaderboard_individual()
    if not indiv:
        st.caption("No individual games played yet this week.")
    for i, row in enumerate(indiv, start=1):
        card(f"**#{i} {row['display_name']}** — {row['weekly_xp']} XP this week "
             f"<span class='sh-muted'>(lifetime {row['total_xp']})</span>")

    st.markdown("#### 👥 Teams")
    teams = db.leaderboard_teams()
    if not teams:
        st.caption("No team games played yet this week.")
    for i, row in enumerate(teams, start=1):
        card(f"**#{i} {row['display_name']}** — {row['weekly_xp']} XP this week "
             f"<span class='sh-muted'>(lifetime {row['team_xp']})</span>")

    if st.button("← Back"):
        st.session_state.page = "mode_select"
        st.rerun()


# =================================================================== ROUTER
if st.session_state.player is None:
    page_login()
else:
    page = st.session_state.page
    if page == "mode_select":
        page_mode_select()
    elif page == "puzzle_level":
        page_puzzle_level()
    elif page == "puzzle_play":
        page_puzzle_play()
    elif page == "puzzle_results":
        page_puzzle_results()
    elif page == "scenario_indiv_level":
        page_scenario_indiv_level()
    elif page == "scenario_indiv_play":
        page_scenario_indiv_play()
    elif page == "team_game_setup":
        page_team_game_setup()
    elif page in ("team_lobby",):
        page_team_lobby_or_active()
    elif page == "team_debrief":
        page_team_debrief()
    elif page == "dashboard":
        page_dashboard()
    else:
        st.session_state.page = "mode_select"
        st.rerun()
