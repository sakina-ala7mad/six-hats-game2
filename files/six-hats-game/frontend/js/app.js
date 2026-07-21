// ===== Six Hats Game — frontend app.js =====
// Vanilla JS, no build step. Talks to the FastAPI backend via REST + one
// persistent WebSocket per active game for zero-delay updates.

const API = ""; // same-origin: backend serves this frontend, so relative paths work
const HAT_COLORS = {
  white: "var(--hat-white)", red: "var(--hat-red)", black: "var(--hat-black)",
  yellow: "var(--hat-yellow)", green: "var(--hat-green)", blue: "var(--hat-blue)",
};
const HAT_TEXT = {
  white: "var(--hat-white-text)", red: "var(--hat-red-text)", black: "var(--hat-black-text)",
  yellow: "var(--hat-yellow-text)", green: "var(--hat-green-text)", blue: "var(--hat-blue-text)",
};
const HAT_EMOJI = { white: "🤍", red: "❤️", black: "🖤", yellow: "💛", green: "💚", blue: "💙" };

let state = {
  player: null,       // {name, xp, level}
  selectedTeam: null,  // {id, name}
  gameModeType: "individual", // individual | team
  gameMode: "puzzle",  // puzzle | scenario
  level: "easy",
  ws: null,
  gameId: null,
  puzzleMatches: {},   // sentence_id -> hat
  activeHatChip: null,
  roleCard: null,
};

// ---------- helpers ----------
function $(id) { return document.getElementById(id); }
function show(id) { $(id).classList.remove("hidden"); }
function hide(id) { $(id).classList.add("hidden"); }
function screen(name) {
  document.querySelectorAll(".screen").forEach(s => s.classList.add("hidden"));
  show("screen-" + name);
}
async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

// ---------- theme ----------
function applyTheme(theme) {
  document.body.setAttribute("data-theme", theme);
  $("themeToggle").textContent = theme === "dark" ? "🌙" : "☀️";
  localStorage.setItem("sixhats_theme", theme);
}
$("themeToggle").onclick = () => {
  const current = document.body.getAttribute("data-theme");
  applyTheme(current === "dark" ? "light" : "dark");
};
applyTheme(localStorage.getItem("sixhats_theme") || "dark");

// ---------- six hats intro ----------
async function maybeShowIntro() {
  const hats = await api("/api/hats-intro");
  const list = $("introHatsList");
  list.innerHTML = "";
  for (const [key, h] of Object.entries(hats)) {
    const row = document.createElement("div");
    row.className = "intro-hat-row";
    row.innerHTML = `<div class="hat-dot" style="background:${HAT_COLORS[key]}"></div>
      <div><strong>${h.name}</strong><br><span class="muted small">${h.meaning} — ${h.prompt}</span></div>`;
    list.appendChild(row);
  }
  show("helpBtn");
  const seenKey = "sixhats_intro_seen_" + state.player.name;
  if (!localStorage.getItem(seenKey)) {
    show("introModal");
    localStorage.setItem(seenKey, "1");
  }
}
$("introSkipBtn").onclick = () => hide("introModal");
$("helpBtn").onclick = () => show("introModal");

// ---------- auth ----------
$("loginBtn").onclick = async () => {
  const name = $("authName").value.trim();
  const password = $("authPassword").value;
  $("authError").textContent = "";
  if (!name || !password) { $("authError").textContent = "Enter a name and password."; return; }
  try {
    let player;
    try {
      player = await api("/api/players/login", { method: "POST", body: JSON.stringify({ name, password }) });
    } catch (e) {
      // no such account yet -> register it
      player = await api("/api/players/register", { method: "POST", body: JSON.stringify({ name, password }) });
    }
    state.player = player;
    await enterHome();
  } catch (e) {
    $("authError").textContent = e.message;
  }
};

async function enterHome() {
  $("homePlayerName").textContent = state.player.name;
  $("homeLevelBadge").textContent = `${state.player.level.toUpperCase()} · ${state.player.xp} XP`;
  screen("home");
  await maybeShowIntro();
  await refreshTeamList();
}

