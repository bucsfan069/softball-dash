/*
 * Class B North Softball Dashboard — frontend.
 * Reads JSON written by the Python scraper in ./data/ and renders:
 *   - Standings with Heal Points
 *   - Schedule & results (filterable)
 *   - Scouting cards per team
 *   - Head-to-head comparison
 *
 * No build step, no framework — intentionally simple so it runs from a
 * GitHub Pages / Netlify static host with zero backend.
 */

const DATA = { standings: [], schedule: [], teams: [], lastUpdated: null, tiHistory: {} };
const FOCUS_TEAM_KEY = "lawrence";  // highlight Lawrence in the standings
const SEASON_STORAGE_KEY = "softball_selected_season";
const HEAL_POINTS = { A: 40, B: 38, C: 36, D: 34 };
const LAWRENCE_CLASS = "B";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

async function loadJSON(path, fallback) {
  try {
    const resp = await fetch(path, { cache: "no-store" });
    if (!resp.ok) throw new Error(resp.status);
    return await resp.json();
  } catch (err) {
    console.warn(`Could not load ${path}:`, err);
    return fallback;
  }
}

async function loadAll(season) {
  const base = `./data/${season}`;
  const [standings, schedule, teams, lastUpdated, tiHistory] = await Promise.all([
    loadJSON(`${base}/standings.json`, []),
    loadJSON(`${base}/schedule.json`, []),
    loadJSON(`${base}/teams.json`, []),
    loadJSON(`${base}/last_updated.json`, null),
    loadJSON(`${base}/ti_history.json`, {}),
  ]);
  Object.assign(DATA, { standings, schedule, teams, lastUpdated, tiHistory });
}

// Returns a normalized { seasons: [{year, label}], current: <year> } object
// regardless of whether seasons.json is in the old array format or new object format.
async function loadSeasons() {
  const raw = await loadJSON("./data/seasons.json", []);
  if (Array.isArray(raw)) {
    const sorted = [...raw].sort((a, b) => b.year - a.year);
    return { seasons: raw, current: sorted[0]?.year ?? new Date().getFullYear() };
  }
  return raw;
}

// ------------------- Helpers -------------------

function computeRunTotals() {
  const totals = {};
  DATA.schedule.filter(g => g.played).forEach(g => {
    const hs = g.home_score ?? 0;
    const as_ = g.away_score ?? 0;
    if (!totals[g.home_team_key]) totals[g.home_team_key] = { rs: 0, ra: 0 };
    if (!totals[g.away_team_key]) totals[g.away_team_key] = { rs: 0, ra: 0 };
    totals[g.home_team_key].rs += hs;
    totals[g.home_team_key].ra += as_;
    totals[g.away_team_key].rs += as_;
    totals[g.away_team_key].ra += hs;
  });
  return totals;
}

function getNextLawrenceGame() {
  return DATA.schedule
    .filter(g => !g.played && (g.home_team_key === FOCUS_TEAM_KEY || g.away_team_key === FOCUS_TEAM_KEY))
    .sort((a, b) => (a.date || "").localeCompare(b.date || ""))[0] || null;
}

