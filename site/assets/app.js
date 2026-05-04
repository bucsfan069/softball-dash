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

const DATA = { standings: [], schedule: [], teams: [], lastUpdated: null };
const FOCUS_TEAM_KEY = "lawrence";  // highlight Lawrence in the standings
const SEASON_STORAGE_KEY = "softball_selected_season";

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
  const [standings, schedule, teams, lastUpdated] = await Promise.all([
    loadJSON(`${base}/standings.json`, []),
    loadJSON(`${base}/schedule.json`, []),
    loadJSON(`${base}/teams.json`, []),
    loadJSON(`${base}/last_updated.json`, null),
  ]);
  Object.assign(DATA, { standings, schedule, teams, lastUpdated });
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
    return `
      <tr class="${isFocus ? "highlight" : ""}">
        <td class="rank">${row.rank || i + 1}</td>
        <td>
          <div class="team-cell">
            <span class="team-name">${row.team_name}</span>
            ${team ? `<span class="team-city">${team.city}</span>` : ""}
          </div>
        </td>
        <td>${row.wins ?? "—"}</td>
        <td>${row.losses ?? "—"}</td>
        <td>${row.scheduled_games ?? "—"}</td>
        <td>${rt.rs}</td>
        <td>${rt.ra}</td>
        <td>${row.preliminary_index != null ? Number(row.preliminary_index).toFixed(3) : "—"}</td>
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
        <td>${away ? away.name : g.away_team_key} <span class="team-city">at</span> ${home ? home.name : g.home_team_key}</td>
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

  grid.innerHTML = DATA.teams.map(t => {
    const s = standingByKey[t.key];
    const rt = runTotals[t.key] || { rs: 0, ra: 0 };
    const record = s ? `${s.wins}–${s.losses}` : "0–0";
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
  const a = teamByKey($("#h2h-a").value);
  const b = teamByKey($("#h2h-b").value);
  const out = $("#h2h-output");
  if (!a || !b || a.key === b.key) {
    out.innerHTML = `<p class="hint">Pick two different teams above to compare.</p>`;
    return;
  }
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
  aOpps.forEach(k => { if (bOpps.has(k)) commonOpponents.push(teamByKey(k)?.name || k); });

  out.innerHTML = `
    <div class="h2h-grid">
      <div class="h2h-col">
        <h3>${a.name}</h3>
        <div class="stat">${aStand.wins ?? 0}–${aStand.losses ?? 0}</div>
        <div class="substat">TI ${aStand.tournament_index != null ? Number(aStand.tournament_index).toFixed(3) : "—"}</div>
        <div class="substat">Seed #${aStand.rank ?? "—"}</div>
      </div>
      <div class="h2h-vs">vs.</div>
      <div class="h2h-col">
        <h3>${b.name}</h3>
        <div class="stat">${bStand.wins ?? 0}–${bStand.losses ?? 0}</div>
        <div class="substat">TI ${bStand.tournament_index != null ? Number(bStand.tournament_index).toFixed(3) : "—"}</div>
        <div class="substat">Seed #${bStand.rank ?? "—"}</div>
      </div>
    </div>
    <hr style="border-color: var(--border); margin: 16px 0;" />
    <p><strong>Head-to-head this season:</strong> ${played.length
      ? `${a.name} ${aWins} — ${b.name} ${bWins} (${played.length} played)`
      : "No games played yet between these two."}</p>
    <p><strong>Common opponents (both played):</strong> ${commonOpponents.length ? commonOpponents.join(", ") : "None yet."}</p>
  `;
}

// ------------------- Season & Refresh -------------------

function populateTeamFilters() {
  const teamFilter = $("#team-filter");
  const h2hA = $("#h2h-a");
  const h2hB = $("#h2h-b");
  // Clear existing team options (keep "All teams" in team-filter)
  while (teamFilter.options.length > 1) teamFilter.remove(1);
  h2hA.innerHTML = "";
  h2hB.innerHTML = "";
  DATA.teams.forEach((t, i) => {
    teamFilter.insertAdjacentHTML("beforeend", `<option value="${t.key}">${t.name}</option>`);
    h2hA.insertAdjacentHTML("beforeend", `<option value="${t.key}" ${t.key === "lawrence" ? "selected" : ""}>${t.name}</option>`);
    h2hB.insertAdjacentHTML("beforeend", `<option value="${t.key}" ${i === 1 ? "selected" : ""}>${t.name}</option>`);
  });
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
  renderStandings();
  renderSchedule();
  renderScouting();
  renderH2H();
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
    const data = await resp.json();
    if (data.ok) {
      await switchSeason(year);
      showToast(`Refreshed in ${(data.duration_ms / 1000).toFixed(1)}s`, "success");
    } else {
      showToast(data.error || "Refresh failed", "error");
    }
  } catch (err) {
    // On static hosts (GitHub Pages, Netlify) the API endpoint doesn't exist.
    // Hide the button rather than showing a confusing error.
    if (err instanceof TypeError) {
      btn.style.display = "none";
      return;
    }
    showToast(`Network error: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    label.textContent = "Refresh";
  }
}

// ------------------- Wiring -------------------

function wireEvents() {
  $("#team-filter").addEventListener("change", renderSchedule);
  $("#when-filter").addEventListener("change", renderSchedule);
  $("#h2h-a").addEventListener("change", renderH2H);
  $("#h2h-b").addEventListener("change", renderH2H);
  $("#season-select").addEventListener("change", e => switchSeason(parseInt(e.target.value, 10)));
  const refreshBtn = $("#refresh-btn");
  if (refreshBtn) refreshBtn.addEventListener("click", refreshCurrentSeason);
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
  renderStandings();
  renderSchedule();
  renderScouting();
  renderH2H();
  wireEvents();
})();
