const state = {
  maps: [],
  status: null,
  actions: [],
  selectedMap: null,
  selectedJob: null,
  pollTimer: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function escapeText(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function mapStatus(key) {
  return state.status?.maps?.find((item) => item.key === key) || {};
}

function statusPill(label, good, badWhenFalse = false) {
  const cls = good ? "pill ok" : badWhenFalse ? "pill bad" : "pill";
  return `<span class="${cls}">${label}</span>`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

async function refreshAll() {
  const [maps, status, actions, jobs] = await Promise.all([
    api("/api/maps"),
    api("/api/status"),
    api("/api/actions"),
    api("/api/jobs"),
  ]);
  state.maps = maps;
  state.status = status;
  state.actions = actions;
  if (!state.selectedMap && maps.length) state.selectedMap = maps[0].key;
  $("#rootPath").textContent = status.root;
  renderMaps();
  renderMapSelect();
  renderMapDetail();
  renderActions();
  renderSetup();
  renderJobs(jobs);
}

function renderMaps() {
  $("#processSummary").textContent = `${state.status.processCount} DayZ server process(es)`;
  $("#processSummary").className = state.status.processCount ? "pill ok" : "pill";
  const grid = $("#mapGrid");
  grid.innerHTML = "";
  for (const map of state.maps) {
    const status = mapStatus(map.key);
    const card = document.createElement("article");
    card.className = "map-card";
    card.tabIndex = 0;
    card.addEventListener("click", () => selectMap(map.key, true));
    card.innerHTML = `
      <h3>${escapeText(map.title)}</h3>
      <dl class="kv">
        <dt>Key</dt><dd>${escapeText(map.key)}</dd>
        <dt>Ports</dt><dd>${map.port} / query ${map.queryPort}</dd>
        <dt>Mission</dt><dd>${escapeText(map.mission || "unknown")}</dd>
        <dt>Profile</dt><dd>${escapeText(map.profilesDir)}</dd>
      </dl>
      <div class="status-row">
        ${statusPill("game", status.gameActive)}
        ${statusPill("query", status.queryActive)}
        ${statusPill("config", map.configExists, true)}
        ${statusPill("mission", map.missionExists, true)}
        ${statusPill(`${map.missingMods.length} missing mods`, map.missingMods.length === 0, map.missingMods.length > 0)}
        ${status.log?.ready ? statusPill("ready log", true) : statusPill("not ready", false)}
      </div>
    `;
    grid.appendChild(card);
  }
}

function renderMapSelect() {
  const select = $("#mapSelect");
  select.innerHTML = "";
  for (const map of state.maps) {
    const option = document.createElement("option");
    option.value = map.key;
    option.textContent = map.title;
    if (map.key === state.selectedMap) option.selected = true;
    select.appendChild(option);
  }
}

function renderMapDetail() {
  const map = state.maps.find((item) => item.key === state.selectedMap);
  if (!map) return;
  const status = mapStatus(map.key);
  const missing = map.missingMods.length ? map.missingMods.join(", ") : "none";
  $("#mapDetail").innerHTML = `
    <article class="detail-card">
      <h3>Launch</h3>
      <dl class="kv">
        <dt>Config</dt><dd>${escapeText(map.config)}</dd>
        <dt>Profile</dt><dd>${escapeText(map.profilesDir)}</dd>
        <dt>CPU</dt><dd>${escapeText(map.cpu)}</dd>
        <dt>Imported</dt><dd>${map.isImported ? "yes" : "no"}</dd>
      </dl>
    </article>
    <article class="detail-card">
      <h3>Network</h3>
      <dl class="kv">
        <dt>Game port</dt><dd>${map.port} ${status.gameActive ? "(active)" : "(inactive)"}</dd>
        <dt>Query port</dt><dd>${map.queryPort} ${status.queryActive ? "(active)" : "(inactive)"}</dd>
        <dt>Steam port</dt><dd>${map.steamPort} ${status.steamActive ? "(active)" : "(inactive)"}</dd>
        <dt>PIDs</dt><dd>${(status.pids || []).join(", ") || "none"}</dd>
      </dl>
    </article>
    <article class="detail-card">
      <h3>Files</h3>
      <dl class="kv">
        <dt>Config</dt><dd>${map.configExists ? "present" : "missing"}</dd>
        <dt>Mission</dt><dd>${map.missionExists ? "present" : "missing"}</dd>
        <dt>Mods</dt><dd>${map.modCount} listed</dd>
        <dt>Missing</dt><dd>${escapeText(missing)}</dd>
      </dl>
    </article>
    <article class="detail-card">
      <h3>Latest Log</h3>
      <dl class="kv">
        <dt>File</dt><dd>${escapeText(status.log?.file || "none")}</dd>
        <dt>Ready</dt><dd>${status.log?.ready ? "yes" : "no"}</dd>
        <dt>Blockers</dt><dd>${status.log?.blockers ?? 0}</dd>
        <dt>Updated</dt><dd>${escapeText(status.log?.updated || "unknown")}</dd>
      </dl>
    </article>
  `;
}

function actionButton(action) {
  const danger = action.risk === "high" ? " danger" : "";
  return `
    <article class="action-card">
      <h3>${escapeText(action.label)}</h3>
      <p>${escapeText(action.description)}</p>
      <footer>
        <span class="pill ${action.risk === "high" ? "bad" : action.risk === "guarded" ? "warning" : ""}">${action.risk}</span>
        <button class="${danger}" data-action="${action.key}" data-map-source="${action.mapMode === "none" ? "" : "selected"}" type="button">Run</button>
      </footer>
    </article>
  `;
}

function renderActions() {
  const maintenance = state.actions.filter((item) => ["maintenance", "diagnostics"].includes(item.group));
  const generation = state.actions.filter((item) => ["generation", "high-risk", "map"].includes(item.group));
  $("#maintenanceActions").innerHTML = maintenance.map(actionButton).join("");
  $("#generationActions").innerHTML = generation.map(actionButton).join("");
}

function renderSetup() {
  const configMissing = state.maps.filter((map) => !map.configExists);
  const missionMissing = state.maps.filter((map) => !map.missionExists);
  const modMissing = state.maps.filter((map) => map.missingMods.length > 0);
  $("#setupChecklist").innerHTML = `
    <article class="check-card">
      <h3>Private Configs</h3>
      <p class="${configMissing.length ? "pill bad" : "pill ok"}">${configMissing.length ? `${configMissing.length} missing` : "all present"}</p>
    </article>
    <article class="check-card">
      <h3>Mission Folders</h3>
      <p class="${missionMissing.length ? "pill bad" : "pill ok"}">${missionMissing.length ? `${missionMissing.length} missing` : "all present"}</p>
    </article>
    <article class="check-card">
      <h3>Workshop Mods</h3>
      <p class="${modMissing.length ? "pill bad" : "pill ok"}">${modMissing.length ? `${modMissing.length} maps missing mods` : "all listed mods present"}</p>
    </article>
    <article class="check-card">
      <h3>Validation</h3>
      <p class="muted">Run public repo and imported-map validation before publishing or sharing configs.</p>
    </article>
  `;
}

function renderJobs(jobs) {
  const list = $("#jobList");
  list.innerHTML = "";
  for (const job of jobs.slice(0, 12)) {
    const item = document.createElement("div");
    item.className = `job-item ${state.selectedJob === job.id ? "active" : ""}`;
    item.addEventListener("click", () => showJob(job.id));
    item.innerHTML = `
      <strong>${escapeText(job.label)}</strong>
      <span>${escapeText(job.status)}</span>
      <span>${escapeText(job.createdAt)}</span>
      <span>${job.returncode ?? ""}</span>
    `;
    list.appendChild(item);
  }
}

async function runAction(actionKey, explicitMap) {
  const action = state.actions.find((item) => item.key === actionKey);
  if (!action) return;
  let map = explicitMap;
  if (!map && action.mapMode !== "none") map = state.selectedMap;
  if (action.mapMode === "all") map = explicitMap || "all";
  if (action.key === "recover_imported_map" && map && !isImportedMap(map)) {
    alert("Recover Imported requires an imported map.");
    return;
  }
  let confirm = "";
  if (action.confirm) {
    confirm = prompt(`Type ${action.confirm} to run: ${action.label}`) || "";
    if (confirm !== action.confirm) return;
  }
  const job = await api("/api/actions/run", {
    method: "POST",
    body: JSON.stringify({ action: actionKey, map, confirm }),
  });
  state.selectedJob = job.id;
  $("#jobOutput").textContent = job.output || `Queued ${job.label}...`;
  startPolling();
  await refreshJobs();
}

function isImportedMap(mapKey) {
  const map = state.maps.find((item) => item.key === mapKey);
  return Boolean(map?.isImported);
}

async function refreshJobs() {
  const jobs = await api("/api/jobs");
  renderJobs(jobs);
  if (state.selectedJob) await showJob(state.selectedJob, false);
}

async function showJob(jobId, mark = true) {
  const job = await api(`/api/jobs/${jobId}`);
  if (mark) state.selectedJob = jobId;
  $("#jobOutput").textContent = job.output || `${job.label}: ${job.status}`;
  const jobs = await api("/api/jobs");
  renderJobs(jobs);
  if (["queued", "running"].includes(job.status)) startPolling();
}

function startPolling() {
  if (state.pollTimer) return;
  state.pollTimer = setInterval(async () => {
    try {
      await refreshJobs();
      const jobs = await api("/api/jobs");
      const active = jobs.some((job) => ["queued", "running"].includes(job.status));
      if (!active) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
        await refreshAll();
      }
    } catch (error) {
      console.error(error);
    }
  }, 1800);
}

async function loadLog() {
  const map = state.selectedMap;
  if (!map) return;
  const data = await api(`/api/logs?map=${encodeURIComponent(map)}&lines=220`);
  const header = data.file ? `# ${data.file}\n` : "# No log found\n";
  $("#logOutput").textContent = header + data.lines.join("\n");
}

function selectMap(key, switchTab = false) {
  state.selectedMap = key;
  $("#mapSelect").value = key;
  renderMapDetail();
  if (switchTab) activateTab("map");
  loadLog().catch((error) => ($("#logOutput").textContent = error.message));
}

function activateTab(name) {
  $$(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === name));
}

function bindEvents() {
  $$(".tab").forEach((tab) => tab.addEventListener("click", () => activateTab(tab.dataset.tab)));
  $("#refreshButton").addEventListener("click", () => refreshAll().catch(showError));
  $("#openValidationButton").addEventListener("click", () => runAction("validate_public_repo"));
  $("#mapSelect").addEventListener("change", (event) => selectMap(event.target.value));
  $("#loadLogButton").addEventListener("click", () => loadLog().catch(showError));
  $("#clearOutputButton").addEventListener("click", () => ($("#jobOutput").textContent = ""));
  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const source = button.dataset.mapSource;
    const map = source === "all" ? "all" : source === "selected" ? state.selectedMap : undefined;
    runAction(button.dataset.action, map).catch(showError);
  });
}

function showError(error) {
  $("#jobOutput").textContent = `ERROR: ${error.message || error}`;
}

async function init() {
  bindEvents();
  await refreshAll();
  await loadLog().catch(() => {});
}

init().catch(showError);