// Returns a copy of the standings re-sorted after simulating one game result.
// Each entry gets a simRank and rankDelta (positive = moved up).
function simulateGame(game, lawrenceWins) {
  const byKey = {};
  DATA.standings.forEach(s => { byKey[s.team_key] = { ...s }; });

  const opponentKey = game.home_team_key === FOCUS_TEAM_KEY ? game.away_team_key : game.home_team_key;
  const opponentClass = game.opponent_class || LAWRENCE_CLASS;
  const law = byKey[FOCUS_TEAM_KEY];
  const opp = byKey[opponentKey];

  if (lawrenceWins && law) {
    const heal = HEAL_POINTS[opponentClass] || 35;
    const actualHealSum = law.wins === 0 ? 0 : law.preliminary_index * law.scheduled_games;
    const oppPI = opp ? opp.preliminary_index : 1.0;
    law.wins = (law.wins || 0) + 1;
    law.preliminary_index = (actualHealSum + heal) / law.scheduled_games;
    law.tournament_index = ((law.tournament_index * law.scheduled_games / 10) + oppPI) / law.scheduled_games * 10;
  } else if (!lawrenceWins && opp) {
    const heal = HEAL_POINTS[LAWRENCE_CLASS];
    const actualHealSum = opp.wins === 0 ? 0 : opp.preliminary_index * opp.scheduled_games;
    const lawPI = law ? law.preliminary_index : 1.0;
    opp.wins = (opp.wins || 0) + 1;
    opp.preliminary_index = (actualHealSum + heal) / opp.scheduled_games;
    opp.tournament_index = ((opp.tournament_index * opp.scheduled_games / 10) + lawPI) / opp.scheduled_games * 10;
  }

  const currentRanks = {};
  DATA.standings.forEach((s, i) => { currentRanks[s.team_key] = i + 1; });

  return Object.values(byKey)
    .sort((a, b) => b.tournament_index - a.tournament_index)
    .map((s, i) => ({ ...s, simRank: i + 1, rankDelta: (currentRanks[s.team_key] || i + 1) - (i + 1) }));
}

// ------------------- Rendering -------------------

function renderLastUpdated() {
  const el = $("#last-updated");
  if (!DATA.lastUpdated) { el.textContent = "Data not yet refreshed"; return; }
  const d = new Date(DATA.lastUpdated.utc);
  el.textContent = `Updated ${d.toLocaleString()} · source: ${DATA.lastUpdated.standings_source || "mpa"}`;
}