// ---------- home: mode toggles ----------
$("modeIndividualBtn").onclick = () => setModeType("individual");
$("modeTeamBtn").onclick = () => setModeType("team");
function setModeType(t) {
  state.gameModeType = t;
  $("modeIndividualBtn").classList.toggle("active", t === "individual");
  $("modeTeamBtn").classList.toggle("active", t === "team");
  $("teamSection").classList.toggle("hidden", t !== "team");
}

$("puzzleModeBtn").onclick = () => setGameMode("puzzle");
$("scenarioModeBtn").onclick = () => setGameMode("scenario");
function setGameMode(m) {
  state.gameMode = m;
  $("puzzleModeBtn").classList.toggle("active", m === "puzzle");
  $("scenarioModeBtn").classList.toggle("active", m === "scenario");
}

document.querySelectorAll("[data-level]").forEach(btn => {
  btn.onclick = () => {
    document.querySelectorAll("[data-level]").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.level = btn.dataset.level;
  };
});

// ---------- teams ----------
async function refreshTeamList() {
  const teams = await api("/api/teams");
  const list = $("teamList");
  list.innerHTML = "";
  teams.forEach(t => {
    const row = document.createElement("div");
    row.className = "team-item" + (state.selectedTeam?.id === t.id ? " selected" : "");
    row.innerHTML = `<span>${t.name}</span><span class="muted small">${t.member_count}/6</span>`;
    row.onclick = () => selectTeam(t);
    list.appendChild(row);
  });
}
function selectTeam(t) {
  state.selectedTeam = t;
  refreshTeamList();
}
$("createTeamBtn").onclick = async () => {
  const name = $("newTeamName").value.trim();
  if (!name) return;
  try {
    const team = await api("/api/teams/create", {
      method: "POST",
      body: JSON.stringify({ player_name: state.player.name, team_name: name }),
    });
    state.selectedTeam = team;
    $("newTeamName").value = "";
    await refreshTeamList();
  } catch (e) {
    alert(e.message);
  }
};

// ---------- start / join game ----------
$("startGameBtn").onclick = async () => {
  if (state.gameModeType === "team") {
    if (!state.selectedTeam) { alert("Pick or create a team first."); return; }
    try {
      await api("/api/teams/join", {
        method: "POST",
        body: JSON.stringify({ player_name: state.player.name, team_id: state.selectedTeam.id }),
      });
    } catch (e) { /* already a member / full — ignore already-member case */ }

    const existing = await api(`/api/teams/${state.selectedTeam.id}/active-game`);
    if (existing.game_id) {
      openGame(existing.game_id);
      return;
    }
  }

  const body = {
    host_name: state.player.name,
    mode: state.gameMode,
    is_team: state.gameModeType === "team",
    level: state.level,
    team_id: state.gameModeType === "team" ? state.selectedTeam.id : null,
  };
  const res = await api("/api/games/create", { method: "POST", body: JSON.stringify(body) });
  openGame(res.game_id);
};

function openGame(gameId) {
  state.gameId = gameId;
  screen("game");
  $("gameIdLabel").textContent = "Game: " + gameId;
  connectWS(gameId);
}

// ---------- websocket ----------
function connectWS(gameId) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}/ws/game/${gameId}/${encodeURIComponent(state.player.name)}`;
  state.ws = new WebSocket(url);
  state.ws.onmessage = (evt) => handleWSMessage(JSON.parse(evt.data));
  state.ws.onclose = () => {};
}
function wsSend(action, payload) {
  state.ws.send(JSON.stringify({ action, payload }));
}

function handleWSMessage(msg) {
  if (msg.type === "state") {
    renderGameState(msg.state);
    if (msg.debrief) renderDebrief(msg.debrief);
  } else if (msg.type === "round_started") {
    renderGameState(msg.state);
    hide("roundResult");
    if (msg.puzzle) startPuzzleUI(msg.puzzle);
    if (msg.your_view) startScenarioUI(msg.your_view);
  } else if (msg.type === "typing") {
    if (msg.player !== state.player.name) {
      show("typingIndicator");
      clearTimeout(window._typingTimeout);
      window._typingTimeout = setTimeout(() => hide("typingIndicator"), 2000);
    }
  }
}

let timerInterval = null;
function renderGameState(s) {
  const isHost = s.host === state.player.name;
  $("hostControls").classList.toggle("hidden", !isHost || s.status === "active");
  $("scenarioBanner").classList.toggle("hidden", !s.scenario_text);
  if (s.scenario_text) { $("scenarioTitle").textContent = "Scenario"; $("scenarioText").textContent = s.scenario_text; }

  // faces grid
  const grid = $("facesGrid");
  grid.innerHTML = "";
  s.players.forEach(p => {
    const tile = document.createElement("div");
    tile.className = "face-tile";
    const face = document.createElement("div");
    let cls = "face";
    if (p.connected) cls += " joined";
    if (p.hat) cls += " hat-assigned";
    if (p.submitted) cls += " submitted";
    if (!p.connected) cls += " disconnected";
    face.className = cls;
    if (p.hat) {
      face.style.background = HAT_COLORS[p.hat];
      face.textContent = p.submitted ? "😄" : HAT_EMOJI[p.hat];
    } else {
      face.style.background = "var(--bg-elevated)";
      face.textContent = "🙂";
    }
    tile.appendChild(face);
    const name = document.createElement("div");
    name.className = "face-name";
    name.textContent = p.name + (p.name === s.host ? " (host)" : "");
    tile.appendChild(name);
    grid.appendChild(tile);
  });

  clearInterval(timerInterval);
  if (s.status === "active" && s.seconds_left !== null) {
    let secs = s.seconds_left;
    const updateTimer = () => {
      const m = Math.floor(secs / 60), sec = String(secs % 60).padStart(2, "0");
      $("timerLabel").textContent = `⏱ ${m}:${sec}`;
      if (secs <= 0) clearInterval(timerInterval); else secs--;
    };
    updateTimer();
    timerInterval = setInterval(updateTimer, 1000);
  } else {
    $("timerLabel").textContent = "⏱ --:--";
  }

  $("playAgainBtn").classList.toggle("hidden", !(isHost && s.status === "round_result"));
  if (s.status === "round_result" && s.last_round_result) renderRoundResult(s.last_round_result);
  if (s.status !== "active") { hide("puzzleArea"); hide("scenarioArea"); }
}

$("startRoundBtn").onclick = () => wsSend("start_round", {});
$("playAgainBtn").onclick = () => wsSend("play_again", {});
$("leaveGameBtn").onclick = () => { wsSend("leave", {}); state.ws.close(); screen("home"); };

// ---------- puzzle mode ----------
function startPuzzleUI(puzzle) {
  show("puzzleArea");
  hide("scenarioArea");
  state.puzzleMatches = {};
  state.activeHatChip = null;

  const chips = $("hatPicker");
  chips.innerHTML = "";
  Object.keys(HAT_COLORS).forEach(hat => {
    const chip = document.createElement("div");
    chip.className = "hat-chip";
    chip.style.background = HAT_COLORS[hat];
    chip.textContent = HAT_EMOJI[hat];
    chip.onclick = () => {
      document.querySelectorAll(".hat-chip").forEach(c => c.classList.remove("selected"));
      chip.classList.add("selected");
      state.activeHatChip = hat;
    };
    chips.appendChild(chip);
  });

  const list = $("puzzleSentences");
  list.innerHTML = "";
  puzzle.sentences.forEach(s => {
    const row = document.createElement("div");
    row.className = "puzzle-sentence-row";
    row.innerHTML = `${s.text} <span class="assigned-hat" data-sid="${s.sentence_id}"></span>`;
    row.onclick = () => {
      if (!state.activeHatChip) return;
      state.puzzleMatches[s.sentence_id] = state.activeHatChip;
      row.querySelector(".assigned-hat").textContent = HAT_EMOJI[state.activeHatChip];
    };
    list.appendChild(row);
  });
}
$("submitPuzzleBtn").onclick = () => {
  wsSend("submit_answer", { matches: state.puzzleMatches });
  hide("puzzleArea");
};

// ---------- scenario mode ----------
function startScenarioUI(view) {
  hide("puzzleArea");
  show("scenarioArea");
  state.roleCard = view;
  const rc = $("roleCard");
  rc.style.borderLeft = `6px solid ${HAT_COLORS[view.your_hat]}`;
  rc.innerHTML = `<div style="font-size:1.5rem">${HAT_EMOJI[view.your_hat]} <strong>${view.role_card.name}</strong></div>
    <p class="muted small">${view.role_card.meaning}</p>
    <p>${view.role_card.prompt}</p>
    <p class="muted small"><em>Example: "${view.role_card.example_sentence}"</em></p>`;
  $("scenarioAnswer").value = "";
  $("scenarioAnswer").oninput = () => wsSend("typing", {});
}
$("submitScenarioBtn").onclick = () => {
  const text = $("scenarioAnswer").value.trim();
  if (!text) return;
  wsSend("submit_answer", { text });
  hide("scenarioArea");
};

// ---------- round result + debrief ----------
function renderRoundResult(result) {
  const box = $("roundResult");
  show(box.id);
  let html = `<h3>Round result</h3>`;
  if (result.team_xp) html += `<p>Team earned <strong>${result.team_xp} XP</strong></p>`;
  if (result.mode === "puzzle") {
    for (const [player, r] of Object.entries(result.results)) {
      html += `<div class="debrief-row"><strong>${player}</strong> — ${r.xp} XP<br>`;
      r.per_question.forEach(q => {
        html += `<div class="small ${q.correct ? "correct-tag" : "incorrect-tag"}">
          ${q.correct ? "✔ correct" : `✘ wrong — correct hat: ${HAT_EMOJI[q.correct_hat] || ""} ${q.correct_hat}`}
        </div>`;
      });
      html += `</div>`;
    }
  } else {
    for (const [player, r] of Object.entries(result.results)) {
      html += `<div class="debrief-row">
        <div style="width:36px;text-align:center">${HAT_EMOJI[r.hat]}</div>
        <div><strong>${player}</strong> ${r.first_submitter ? "⚡fastest" : ""}<br>
        <span class="${r.correct ? "correct-tag" : "incorrect-tag"}">${r.correct ? "On target" : "Needs work"}</span> (+${r.individual_bonus_xp} xp)<br>
        <span class="small">"${r.answer}"</span><br>
        <span class="small muted">${r.correction}</span></div></div>`;
    }
  }
  box.innerHTML = html;
}

function renderDebrief(debrief) {
  if (!debrief) return;
  const box = $("roundResult");
  let html = box.innerHTML + `<h3 style="margin-top:16px">🗣 Debrief — all hats, side by side</h3><p class="muted small">${debrief.scenario_text}</p>`;
  for (const [hat, d] of Object.entries(debrief.by_hat)) {
    html += `<div class="debrief-row"><div style="width:36px;text-align:center">${HAT_EMOJI[hat]}</div>
      <div><strong>${d.player}</strong><br>${d.answer}</div></div>`;
  }
  box.innerHTML = html;
}

// ---------- dashboard ----------
$("dashboardBtn").onclick = async () => {
  const data = await api("/api/dashboard");
  const indiv = $("leaderIndividuals");
  indiv.innerHTML = "";
  data.individuals.forEach((p, i) => {
    const row = document.createElement("div");
    row.className = "leader-row";
    row.innerHTML = `<span><span class="leader-rank">#${i + 1}</span>${p.name}</span><span>${p.weekly_xp} XP</span>`;
    indiv.appendChild(row);
  });
  const teams = $("leaderTeams");
  teams.innerHTML = "";
  data.teams.forEach((t, i) => {
    const row = document.createElement("div");
    row.className = "leader-row";
    row.innerHTML = `<span><span class="leader-rank">#${i + 1}</span>${t.name}</span><span>${t.weekly_xp} XP</span>`;
    teams.appendChild(row);
  });
  screen("dashboard");
};
$("backHomeBtn").onclick = () => screen("home");