function teamByName(name) {
  if (!name) return null;
  const n = name.toLowerCase();
  return DATA.teams.find(t => t.name.toLowerCase() === n || n.includes(t.name.toLowerCase()));
}
function teamByKey(key) { return DATA.teams.find(t => t.key === key); }
function teamDisplayName(key) {
  return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function renderStandings() {
  const body = $("#standings-body");
  if (!DATA.standings.length) {
    body.innerHTML = `<tr><td colspan="9" class="loading">No standings data yet. Run the scraper to populate.</td></tr>`;
    return;
  }
  const runTotals = computeRunTotals();
  const rows = DATA.standings.map((row, i) => {
    const team = row.team_key ? teamByKey(row.team_key) : teamByName(row.team_name);
    const isFocus = team && team.key === FOCUS_TEAM_KEY;
    const rt = team ? (runTotals[team.key] || { rs: 0, ra: 0 }) : { rs: 0, ra: 0 };
    const w = row.wins || 0;
    const l = row.losses || 0;
    const t = row.ties || 0;
    const gp = w + l + t;
    const winPct = gp > 0 ? ((w + 0.5 * t) / gp).toFixed(3) : "—";
    const rd = rt.rs - rt.ra;
    const rdStr = gp > 0 ? (rd > 0 ? `+${rd}` : String(rd)) : "—";
    const rdClass = rd > 0 ? "rd-pos" : rd < 0 ? "rd-neg" : "";
    return `
      <tr class="${isFocus ? "highlight" : ""}">
        <td class="rank">${row.rank || i + 1}</td>
        <td>
          <div class="team-cell">
            <span class="team-name">${row.team_name}</span>
            ${team ? `<span class="team-city">${team.city}</span>` : ""}
          </div>
        </td>
        <td class="grp-start">${w}</td>
        <td>${l}</td>
        <td>${t}</td>
        <td>${winPct}</td>
        <td class="grp-start">${rt.rs}</td>
        <td>${rt.ra}</td>
        <td class="${rdClass}">${rdStr}</td>
        <td class="grp-start">${row.preliminary_index != null ? Number(row.preliminary_index).toFixed(3) : "—"}</td>
        <td><strong>${row.tournament_index != null ? Number(row.tournament_index).toFixed(4) : "—"}</strong></td>
      </tr>
    `;
  }).join("");
  body.innerHTML = rows;
}

function renderSchedule() {
  const body = $("#schedule-body");
  const teamFilter = $("#team-filter").value;
  const whenFilter = $("#when-filter").value;

  const filtered = DATA.schedule.filter(g => {
    if (teamFilter !== "all" && g.home_team_key !== teamFilter && g.away_team_key !== teamFilter) return false;
    if (whenFilter === "upcoming" && g.played) return false;
    if (whenFilter === "past" && !g.played) return false;
    return true;
  }).sort((a, b) => (a.date || "").localeCompare(b.date || ""));

  if (!filtered.length) {
    body.innerHTML = `<tr><td colspan="4" class="loading">No games match your filter.</td></tr>`;
    return;
  }

  body.innerHTML = filtered.map(g => {
    const home = teamByKey(g.home_team_key);
    const away = teamByKey(g.away_team_key);
    let resultCell = "<span class='chip'>Scheduled</span>";
    if (g.played) {
      const homeScore = g.home_score ?? 0;
      const awayScore = g.away_score ?? 0;
      const lawrenceIsHome = g.home_team_key === FOCUS_TEAM_KEY;
      const lawrenceIsAway = g.away_team_key === FOCUS_TEAM_KEY;
      let chipClass = "chip";
      if (lawrenceIsHome || lawrenceIsAway) {
        const lawrenceScore = lawrenceIsHome ? homeScore : awayScore;
        const oppScore = lawrenceIsHome ? awayScore : homeScore;
        chipClass = lawrenceScore > oppScore ? "chip win" : "chip loss";
      }
      resultCell = `<span class="${chipClass}">${homeScore}–${awayScore}</span>`;
    }
    return `
      <tr>
        <td>${g.date || "TBD"}</td>
        <td>${away ? away.name : teamDisplayName(g.away_team_key)} <span class="team-city">at</span> ${home ? home.name : teamDisplayName(g.home_team_key)}</td>
        <td>${(g.home_team_key === FOCUS_TEAM_KEY || g.away_team_key === FOCUS_TEAM_KEY)
              ? (g.home_team_key === FOCUS_TEAM_KEY ? "Home" : "Away") : "—"}</td>
        <td>${resultCell}</td>
      </tr>
    `;
  }).join("");
}

function renderScouting() {
  const grid = $("#scouting-grid");
  if (!DATA.teams.length) {
    grid.innerHTML = `<p class="loading">No team data yet.</p>`;
    return;
  }
  const standingByKey = {};
  DATA.standings.forEach((s, i) => {
    const t = s.team_key ? teamByKey(s.team_key) : teamByName(s.team_name);
    if (t) standingByKey[t.key] = { ...s, rank: s.rank || i + 1 };
  });
  const runTotals = computeRunTotals();

  const sortVal = $("#scout-sort")?.value || "rank";
  const sortedTeams = [...DATA.teams].sort((a, b) => {
    if (sortVal === "alpha") return a.name.localeCompare(b.name);
    const ra = standingByKey[a.key]?.rank ?? 999;
    const rb = standingByKey[b.key]?.rank ?? 999;
    return ra - rb;
  });

  grid.innerHTML = sortedTeams.map(t => {
    const s = standingByKey[t.key];
    const rt = runTotals[t.key] || { rs: 0, ra: 0 };
    const record = s
      ? (s.ties ? `${s.wins}–${s.losses}–${s.ties}` : `${s.wins}–${s.losses}`)
      : "0–0";
    const ti = s && s.tournament_index != null ? Number(s.tournament_index).toFixed(3) : "—";
    const diff = rt.rs - rt.ra;
    const diffStr = diff > 0 ? `+${diff}` : String(diff);
    const maxprepsUrl = t.maxpreps_slug
      ? `https://www.maxpreps.com/me/${t.city.toLowerCase().replace(/\s+/g, "-")}/${t.maxpreps_slug}/softball/`
      : null;
    return `
      <div class="scout-card" data-team="${t.key}">
        <h3>${t.name}</h3>
        <div class="line"><span>${t.city}</span><span class="chip">#${s ? s.rank : "—"}</span></div>
        <div class="line"><span>Record</span><strong>${record}</strong></div>
        <div class="line"><span>RS / RA</span><strong>${rt.rs} / ${rt.ra} <span class="muted">(${diffStr})</span></strong></div>
        <div class="line"><span>Tournament Index</span><strong>${ti}</strong></div>
        ${maxprepsUrl ? `<div class="line"><a href="${maxprepsUrl}" target="_blank" rel="noopener">MaxPreps ↗</a></div>` : ""}
      </div>
    `;
  }).join("");
}

function renderH2H() {
  const aKey = $("#h2h-a").value;
  const bKey = $("#h2h-b").value;
  const out = $("#h2h-output");
  if (!aKey || !bKey || aKey === bKey) {
    out.innerHTML = `<p class="hint">Pick two different teams above to compare.</p>`;
    return;
  }
  const a = teamByKey(aKey) || { key: aKey, name: teamDisplayName(aKey), city: "" };
  const b = teamByKey(bKey) || { key: bKey, name: teamDisplayName(bKey), city: "" };

  const games = DATA.schedule.filter(g =>
    (g.home_team_key === a.key && g.away_team_key === b.key) ||
    (g.home_team_key === b.key && g.away_team_key === a.key)
  );
  const played = games.filter(g => g.played);
  const aWins = played.filter(g => (g.home_team_key === a.key ? g.home_score > g.away_score : g.away_score > g.home_score)).length;
  const bWins = played.length - aWins;

  const standingByKey = {};
  DATA.standings.forEach(s => {
    const t = s.team_key ? teamByKey(s.team_key) : teamByName(s.team_name);
    if (t) standingByKey[t.key] = s;
  });
  const aStand = standingByKey[a.key] || {};
  const bStand = standingByKey[b.key] || {};

  const commonOpponents = [];
  const aOpps = new Set(DATA.schedule.filter(g => g.played && (g.home_team_key === a.key || g.away_team_key === a.key))
    .map(g => g.home_team_key === a.key ? g.away_team_key : g.home_team_key));
  const bOpps = new Set(DATA.schedule.filter(g => g.played && (g.home_team_key === b.key || g.away_team_key === b.key))
    .map(g => g.home_team_key === b.key ? g.away_team_key : g.home_team_key));
  aOpps.forEach(k => { if (bOpps.has(k)) commonOpponents.push(teamByKey(k)?.name || teamDisplayName(k)); });

  const aIsConf = !!standingByKey[a.key];
  const bIsConf = !!standingByKey[b.key];

  out.innerHTML = `
    <div class="h2h-grid">
      <div class="h2h-col">
        <h3>${a.name}</h3>
        <div class="stat">${aStand.wins ?? "—"}–${aStand.losses ?? "—"}</div>
        <div class="substat">TI ${aStand.tournament_index != null ? Number(aStand.tournament_index).toFixed(3) : (aIsConf ? "—" : "Non-conf")}</div>
        <div class="substat">${aIsConf ? `Seed #${aStand.rank ?? "—"}` : "Non-conference"}</div>
      </div>
      <div class="h2h-vs">vs.</div>
      <div class="h2h-col">
        <h3>${b.name}</h3>
        <div class="stat">${bStand.wins ?? "—"}–${bStand.losses ?? "—"}</div>
        <div class="substat">TI ${bStand.tournament_index != null ? Number(bStand.tournament_index).toFixed(3) : (bIsConf ? "—" : "Non-conf")}</div>
        <div class="substat">${bIsConf ? `Seed #${bStand.rank ?? "—"}` : "Non-conference"}</div>
      </div>
    </div>
    <hr style="border-color: var(--border); margin: 16px 0;" />
    <p><strong>Head-to-head this season:</strong> ${played.length
      ? `${a.name} ${aWins} — ${b.name} ${bWins} (${played.length} played)`
      : "No games played yet between these two."}</p>
    <p><strong>Common opponents (both played):</strong> ${commonOpponents.length ? commonOpponents.join(", ") : "None yet."}</p>
  `;
}

function renderWhatIf() {
  const container = $("#whatif-content");
  if (!container) return;

  const game = getNextLawrenceGame();
  if (!game) {
    container.innerHTML = `<p class="hint">No upcoming Lawrence games remaining this season.</p>`;
    return;
  }

  const opponentKey = game.home_team_key === FOCUS_TEAM_KEY ? game.away_team_key : game.home_team_key;
  const isHome = game.home_team_key === FOCUS_TEAM_KEY;
  const opponent = teamByKey(opponentKey);
  const opponentName = opponent ? opponent.name : opponentKey.replace(/_/g, " ");
  const opponentClass = game.opponent_class || "B";
  const inConference = !!DATA.standings.find(s => s.team_key === opponentKey);

  const winSim = simulateGame(game, true);
  const lossSim = simulateGame(game, false);

  // TI deltas for headings
  const lawStanding = DATA.standings.find(s => s.team_key === FOCUS_TEAM_KEY);
  const currentLawTI = lawStanding?.tournament_index ?? 0;
  const winLawTI = winSim.find(s => s.team_key === FOCUS_TEAM_KEY)?.tournament_index ?? currentLawTI;
  const tiGain = winLawTI - currentLawTI;

  const oppStanding = DATA.standings.find(s => s.team_key === opponentKey);
  const currentOppTI = oppStanding?.tournament_index ?? null;
  const lossOppTI = lossSim.find(s => s.team_key === opponentKey)?.tournament_index ?? null;

  const winSubline = `TI ${currentLawTI.toFixed(3)} → ${winLawTI.toFixed(3)} <span class="rank-up">(+${tiGain.toFixed(3)})</span>`;
  let lossSubline;
  if (inConference && currentOppTI !== null && lossOppTI !== null) {
    const oppGain = lossOppTI - currentOppTI;
    lossSubline = `${opponentName} TI +${oppGain.toFixed(3)}`;
  } else {
    lossSubline = `No conference TI change`;
  }

  function deltaHtml(d) {
    if (d > 0) return `<span class="rank-up">▲${d}</span>`;
    if (d < 0) return `<span class="rank-dn">▼${Math.abs(d)}</span>`;
    return `<span class="rank-same">—</span>`;
  }

  const thead = `<thead><tr><th>#</th><th>Team</th><th>TI</th><th>Δ</th></tr></thead>`;

  function buildRows(items) {
    return items.map(s => {
      const isLaw = s.team_key === FOCUS_TEAM_KEY;
      const isOpp = s.team_key === opponentKey;
      const cutline = s.simRank === 9
        ? `<tr class="playoff-cutline"><td colspan="4">— playoff cutline —</td></tr>`
        : "";
      return `${cutline}<tr class="${isLaw ? "highlight" : isOpp ? "whatif-opp" : ""}">
        <td class="rank">${s.simRank}</td>
        <td>${s.team_name}</td>
        <td>${Number(s.tournament_index).toFixed(3)}</td>
        <td>${deltaHtml(s.rankDelta)}</td>
      </tr>`;
    }).join("");
  }

  function miniTable(simStandings) {
    const lawIdx = simStandings.findIndex(s => s.team_key === FOCUS_TEAM_KEY);
    const start = Math.max(0, lawIdx - 3);
    const end   = Math.min(simStandings.length - 1, lawIdx + 3);
    const compact = simStandings.slice(start, end + 1);

    const aboveCount = start;
    const belowCount = simStandings.length - 1 - end;
    const ellipsisTop = aboveCount > 0
      ? `<tr class="whatif-ellipsis"><td colspan="4">↑ ${aboveCount} team${aboveCount > 1 ? "s" : ""} not shown</td></tr>`
      : "";
    const ellipsisBottom = belowCount > 0
      ? `<tr class="whatif-ellipsis"><td colspan="4">↓ ${belowCount} team${belowCount > 1 ? "s" : ""} not shown</td></tr>`
      : "";

    return `
      <div class="table-wrap"><table class="whatif-table">
        ${thead}
        <tbody>${ellipsisTop}${buildRows(compact)}${ellipsisBottom}</tbody>
      </table></div>
      <details class="whatif-expand">
        <summary>Show all ${simStandings.length} teams</summary>
        <div class="table-wrap"><table class="whatif-table">
          ${thead}<tbody>${buildRows(simStandings)}</tbody>
        </table></div>
      </details>`;
  }

  container.innerHTML = `
    <div class="whatif-game">
      <span class="whatif-label">Next Lawrence game:</span>
      <strong>${game.date}</strong> &mdash;
      Lawrence <strong>${isHome ? "vs." : "at"}</strong> ${opponentName}
      <span class="chip">Class ${opponentClass}</span>
      <span class="whatif-label" style="margin-left:8px">Heal pts if win: ${HEAL_POINTS[opponentClass] || 35}</span>
    </div>
    <p class="hint">Approximate — assumes no other games are played simultaneously.</p>
    <div class="whatif-grid">
      <div class="whatif-col">
        <div class="whatif-scenario whatif-win">
          If Lawrence Wins
          <div class="whatif-ti">${winSubline}</div>
        </div>
        ${miniTable(winSim)}
      </div>
      <div class="whatif-col">
        <div class="whatif-scenario whatif-loss">
          If Lawrence Loses
          <div class="whatif-ti">${lossSubline}</div>
        </div>
        ${miniTable(lossSim)}
      </div>
    </div>
  `;
}

function autoSelectNextOpponent() {
  const game = getNextLawrenceGame();
  const h2hA = $("#h2h-a");
  const h2hB = $("#h2h-b");
  if (h2hA) h2hA.value = FOCUS_TEAM_KEY;
  if (game && h2hB) {
    const opponentKey = game.home_team_key === FOCUS_TEAM_KEY ? game.away_team_key : game.home_team_key;
    const inDropdown = Array.from(h2hB.options).some(o => o.value === opponentKey);
    if (inDropdown) h2hB.value = opponentKey;
  }
  renderH2H();
}

// ------------------- Season & Refresh -------------------

function populateTeamFilters() {
  const teamFilter = $("#team-filter");
  const h2hA = $("#h2h-a");
  const h2hB = $("#h2h-b");

  // Clear existing options (keep "All teams" in team-filter)
  while (teamFilter.options.length > 1) teamFilter.remove(1);
  h2hA.innerHTML = "";
  h2hB.innerHTML = "";

  // Find non-conference teams present in the schedule
  const confKeys = new Set(DATA.teams.map(t => t.key));
  const nonConfKeys = [...new Set(
    DATA.schedule.flatMap(g => [g.home_team_key, g.away_team_key])
      .filter(k => k && !confKeys.has(k))
  )].sort((a, b) => teamDisplayName(a).localeCompare(teamDisplayName(b)));

  const confOptHtml = (selectedKey) => DATA.teams.map(t =>
    `<option value="${t.key}" ${t.key === selectedKey ? "selected" : ""}>${t.name}</option>`
  ).join("");
  const nonConfOptHtml = nonConfKeys.map(k =>
    `<option value="${k}">${teamDisplayName(k)}</option>`
  ).join("");

  // Schedule team filter
  DATA.teams.forEach(t => {
    teamFilter.insertAdjacentHTML("beforeend", `<option value="${t.key}">${t.name}</option>`);
  });
  if (nonConfKeys.length) {
    teamFilter.insertAdjacentHTML("beforeend",
      `<optgroup label="Non-conference">${nonConfOptHtml}</optgroup>`);
  }

  // H2H dropdowns — wrap conference in optgroup only when there are non-conf teams
  if (nonConfKeys.length) {
    h2hA.innerHTML =
      `<optgroup label="Class B North">${confOptHtml("lawrence")}</optgroup>` +
      `<optgroup label="Non-conference">${nonConfOptHtml}</optgroup>`;
    const secondKey = DATA.teams[1]?.key ?? "";
    h2hB.innerHTML =
      `<optgroup label="Class B North">${confOptHtml(secondKey)}</optgroup>` +
      `<optgroup label="Non-conference">${nonConfOptHtml}</optgroup>`;
  } else {
    h2hA.innerHTML = confOptHtml("lawrence");
    const secondKey = DATA.teams[1]?.key ?? "";
    h2hB.innerHTML = confOptHtml(secondKey);
  }
}

function populateSeasonDropdown(seasons) {
  const sel = $("#season-select");
  sel.innerHTML = "";
  // Newest season first
  const sorted = [...seasons].sort((a, b) => b.year - a.year);
  sorted.forEach(s => {
    sel.insertAdjacentHTML("beforeend", `<option value="${s.year}">${s.label}</option>`);
  });
}

async function switchSeason(year) {
  localStorage.setItem(SEASON_STORAGE_KEY, String(year));
  await loadAll(year);
  renderLastUpdated();
  populateTeamFilters();
  populateTiDropdown();
  renderStandings();
  renderSchedule();
  renderScouting();
  autoSelectNextOpponent();
  renderWhatIf();
  renderTiHistory();
}

function showToast(message, type = "info") {
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  document.body.appendChild(el);
  // Trigger reflow before adding the visible class so the CSS transition fires
  el.getBoundingClientRect();
  el.classList.add("toast-visible");
  setTimeout(() => {
    el.classList.remove("toast-visible");
    setTimeout(() => el.remove(), 300);
  }, 4000);
}

async function refreshCurrentSeason() {
  const btn = $("#refresh-btn");
  const label = $("#refresh-label");
  const year = parseInt($("#season-select").value, 10);

  btn.disabled = true;
  label.textContent = "Refreshing…";

  try {
    const resp = await fetch("/api/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ year }),
    });
    // On static hosts (GitHub Pages) the endpoint returns a 404 HTML page.
    // Treat any non-JSON response the same as a network failure — hide the button.
    let data;
    try { data = await resp.json(); } catch { btn.style.display = "none"; return; }
    if (data.ok) {
      await switchSeason(year);
      showToast(`Refreshed in ${(data.duration_ms / 1000).toFixed(1)}s`, "success");
    } else {
      showToast(data.error || "Refresh failed", "error");
    }
  } catch (err) {
    // TypeError = fetch failed entirely (no network, strict CORS, etc.)
    btn.style.display = "none";
  } finally {
    btn.disabled = false;
    label.textContent = "Refresh";
  }
}

// ------------------- TI History -------------------

function populateTiDropdown() {
  const sel = $("#ti-team-select");
  if (!sel) return;
  sel.innerHTML = DATA.teams.map(t =>
    `<option value="${t.key}" ${t.key === FOCUS_TEAM_KEY ? "selected" : ""}>${t.name}</option>`
  ).join("");
}

function renderTiHistory() {
  const sel = $("#ti-team-select");
  const content = $("#ti-history-content");
  if (!sel || !content) return;

  const teamKey = sel.value;
  const info = DATA.tiHistory[teamKey];

  if (!info || !info.events) {
    content.innerHTML = `<p class="hint">No TI history data for this team yet.</p>`;
    return;
  }

  const standingRow = DATA.standings.find(s => s.team_key === teamKey);
  const officialTI = standingRow ? Number(standingRow.tournament_index).toFixed(4) : null;
  const localTI = Number(info.final_ti).toFixed(4);

  const winEvents = info.events.filter(e => e.event_type === "win").length;
  const cascadeEvents = info.events.filter(e => e.event_type === "opponent_win").length;

  function fmtDate(d) {
    if (!d) return "—";
    const [, m, day] = d.split("-");
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${months[parseInt(m,10)-1]} ${parseInt(day,10)}`;
  }

  function classChip(cls) {
    return `<span class="chip ti-class-chip ti-class-${cls}">Class ${cls}</span>`;
  }

  const header = `
    <div class="ti-summary">
      <div class="ti-summary-row">
        <span class="ti-summary-label">Team:</span>
        <span class="ti-summary-val">${info.team_name}</span>
      </div>
      ${officialTI ? `<div class="ti-summary-row">
        <span class="ti-summary-label">Official TI (MPA):</span>
        <span class="ti-summary-val ti-official">${officialTI}</span>
      </div>` : ""}
      <div class="ti-summary-row">
        <span class="ti-summary-label">Locally replayed TI:</span>
        <span class="ti-summary-val">${localTI}</span>
        <span class="ti-summary-note">May differ slightly from official — based on schedule data</span>
      </div>
      <div class="ti-summary-row">
        <span class="ti-summary-label">Events:</span>
        <span class="ti-summary-val">${winEvents} win${winEvents !== 1 ? "s" : ""} · ${cascadeEvents} ripple effect${cascadeEvents !== 1 ? "s" : ""}</span>
      </div>
    </div>
    <div class="ti-legend">
      <span class="ti-legend-item"><span class="ti-dot ti-dot-win"></span> Direct win</span>
      <span class="ti-legend-item"><span class="ti-dot ti-dot-opp"></span> Ripple effect (beaten opponent won another game)</span>
    </div>`;

  if (!info.events.length) {
    content.innerHTML = header + `<p class="hint" style="margin-top:12px">No TI-affecting events yet this season.</p>`;
    return;
  }

  const rows = info.events.map(e => {
    const deltaStr = `+${e.ti_delta.toFixed(4)}`;
    const tiAfterStr = e.ti_after.toFixed(4);

    if (e.event_type === "win") {
      const classStr = e.opponent_class || "B";
      return `
        <div class="ti-event ti-event-win">
          <div class="ti-event-date">${fmtDate(e.date)}</div>
          <div class="ti-event-body">
            <div class="ti-event-title">Beat ${e.opponent_name} ${classChip(classStr)}</div>
            <div class="ti-event-detail">
              Score: ${e.score} &nbsp;·&nbsp; Their PI at the time: ${Number(e.opponent_pi).toFixed(3)}
            </div>
            <div class="ti-event-explain">
              Their PI was added to your TI sum. TI = (sum of beaten opponents' PI) ÷ scheduled games × 10
            </div>
          </div>
          <div class="ti-event-delta">
            <span class="ti-delta-val">${deltaStr}</span>
            <span class="ti-delta-now">→ ${tiAfterStr}</span>
          </div>
        </div>`;
    } else {
      return `
        <div class="ti-event ti-event-opp">
          <div class="ti-event-date">${fmtDate(e.date)}</div>
          <div class="ti-event-body">
            <div class="ti-event-title">${e.game_winner_name} beat ${e.game_loser_name}</div>
            <div class="ti-event-detail">
              ${e.game_winner_name}'s PI increased — and you previously beat them, so their higher PI lifted your TI
            </div>
          </div>
          <div class="ti-event-delta">
            <span class="ti-delta-val">${deltaStr}</span>
            <span class="ti-delta-now">→ ${tiAfterStr}</span>
          </div>
        </div>`;
    }
  }).join("");

  content.innerHTML = header + `<div class="ti-timeline">${rows}</div>`;
}

// ------------------- Wiring -------------------

function wireEvents() {
  $("#team-filter").addEventListener("change", renderSchedule);
  $("#when-filter").addEventListener("change", renderSchedule);
  $("#scout-sort").addEventListener("change", renderScouting);
  $("#h2h-a").addEventListener("change", renderH2H);
  $("#h2h-b").addEventListener("change", renderH2H);
  const tiSel = $("#ti-team-select");
  if (tiSel) tiSel.addEventListener("change", renderTiHistory);
  $("#season-select").addEventListener("change", e => switchSeason(parseInt(e.target.value, 10)));
  const refreshBtn = $("#refresh-btn");
  if (refreshBtn) refreshBtn.addEventListener("click", refreshCurrentSeason);
  $$(".panel-toggle").forEach(btn => {
    btn.addEventListener("click", () => btn.closest(".panel").classList.toggle("collapsed"));
  });
  $$(".nav-link").forEach(link => {
    link.addEventListener("click", () => {
      $$(".nav-link").forEach(l => l.classList.remove("active"));
      link.classList.add("active");
    });
  });
}

(async () => {
  const { seasons, current } = await loadSeasons();
  populateSeasonDropdown(seasons);

  // Restore the user's last-selected season from localStorage, falling back to
  // the manifest's "current" season if the saved value no longer exists.
  const saved = parseInt(localStorage.getItem(SEASON_STORAGE_KEY) || "", 10);
  const defaultYear = (saved && seasons.some(s => s.year === saved))
    ? saved
    : (current ?? new Date().getFullYear());

  $("#season-select").value = String(defaultYear);
  await loadAll(defaultYear);
  renderLastUpdated();
  populateTeamFilters();
  populateTiDropdown();
  renderStandings();
  renderSchedule();
  renderScouting();
  autoSelectNextOpponent();
  renderWhatIf();
  renderTiHistory();
  wireEvents();
})();
