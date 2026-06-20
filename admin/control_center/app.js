const state = {
  app: null,
  maps: [],
  status: null,
  actions: [],
  balance: null,
  setup: null,
  troubleshooting: null,
  events: null,
  eventsMap: null,
  missions: null,
  missionsMap: null,
  report: null,
  reportScope: "all",
  snapshots: null,
  schedules: null,
  watchdog: null,
  updates: null,
  players: null,
  killfeed: null,
  playersMap: null,
  rcon: null,
  rconMap: null,
  selectedMap: null,
  selectedJob: null,
  pendingSave: null,
  pollTimer: null,
  statusTimer: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const ACTION_HELP = {
  status_all: {
    when: "Use for a quick across-the-board health snapshot.",
    result: "Shows AI, loot, event, port, and imported-map safety summaries.",
  },
  check_map_launch: {
    when: "Use after adding maps, changing mod folders, or editing launch config.",
    result: "Confirms configs, missions, mod folders, and expected ports.",
  },
  check_admin_tooling: {
    when: "Use when VPP hotkeys, profiles, or desktop launchers feel wrong.",
    result: "Checks VPP files, input presets, client profiles, and launch helpers.",
  },
  validate_public_repo: {
    when: "Use before committing, pushing, or sharing the repo.",
    result: "Confirms tracked files are public-safe and parse cleanly.",
  },
  validate_imported_maps: {
    when: "Use after repairing or importing community maps.",
    result: "Confirms imported maps are not carrying risky generated content.",
  },
  triage_logs: {
    when: "Use when a map boots strangely or players report a broken server.",
    result: "Highlights likely blockers and separates common harmless warnings.",
  },
  config_drift: {
    when: "Use when launcher files, ports, or config names seem mismatched.",
    result: "Compares launch config, real configs, examples, and helpers.",
  },
  lan_visibility_check: {
    when: "Use when direct connect works but the launcher is confusing.",
    result: "Checks active ports, Steam query, firewall hints, and A2S responses.",
  },
  snapshot_configs: {
    when: "Use before any manual edit or larger generated refresh.",
    result: "Creates a private backup zip under admin/backups.",
  },
  apply_loot_current: {
    when: "Use after selecting a loot preset or changing loot config.",
    result: "Regenerates and applies loot files from the active preset.",
  },
  smoke_test_map: {
    when: "Use after changes to prove a map reaches ready state.",
    result: "Starts one map, waits for readiness, queries it, and stops only what it started.",
  },
  sync_vpp_profiles: {
    when: "Use after switching admin tooling or adding a new map profile.",
    result: "Copies VPP profile files where each map expects them.",
  },
  repair_vpp_inputs: {
    when: "Use when VPP hotkeys do not respond in-game.",
    result: "Repairs known VPP input preset locations.",
  },
  sync_desktop_launchers: {
    when: "Use after launch config or map list changes.",
    result: "Updates desktop start scripts from the shared launch configuration.",
  },
  stop_dayz_servers: {
    when: "Use only when you intentionally want all DayZ server processes stopped.",
    result: "Stops DayZ server processes after typed confirmation.",
  },
  wipe_imported_storage: {
    when: "Use only when imported-map persistence is broken or poisoned by bad generated content.",
    result: "Wipes imported-map storage after typed confirmation.",
  },
  recover_imported_map: {
    when: "Use when an imported map is stuck on boot or out-of-bounds generated content keeps returning.",
    result: "Runs the guarded imported-map cleanup/recovery flow.",
  },
  full_generation_refresh: {
    when: "Use only when you want to rebuild the generated gameplay config set.",
    result: "Runs the full generation pipeline and validations after typed confirmation.",
  },
};

const RISK_COPY = {
  read: "Read-only. Safe while servers are running.",
  guarded: "Can write files or start a controlled test. Snapshot is used where appropriate.",
  high: "Power tool. Requires typed confirmation and may stop servers, wipe storage, or rewrite generated files.",
};

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
  return `<span class="${cls}" title="${escapeText(good ? "Healthy" : badWhenFalse ? "Needs attention" : "Not active or not applicable")}">${label}</span>`;
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
  const [app, maps, status, actions, balance, setup, troubleshooting, jobs] = await Promise.all([
    api("/api/app"),
    api("/api/maps"),
    api("/api/status"),
    api("/api/actions"),
    api("/api/balance"),
    api("/api/setup"),
    api("/api/troubleshooting"),
    api("/api/jobs"),
  ]);
  state.app = app;
  state.maps = maps;
  state.status = status;
  state.actions = actions;
  state.balance = balance;
  state.setup = setup;
  state.troubleshooting = troubleshooting;
  if (!state.selectedMap && maps.length) state.selectedMap = maps[0].key;
  $("#rootPath").textContent = status.root;
  renderAppInfo();
  renderMaps();
  renderMapSelect();
  renderMapDetail();
  renderBalance();
  renderActions();
  renderSetup();
  renderTroubleshooting();
  renderJobs(jobs);
}

function renderAppInfo() {
  if (!state.app) return;
  const pill = $("#appVersion");
  if (pill) {
    pill.textContent = `v${state.app.version}${state.app.channel ? ` ${state.app.channel}` : ""}`;
  }
  const link = $("#releaseLink");
  if (link) {
    const url = state.app.latestReleaseUrl || state.app.releasesUrl;
    if (url) {
      link.href = url;
      link.hidden = false;
    } else {
      link.hidden = true;
    }
  }
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
    card.title = "Open map detail and latest log tools.";
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
      <p class="card-help">${mapCardHelp(map, status)}</p>
    `;
    grid.appendChild(card);
  }
}

function mapCardHelp(map, status) {
  if (!map.configExists) return "Private config is missing. Open Setup Helper before launch.";
  if (!map.missionExists) return "Mission folder is missing. Fix mission files before smoke testing.";
  if (map.missingMods.length) return "Some Workshop/mod folders are missing from the server root.";
  if (status.queryActive) return "Query port is active, so this map is currently discoverable by A2S/direct checks.";
  if (status.log?.ready) return "Latest log reached ready state. Start the map if you need active ports.";
  return "Looks configured. Start or smoke test it to confirm runtime health.";
}

function renderMapSelect() {
  const select = $("#mapSelect");
  const troubleshootSelect = $("#troubleshootMapSelect");
  const eventsSelect = $("#eventsMapSelect");
  const missionSelect = $("#missionMapSelect");
  const reportSelect = $("#reportMapSelect");
  const rconSelect = $("#rconMapSelect");
  const playersSelect = $("#playersMapSelect");
  select.innerHTML = "";
  if (troubleshootSelect) troubleshootSelect.innerHTML = "";
  if (eventsSelect) eventsSelect.innerHTML = "";
  if (missionSelect) missionSelect.innerHTML = "";
  if (rconSelect) rconSelect.innerHTML = "";
  if (playersSelect) playersSelect.innerHTML = "";
  if (reportSelect) {
    reportSelect.innerHTML = "";
    const all = document.createElement("option");
    all.value = "all";
    all.textContent = "All maps";
    if ((state.reportScope || "all") === "all") all.selected = true;
    reportSelect.appendChild(all);
  }
  for (const target of [$("#zombieTargetSelect"), $("#aiTargetSelect")]) {
    target.innerHTML = "";
    const all = document.createElement("option");
    all.value = "all";
    all.textContent = "All maps";
    target.appendChild(all);
  }
  for (const map of state.maps) {
    const option = document.createElement("option");
    option.value = map.key;
    option.textContent = map.title;
    if (map.key === state.selectedMap) option.selected = true;
    select.appendChild(option);
    if (troubleshootSelect) troubleshootSelect.appendChild(option.cloneNode(true));
    if (eventsSelect) {
      const eventsOption = option.cloneNode(true);
      if (map.key === (state.eventsMap || state.selectedMap)) eventsOption.selected = true;
      eventsSelect.appendChild(eventsOption);
    }
    if (missionSelect) {
      const missionOption = option.cloneNode(true);
      if (map.key === (state.missionsMap || state.selectedMap)) missionOption.selected = true;
      missionSelect.appendChild(missionOption);
    }
    if (reportSelect) {
      const reportOption = option.cloneNode(true);
      reportOption.selected = map.key === state.reportScope;
      reportSelect.appendChild(reportOption);
    }
    if (rconSelect) {
      const rconOption = option.cloneNode(true);
      if (map.key === (state.rconMap || state.selectedMap)) rconOption.selected = true;
      rconSelect.appendChild(rconOption);
    }
    if (playersSelect) {
      const playersOption = option.cloneNode(true);
      if (map.key === (state.playersMap || state.selectedMap)) playersOption.selected = true;
      playersSelect.appendChild(playersOption);
    }
    for (const target of [$("#zombieTargetSelect"), $("#aiTargetSelect")]) {
      const targetOption = option.cloneNode(true);
      target.appendChild(targetOption);
    }
  }
}

function renderMapDetail() {
  const map = state.maps.find((item) => item.key === state.selectedMap);
  if (!map) return;
  const status = mapStatus(map.key);
  renderMapAdvice(map, status);
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

function renderMapAdvice(map, status) {
  const advice = [];
  if (!map.configExists) advice.push("Private server config is missing. Create or copy the local serverDZ config before launching.");
  if (!map.missionExists) advice.push("Mission folder is missing. Fix this before running a smoke test.");
  if (map.missingMods.length) advice.push(`${map.missingMods.length} listed mod folder(s) are missing. Sync Workshop/server mods first.`);
  if (status.queryActive) advice.push("Query port is active. Direct-connect and A2S checks should work for this running map.");
  if (!status.queryActive && status.gameActive) advice.push("Game port is active but query is not. Run LAN Check and Triage Logs.");
  if (!status.gameActive && !status.queryActive) advice.push("This map is not running right now. Smoke Test is the safest launch validation.");
  if (map.isImported) advice.push("Imported map: avoid heavy generated placements. Use Recover Imported only when boot stability is broken.");
  if (!advice.length) advice.push("No obvious issues from static checks. Run diagnostics if something feels wrong.");
  $("#mapAdvice").innerHTML = `<strong>Recommended next step:</strong> ${advice.map(escapeText).join(" ")}`;
}

function actionScopeCopy(action) {
  if (action.mapMode === "none") return "No map selection needed.";
  if (action.mapMode === "one") return "Runs on the selected map only.";
  if (action.mapMode === "all") return "Can run on all maps or the selected map depending on the button.";
  if (action.mapMode === "imported") return "Imported maps only, or all imported maps where supported.";
  return "";
}

function actionButton(action) {
  const danger = action.risk === "high" ? " danger" : "";
  const help = ACTION_HELP[action.key] || {};
  const riskHelp = RISK_COPY[action.risk] || action.risk;
  const buttonTip = `${help.when || action.description} ${action.confirm ? `Requires typing ${action.confirm}.` : ""}`.trim();
  const advanced = action.risk === "high" ? " data-advanced" : "";
  return `
    <article class="action-card"${advanced}>
      <h3>${escapeText(action.label)} <span class="help-tip" tabindex="0" data-tip="${escapeText(riskHelp)}">?</span></h3>
      <p>${escapeText(action.description)}</p>
      <dl class="action-help">
        <dt>Use when</dt><dd>${escapeText(help.when || "You need this specific maintenance operation.")}</dd>
        <dt>Result</dt><dd>${escapeText(help.result || "Output will appear in the Jobs panel.")}</dd>
        <dt>Scope</dt><dd>${escapeText(actionScopeCopy(action))}</dd>
      </dl>
      <footer>
        <span class="pill ${action.risk === "high" ? "bad" : action.risk === "guarded" ? "warning" : ""}" title="${escapeText(riskHelp)}">${action.risk}</span>
        <button class="${danger}" data-action="${action.key}" data-map-source="${action.mapMode === "none" ? "" : "selected"}" type="button" data-tip="${escapeText(buttonTip)}">Run</button>
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

const SETUP_STATUS_COPY = {
  ok: { label: "Ready", cls: "pill ok" },
  warn: { label: "Attention", cls: "pill warning" },
  todo: { label: "Action needed", cls: "pill bad" },
  action: { label: "Recommended", cls: "pill" },
  done: { label: "Done", cls: "pill ok" },
};

function setupStepNumber(index) {
  return index + 1;
}

function renderSetup() {
  const setup = state.setup;
  const wizard = $("#setupWizard");
  if (!setup || !wizard) return;

  const pill = $("#setupReadyPill");
  if (pill) {
    if (setup.ready) {
      pill.textContent = "Core requirements met";
      pill.className = "pill ok";
    } else {
      pill.textContent = "Needs attention";
      pill.className = "pill bad";
    }
  }

  const nextBanner = $("#setupNext");
  if (nextBanner) {
    if (setup.recommendedNext) {
      const step = setup.steps.find((item) => item.key === setup.recommendedNext);
      const number = setup.steps.indexOf(step) + 1;
      nextBanner.innerHTML = `<strong>Next step ${number}:</strong> ${escapeText(step.title)} — ${escapeText(step.detail)}`;
      nextBanner.classList.remove("ok");
    } else {
      nextBanner.innerHTML = `
        <strong>✅ You're ready.</strong> Every core requirement is satisfied and your server folder
        is set up correctly. You can run your maps now.
        <div class="status-row">
          <button data-tab-target="dashboard" type="button" data-tip="See all maps, ports, and latest log status.">Open Dashboard</button>
          <button data-tab-target="map" type="button" class="ghost" data-tip="Validate one map by starting it, checking it, and stopping it.">Smoke Test A Map</button>
        </div>`;
      nextBanner.classList.add("ok");
    }
  }

  wizard.innerHTML = setup.steps
    .map((step, index) => {
      const effectiveStatus = step.done && step.status === "action" ? "done" : step.status;
      const badge = SETUP_STATUS_COPY[effectiveStatus] || SETUP_STATUS_COPY.action;
      const isNext = step.key === setup.recommendedNext;
      const items = (step.items || []).filter(Boolean);
      const itemsHtml = items.length
        ? `<ul class="wizard-items">${items.map((item) => `<li>${escapeText(item)}</li>`).join("")}</ul>`
        : "";
      const fixAction = step.fixAction
        ? state.actions.find((action) => action.key === step.fixAction)
        : null;
      const fixSource = fixAction && fixAction.mapMode !== "none" ? "all" : "";
      const fixButton = fixAction
        ? `<button data-action="${escapeText(fixAction.key)}" data-map-source="${fixSource}" type="button" data-tip="${escapeText(fixAction.description)}">${step.status === "action" ? "Run check" : "Fix this"}</button>`
        : "";
      const doneToggle =
        step.status === "action" || step.status === "ok"
          ? `<button class="ghost" data-setup-step="${escapeText(step.key)}" data-setup-done="${step.done ? "false" : "true"}" type="button" data-tip="Mark this step done on this computer only.">${step.done ? "Mark not done" : "Mark done"}</button>`
          : "";
      return `
        <li class="wizard-step ${effectiveStatus} ${isNext ? "is-next" : ""}">
          <div class="wizard-head">
            <span class="step-number">${setupStepNumber(index)}</span>
            <h3>${escapeText(step.title)}</h3>
            <span class="${badge.cls}">${badge.label}</span>
          </div>
          <p class="wizard-summary">${escapeText(step.summary)}</p>
          <p class="card-help">${escapeText(step.detail)}</p>
          ${itemsHtml}
          <div class="action-row wizard-actions">
            ${fixButton}
            ${doneToggle}
          </div>
        </li>
      `;
    })
    .join("");
}

async function saveSetupStep(step, done) {
  const setup = await api("/api/setup/save", {
    method: "POST",
    body: JSON.stringify({ step, done }),
  });
  state.setup = setup;
  renderSetup();
}

const TIER_BY_RISK = {
  read: { label: "Safe check", cls: "pill" },
  guarded: { label: "Guarded repair", cls: "pill warning" },
  high: { label: "High risk", cls: "pill bad" },
};

const TAB_LABELS = {
  balance: "Balance editor",
  maintenance: "Maintenance",
  dashboard: "Dashboard",
  map: "Map detail",
  setup: "Setup",
};

function troubleshootStep(step, index) {
  const number = index + 1;
  if (step.kind === "tab") {
    const label = TAB_LABELS[step.tab] || "Open tab";
    return `
      <li class="fix-step">
        <span class="step-number">${number}</span>
        <div class="fix-step-body">
          <div class="fix-step-head"><span class="pill ok">Editor</span></div>
          <p class="card-help">${escapeText(step.note)}</p>
          <div class="action-row">
            <button class="ghost" data-tab-target="${escapeText(step.tab)}" type="button">Go to ${escapeText(label)}</button>
          </div>
        </div>
      </li>
    `;
  }
  const tier = TIER_BY_RISK[step.risk] || TIER_BY_RISK.read;
  const danger = step.risk === "high" ? " danger" : "";
  const source = step.mapMode === "none" ? "" : "troubleshoot";
  const confirmNote = step.confirm ? ` Requires typing ${step.confirm}.` : "";
  return `
    <li class="fix-step">
      <span class="step-number">${number}</span>
      <div class="fix-step-body">
        <div class="fix-step-head">
          <strong>${escapeText(step.label)}</strong>
          <span class="${tier.cls}">${tier.label}</span>
        </div>
        <p class="card-help">${escapeText(step.note)}${escapeText(confirmNote)}</p>
        <div class="action-row">
          <button class="${danger}" data-action="${escapeText(step.action)}" data-map-source="${source}" type="button">Run ${escapeText(step.label)}</button>
        </div>
      </div>
    </li>
  `;
}

function renderTroubleshooting() {
  const list = $("#troubleshootingList");
  if (!list || !state.troubleshooting) return;
  list.innerHTML = state.troubleshooting.symptoms
    .map(
      (symptom) => `
      <details class="fix-card">
        <summary>${escapeText(symptom.title)}</summary>
        <p class="card-help fix-explain">${escapeText(symptom.explanation)}</p>
        <ol class="fix-steps">
          ${symptom.steps.map(troubleshootStep).join("")}
        </ol>
      </details>
    `
    )
    .join("");
}

function balanceMap(key = state.selectedMap) {
  return state.balance?.maps?.find((item) => item.key === key);
}

function setInput(selector, value) {
  const node = $(selector);
  if (node) node.value = value ?? "";
}

function numericValue(selector) {
  const value = $(selector).value;
  return value === "" ? undefined : Number(value);
}

function renderBalance() {
  if (!state.balance) return;
  const presetSelect = $("#lootPresetSelect");
  const currentPreset = state.balance.loot.activePreset;
  presetSelect.innerHTML = "";
  for (const [name, preset] of Object.entries(state.balance.loot.presets || {})) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = `${name} - ${preset.description || ""}`;
    if (name === currentPreset) option.selected = true;
    presetSelect.appendChild(option);
  }
  renderLootPresetInfo();
  fillBalanceFromSelectedMap();
}

function renderLootPresetInfo() {
  const presetName = $("#lootPresetSelect").value || state.balance?.loot?.activePreset;
  const preset = state.balance?.loot?.presets?.[presetName] || {};
  $("#lootPresetDescription").textContent = preset.description || "";
  const globals = preset.globals || {};
  $("#lootPresetStats").innerHTML = `
    <dt>Nominal mult</dt><dd>${escapeText(preset.nominal_mult ?? "?")}</dd>
    <dt>Min mult</dt><dd>${escapeText(preset.min_mult ?? "?")}</dd>
    <dt>Zombie max</dt><dd>${escapeText(globals.ZombieMaxCount ?? "?")}</dd>
    <dt>Spawn initial</dt><dd>${escapeText(globals.SpawnInitial ?? "?")}</dd>
  `;
}

function fillBalanceFromSelectedMap() {
  const item = balanceMap();
  if (!item) return;
  $("#zombieTargetSelect").value = state.selectedMap;
  $("#aiTargetSelect").value = state.selectedMap;
  setInput("#zombieMaxInput", item.loot.ZombieMaxCount);
  setInput("#animalMaxInput", item.loot.AnimalMaxCount);
  setInput("#spawnInitialInput", item.loot.SpawnInitial);
  setInput("#initialSpawnInput", item.loot.InitialSpawn);
  setInput("#respawnLimitInput", item.loot.RespawnLimit);
  setInput("#respawnTypesInput", item.loot.RespawnTypes);
  setInput("#aiPatrolMaxInput", item.ai.patrolMax);
  setInput("#aiGlobalMaxInput", item.ai.globalMax);
  setInput("#aiObjectMaxInput", item.ai.objectPatrolMax);
  setInput("#aiHeliMaxInput", item.ai.heliPatrolMax);
  setInput("#aiMinInput", item.ai.minAI);
  setInput("#aiMaxInput", item.ai.maxAI);
  setInput("#aiAccuracyMinInput", item.ai.accuracyMin);
  setInput("#aiAccuracyMaxInput", item.ai.accuracyMax);
  setInput("#aiDamageInput", item.ai.damageMultiplier);
  renderBalanceSummary(item);
}

function renderBalanceSummary(item) {
  $("#balanceSummary").innerHTML = `
    <dl class="kv">
      <dt>Map</dt><dd>${escapeText(item.title)}</dd>
      <dt>Mission</dt><dd>${escapeText(item.mission)}</dd>
      <dt>AI patrols</dt><dd>${escapeText(item.ai.patrols ?? "missing")}</dd>
      <dt>Patrol cap</dt><dd>${escapeText(item.ai.patrolMax ?? "?")}</dd>
      <dt>Global cap</dt><dd>${escapeText(item.ai.globalMax ?? "?")}</dd>
      <dt>AI/group</dt><dd>${escapeText(item.ai.minAI ?? "varied")} - ${escapeText(item.ai.maxAI ?? "varied")}</dd>
      <dt>Accuracy</dt><dd>${escapeText(item.ai.accuracyMin ?? "?")} - ${escapeText(item.ai.accuracyMax ?? "?")}</dd>
      <dt>Zombies</dt><dd>${escapeText(item.loot.ZombieMaxCount ?? "?")}</dd>
      <dt>Animals</dt><dd>${escapeText(item.loot.AnimalMaxCount ?? "?")}</dd>
    </dl>
    <p class="card-help">${balanceAdvice(item)}</p>
  `;
}

function balanceAdvice(item) {
  const notes = [];
  if (Number(item.loot.ZombieMaxCount || 0) > 1500) notes.push("High zombie caps can increase placement warnings and CPU pressure.");
  if (Number(item.ai.patrolMax || 0) > 32) notes.push("AI patrol cap is above the current medium baseline.");
  if (Number(item.ai.accuracyMax || 0) > 0.75) notes.push("Accuracy max is leaning hard; expect sharper AI.");
  if (!notes.length) notes.push("Current values look close to the intended medium PvE-friendly baseline.");
  return notes.join(" ");
}

async function previewThenSave({ previewUrl, saveUrl, payload, label, onSaved }) {
  const preview = await api(previewUrl, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!preview.hasChanges) {
    $("#jobOutput").textContent = `${label}: no changes needed. Current values already match what you entered.`;
    return;
  }
  state.pendingSave = { saveUrl, payload, label, onSaved };
  showPreview(preview, label);
}

async function onBalanceSaved(result, label) {
  state.balance = result.balance;
  $("#jobOutput").textContent = `${label} saved.\n\nChanged:\n${result.changed.length ? result.changed.join("\n") : "No file changes needed."}\n\nRestart affected servers for AI/zombie changes. Apply loot separately if you changed loot preset.`;
  await refreshAll();
}

function showPreview(preview, label) {
  const lines = [];
  lines.push(`<p class="preview-label">${escapeText(label)}</p>`);
  lines.push("<h3>Files that will change</h3>");
  lines.push(`<ul class="preview-list">${preview.files.map((file) => `<li>${escapeText(file)}</li>`).join("")}</ul>`);
  if (preview.maps.length) {
    lines.push(`<p><strong>Maps affected:</strong> ${preview.maps.map(escapeText).join(", ")}</p>`);
  }
  lines.push("<h3>What happens</h3>");
  lines.push(`<ul class="preview-list">${preview.changes.map((change) => `<li>${escapeText(change)}</li>`).join("")}</ul>`);
  const notes = [];
  if (preview.snapshot) notes.push(`A config snapshot is created first (label: ${escapeText(preview.snapshotLabel)}).`);
  notes.push(preview.restartRequired ? "Restart the affected map(s) for these changes to take effect." : "No server restart required.");
  if (preview.needsLootApply) notes.push("Loot preset changes also need Apply Loot Now to regenerate loot files.");
  lines.push(`<div class="notice preview-notes">${notes.map((note) => `<p>${escapeText(note)}</p>`).join("")}</div>`);
  $("#previewBody").innerHTML = lines.join("");
  $("#previewTitle").textContent = "Preview changes before saving";
  $("#previewConfirmButton").textContent = "Snapshot & Save";
  $("#previewOverlay").classList.remove("hidden");
}

function hidePreview() {
  $("#previewOverlay").classList.add("hidden");
  state.pendingSave = null;
}

async function confirmPreview() {
  const pending = state.pendingSave;
  if (!pending) return;
  $("#previewOverlay").classList.add("hidden");
  state.pendingSave = null;
  const result = await api(pending.saveUrl, {
    method: "POST",
    body: JSON.stringify(pending.payload),
  });
  if (pending.onSaved) await pending.onSaved(result, pending.label);
}

async function saveLootPreset() {
  await previewThenSave({
    previewUrl: "/api/balance/preview",
    saveUrl: "/api/balance/save",
    payload: { lootPreset: $("#lootPresetSelect").value },
    label: "Loot preset",
    onSaved: onBalanceSaved,
  });
}

async function saveZombies() {
  const values = {
    maps: $("#zombieTargetSelect").value,
    ZombieMaxCount: numericValue("#zombieMaxInput"),
    AnimalMaxCount: numericValue("#animalMaxInput"),
    SpawnInitial: numericValue("#spawnInitialInput"),
    InitialSpawn: numericValue("#initialSpawnInput"),
    RespawnLimit: numericValue("#respawnLimitInput"),
    RespawnTypes: numericValue("#respawnTypesInput"),
  };
  Object.keys(values).forEach((key) => values[key] === undefined && delete values[key]);
  await previewThenSave({
    previewUrl: "/api/balance/preview",
    saveUrl: "/api/balance/save",
    payload: { zombies: values },
    label: "Zombie/spawn settings",
    onSaved: onBalanceSaved,
  });
}

async function saveAi() {
  const values = {
    maps: $("#aiTargetSelect").value,
    patrolMax: numericValue("#aiPatrolMaxInput"),
    globalMax: numericValue("#aiGlobalMaxInput"),
    objectPatrolMax: numericValue("#aiObjectMaxInput"),
    heliPatrolMax: numericValue("#aiHeliMaxInput"),
    minAI: numericValue("#aiMinInput"),
    maxAI: numericValue("#aiMaxInput"),
    accuracyMin: numericValue("#aiAccuracyMinInput"),
    accuracyMax: numericValue("#aiAccuracyMaxInput"),
    damageMultiplier: numericValue("#aiDamageInput"),
  };
  Object.keys(values).forEach((key) => values[key] === undefined && delete values[key]);
  await previewThenSave({
    previewUrl: "/api/balance/preview",
    saveUrl: "/api/balance/save",
    payload: { ai: values },
    label: "AI settings",
    onSaved: onBalanceSaved,
  });
}

const AI_DIFFICULTY_PRESETS = {
  easy: { patrolMax: 12, globalMax: 24, objectPatrolMax: 6, heliPatrolMax: 4, minAI: 2, maxAI: 3, accuracyMin: 0.25, accuracyMax: 0.45, damageMultiplier: 1.0 },
  medium: { patrolMax: 24, globalMax: 40, objectPatrolMax: 10, heliPatrolMax: 6, minAI: 2, maxAI: 4, accuracyMin: 0.4, accuracyMax: 0.6, damageMultiplier: 1.1 },
  hard: { patrolMax: 40, globalMax: 64, objectPatrolMax: 14, heliPatrolMax: 8, minAI: 3, maxAI: 6, accuracyMin: 0.55, accuracyMax: 0.75, damageMultiplier: 1.4 },
};

function applyAiPreset(name) {
  const preset = AI_DIFFICULTY_PRESETS[name];
  if (!preset) return;
  setInput("#aiPatrolMaxInput", preset.patrolMax);
  setInput("#aiGlobalMaxInput", preset.globalMax);
  setInput("#aiObjectMaxInput", preset.objectPatrolMax);
  setInput("#aiHeliMaxInput", preset.heliPatrolMax);
  setInput("#aiMinInput", preset.minAI);
  setInput("#aiMaxInput", preset.maxAI);
  setInput("#aiAccuracyMinInput", preset.accuracyMin);
  setInput("#aiAccuracyMaxInput", preset.accuracyMax);
  setInput("#aiDamageInput", preset.damageMultiplier);
  $("#jobOutput").textContent = `Loaded "${name}" difficulty into the AI fields. Review, then Save AI Settings to preview and apply.`;
}

const EVENTS_CATEGORY_ORDER = ["vehicles", "heli", "airdrops", "static", "animals", "infected", "loot", "other"];
const EVENTS_DEFAULT_OPEN = new Set(["vehicles", "heli", "airdrops", "static"]);

async function loadEvents(map) {
  if (!map) return;
  const data = await api(`/api/events?map=${encodeURIComponent(map)}`);
  state.events = data;
  state.eventsMap = map;
  renderEvents();
}

function eventRow(ev) {
  const num = (field) =>
    `<input class="event-input" type="number" min="0" data-event-name="${escapeText(ev.name)}" data-event-field="${field}" value="${ev[field] ?? ""}">`;
  return `
    <div class="events-row">
      <span class="event-name">${escapeText(ev.name)}</span>
      <input type="checkbox" class="event-active" data-event-name="${escapeText(ev.name)}" data-event-field="active" ${ev.active ? "checked" : ""} aria-label="active">
      ${num("nominal")}${num("min")}${num("max")}${num("lifetime")}
    </div>
  `;
}

function renderEvents() {
  const editor = $("#eventsEditor");
  if (!editor) return;
  const data = state.events;
  if (!data) {
    editor.textContent = "Select a map to load its world events.";
    return;
  }
  if (!data.exists || !data.events.length) {
    editor.innerHTML = `<div class="notice">No db/events.xml found for ${escapeText(data.map)}.</div>`;
    return;
  }
  const labels = data.categoryLabels || {};
  const byCat = {};
  for (const ev of data.events) (byCat[ev.category] ||= []).push(ev);
  const cats = EVENTS_CATEGORY_ORDER.filter((cat) => byCat[cat]);
  editor.innerHTML = cats
    .map((cat) => {
      const open = EVENTS_DEFAULT_OPEN.has(cat) ? "open" : "";
      const rows = byCat[cat].map(eventRow).join("");
      return `
      <details class="events-group" ${open}>
        <summary>${escapeText(labels[cat] || cat)} <span class="muted">(${byCat[cat].length})</span></summary>
        <div class="events-table-head">
          <span>Event</span><span>On</span><span>Nominal</span><span>Min</span><span>Max</span><span>Lifetime</span>
        </div>
        ${rows}
      </details>`;
    })
    .join("");
}

function collectEventChanges() {
  const originals = {};
  for (const ev of state.events?.events || []) originals[ev.name] = ev;
  const changes = {};
  for (const input of $$("#eventsEditor [data-event-name]")) {
    const name = input.dataset.eventName;
    const field = input.dataset.eventField;
    const orig = originals[name];
    if (!orig) continue;
    let value;
    if (field === "active") {
      value = input.checked ? 1 : 0;
    } else {
      if (input.value === "") continue;
      value = Number(input.value);
    }
    const original = field === "active" ? (orig.active ? 1 : 0) : orig[field];
    if (value !== original) (changes[name] ||= {})[field] = value;
  }
  return changes;
}

async function saveEvents() {
  const map = $("#eventsMapSelect").value;
  if (!map) return;
  const changes = collectEventChanges();
  if (!Object.keys(changes).length) {
    $("#jobOutput").textContent = "No event changes to save.";
    return;
  }
  await previewThenSave({
    previewUrl: "/api/events/preview",
    saveUrl: "/api/events/save",
    payload: { map, events: changes },
    label: `Events (${map})`,
    onSaved: async (result) => {
      state.events = result.events;
      renderEvents();
      $("#jobOutput").textContent = `Events saved for ${map}.\n\nChanged:\n${result.changed.join("\n") || "none"}\n\nRestart ${map} for changes to take effect.`;
    },
  });
}

const OBJECTIVE_TYPE_LABELS = { 2: "infected clear", 7: "AI clear" };

async function loadMissions(map) {
  if (!map) return;
  const data = await api(`/api/missions?map=${encodeURIComponent(map)}`);
  state.missions = data;
  state.missionsMap = map;
  renderMissions();
}

function renderMissionTypes() {
  const data = state.missions;
  const select = $("#missionTypeSelect");
  if (!data || !select) return;
  if (!select.options.length) {
    select.innerHTML = data.types
      .map((type) => `<option value="${escapeText(type.key)}">${escapeText(type.label)}</option>`)
      .join("");
  }
  updateMissionTypeUi();
}

function updateMissionTypeUi() {
  const data = state.missions;
  if (!data) return;
  const typeKey = $("#missionTypeSelect").value;
  const type = data.types.find((item) => item.key === typeKey);
  $("#missionTypeHelp").textContent = type ? type.help : "";
  $("#missionAiFields").hidden = !(type && type.needsLocation);
}

function renderMissions() {
  const data = state.missions;
  if (!data) return;
  renderMissionTypes();
  $("#missionQuestsDir").textContent = `Installs into: ${data.questsDir} (next ID ${data.nextId})`;
  const warning = $("#missionBoardWarning");
  if (!data.boardNpcExists) {
    warning.hidden = false;
    warning.textContent =
      "No contract board NPC found for this map yet. Missions will install but players may not be able to accept them until a quest board exists (run Install Money Quests or add a board).";
  } else {
    warning.hidden = true;
  }
  const list = $("#missionList");
  if (!data.missions.length) {
    list.innerHTML = `<p class="muted">No Control Center missions on ${escapeText(data.map)} yet.</p>`;
    return;
  }
  list.innerHTML = data.missions.map(missionRow).join("");
}

function missionRow(mission) {
  const reward = (mission.rewards || [])[0] || {};
  const type = OBJECTIVE_TYPE_LABELS[mission.objectiveType] || `type ${mission.objectiveType}`;
  const rewardClass = reward.className ? ` - ${escapeText(reward.className)}` : "";
  return `
    <div class="mission-item" data-mission-id="${mission.id}">
      <div class="mission-head"><strong>#${mission.id} ${escapeText(mission.title)}</strong> <span class="muted">${escapeText(type)}${rewardClass}</span></div>
      <div class="form-grid">
        <label>Payout<input class="mission-payout" type="number" min="0" max="1000000" step="100" value="${reward.amount ?? 0}"></label>
        <label class="check-field"><input class="mission-active" type="checkbox" ${mission.active ? "checked" : ""}> Active</label>
        <label class="check-field"><input class="mission-repeatable" type="checkbox" ${mission.repeatable ? "checked" : ""}> Repeatable</label>
      </div>
      <div class="action-row">
        <button data-mission-action="save" data-mission-id="${mission.id}" type="button" data-tip="Preview and save payout/active/repeatable changes.">Save Changes</button>
        <button class="danger" data-mission-action="remove" data-mission-id="${mission.id}" type="button" data-tip="Delete this generated mission after typing REMOVE.">Remove</button>
      </div>
    </div>
  `;
}

async function saveMissionUpdate(id) {
  const row = document.querySelector(`.mission-item[data-mission-id="${id}"]`);
  if (!row) return;
  const payload = {
    map: state.missionsMap,
    id: Number(id),
    payout: Number(row.querySelector(".mission-payout").value || 0),
    active: row.querySelector(".mission-active").checked,
    repeatable: row.querySelector(".mission-repeatable").checked,
  };
  await previewThenSave({
    previewUrl: "/api/missions/update/preview",
    saveUrl: "/api/missions/update",
    payload,
    label: `Mission #${id}`,
    onSaved: async (result) => {
      state.missions = result.missions;
      renderMissions();
      $("#jobOutput").textContent = `Mission #${id} updated.\nChanged: ${result.changed.join(", ") || "none"}\nRestart ${state.missionsMap} for changes to take effect.`;
    },
  });
}

async function removeMission(id) {
  const confirmText = prompt(
    `Type REMOVE to delete mission #${id} on ${state.missionsMap}. A snapshot is created first, but the mission files are deleted.`
  );
  if (confirmText !== "REMOVE") return;
  const result = await api("/api/missions/remove", {
    method: "POST",
    body: JSON.stringify({ map: state.missionsMap, id: Number(id), confirm: "REMOVE" }),
  });
  state.missions = result.missions;
  renderMissions();
  $("#jobOutput").textContent = `Removed mission #${id}.\nDeleted:\n${result.removed.join("\n")}`;
}

function collectMissionForm() {
  const type = $("#missionTypeSelect").value;
  const payload = {
    map: $("#missionMapSelect").value,
    type,
    title: $("#missionTitleInput").value.trim(),
    description: $("#missionDescInput").value.trim(),
    objectiveText: $("#missionObjectiveInput").value.trim(),
    payout: Number($("#missionPayoutInput").value || 0),
    amount: Number($("#missionAmountInput").value || 1),
    repeatable: $("#missionRepeatableInput").checked,
  };
  if (type === "ai_clear") {
    payload.location = [
      Number($("#missionLocXInput").value || 0),
      Number($("#missionLocYInput").value || 0),
      Number($("#missionLocZInput").value || 0),
    ];
    payload.aiName = $("#missionAiNameInput").value.trim();
  }
  const itemClass = $("#missionItemClassInput").value.trim();
  if (itemClass) {
    payload.itemReward = { className: itemClass, amount: Number($("#missionItemAmountInput").value || 1) };
  }
  return payload;
}

async function previewMission() {
  const payload = collectMissionForm();
  if (!payload.title) {
    $("#jobOutput").textContent = "Mission title is required.";
    return;
  }
  const preview = await api("/api/missions/preview", { method: "POST", body: JSON.stringify(payload) });
  const lines = [];
  lines.push(`<p class="preview-label">${escapeText(payload.title)} (${escapeText(payload.map)}, Quest ${preview.questId})</p>`);
  if (!preview.boardNpcExists) {
    lines.push(
      `<div class="notice warning-note">No contract board NPC found for this map. The mission installs but may be unreachable until a quest board exists.</div>`
    );
  }
  lines.push("<h3>Summary</h3>");
  lines.push(`<ul class="preview-list">${preview.summary.map((item) => `<li>${escapeText(item)}</li>`).join("")}</ul>`);
  lines.push("<h3>Files that will be created</h3>");
  lines.push(
    `<ul class="preview-list">${preview.files
      .map((file) => `<li>${escapeText(file.path)}${file.exists ? " (exists - blocked)" : ""}</li>`)
      .join("")}</ul>`
  );
  lines.push(
    `<div class="notice preview-notes"><p>A snapshot is created first (label: ${escapeText(preview.snapshotLabel)}).</p><p>Restart ${escapeText(payload.map)} for the new mission to load.</p></div>`
  );
  $("#previewBody").innerHTML = lines.join("");
  $("#previewTitle").textContent = "Preview mission before creating";
  $("#previewConfirmButton").textContent = "Create Mission";
  state.pendingSave = {
    saveUrl: "/api/missions/install",
    payload,
    label: `Mission "${payload.title}"`,
    onSaved: async (result) => {
      $("#jobOutput").textContent = `Mission created on ${result.map} (Quest ${result.questId}).\n\nFiles:\n${result.written.join("\n")}\n\nRestart ${result.map} to load it.`;
      await loadMissions(result.map);
    },
  };
  $("#previewOverlay").classList.remove("hidden");
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
    confirm = prompt(`${RISK_COPY[action.risk] || "Confirmation required."}\n\nType ${action.confirm} to run: ${action.label}`) || "";
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

async function refreshStatus() {
  const status = await api("/api/status");
  state.status = status;
  renderMaps();
}

function startStatusPolling() {
  if (state.statusTimer) return;
  state.statusTimer = setInterval(() => {
    refreshStatus().catch((error) => console.error(error));
  }, 6000);
}

function stopStatusPolling() {
  if (!state.statusTimer) return;
  clearInterval(state.statusTimer);
  state.statusTimer = null;
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
  fillBalanceFromSelectedMap();
  if (switchTab) activateTab("map");
  loadLog().catch((error) => ($("#logOutput").textContent = error.message));
}

function activateTab(name) {
  $$(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === name));
  if (name === "events") {
    const map = $("#eventsMapSelect")?.value || state.selectedMap;
    if (map && state.eventsMap !== map) loadEvents(map).catch(showError);
  }
  if (name === "missions") {
    const map = $("#missionMapSelect")?.value || state.selectedMap;
    if (map && state.missionsMap !== map) loadMissions(map).catch(showError);
  }
  if (name === "backups" && !state.snapshots) loadSnapshots().catch(showError);
  if (name === "rcon") loadRconStatus().catch(showError);
  if (name === "players") loadPlayers().catch(showError);
  if (name === "schedules") {
    loadWatchdog().catch(showError);
    loadSchedules().catch(showError);
  }
  if (name === "updates") loadUpdatesStatus().catch(showError);
  if (name === "dashboard") {
    refreshStatus().catch((error) => console.error(error));
    startStatusPolling();
  } else {
    stopStatusPolling();
  }
}

async function copyOutput() {
  const text = $("#jobOutput").textContent || "";
  if (!text.trim()) return;
  await navigator.clipboard.writeText(text);
  const button = $("#copyOutputButton");
  const original = button.textContent;
  button.textContent = "Copied";
  setTimeout(() => {
    button.textContent = original;
  }, 1200);
}

async function loadReport(scope) {
  const target = scope || $("#reportMapSelect")?.value || "all";
  state.reportScope = target;
  const output = $("#reportOutput");
  output.textContent = "Generating report...";
  $("#copyReportButton").disabled = true;
  $("#downloadReportButton").disabled = true;
  const data = await api(`/api/report?map=${encodeURIComponent(target)}`);
  state.report = data;
  output.textContent = data.text;
  $("#copyReportButton").disabled = false;
  $("#downloadReportButton").disabled = false;
}

async function copyReport() {
  if (!state.report || !state.report.text) return;
  await navigator.clipboard.writeText(state.report.text);
  const button = $("#copyReportButton");
  const original = button.textContent;
  button.textContent = "Copied";
  setTimeout(() => {
    button.textContent = original;
  }, 1200);
}

function downloadReport() {
  if (!state.report || !state.report.text) return;
  const scope = state.report.scope || "all";
  const stamp = (state.report.generatedAt || "").replace(/[^0-9]/g, "").slice(0, 14) || "latest";
  const blob = new Blob([state.report.text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `dayz-control-center-report-${scope}-${stamp}.txt`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function loadSnapshots() {
  const data = await api("/api/snapshots");
  state.snapshots = data;
  renderSnapshots();
}

function snapshotCard(snapshot) {
  const when = snapshot.created || snapshot.modified || "";
  const files = snapshot.files == null ? "?" : snapshot.files;
  return `
    <div class="mission-item">
      <div class="mission-head"><strong>${escapeText(snapshot.label || "config")}</strong> <span class="muted">${escapeText(when)}</span></div>
      <dl class="kv">
        <dt>File</dt><dd>${escapeText(snapshot.name)}</dd>
        <dt>Size</dt><dd>${snapshot.sizeKb} KB</dd>
        <dt>Files</dt><dd>${files}</dd>
      </dl>
      <div class="status-row">
        <button class="danger" data-advanced data-restore-snapshot="${escapeText(snapshot.name)}" type="button" data-tip="Overwrite current configs with this snapshot. Your current state is snapshotted first. Requires typing RESTORE.">Restore</button>
      </div>
    </div>`;
}

function renderSnapshots() {
  const container = $("#snapshotList");
  if (!container) return;
  const data = state.snapshots;
  if (!data || !data.snapshots.length) {
    container.innerHTML = `<p class="muted">No snapshots yet. Use Create Snapshot Now, or one is made automatically before guarded changes.</p>`;
    return;
  }
  container.innerHTML = `<p class="muted">${data.count} snapshot(s) in ${escapeText(data.dir)}. Newest first.</p>${data.snapshots.map(snapshotCard).join("")}`;
}

async function restoreSnapshot(name) {
  const confirmText = prompt(
    `Restore overwrites current configs with this snapshot:\n${name}\n\n` +
      "Your current state is snapshotted first, and you should restart affected maps afterward.\n\n" +
      "Type RESTORE to continue:"
  );
  if (confirmText !== "RESTORE") return;
  const job = await api("/api/actions/run", {
    method: "POST",
    body: JSON.stringify({ action: "restore_snapshot", snapshot: name, confirm: "RESTORE" }),
  });
  state.selectedJob = job.id;
  $("#jobOutput").textContent = job.output || `Queued restore of ${name}...`;
  startPolling();
  await refreshJobs();
}

function playersTargetMap() {
  return $("#playersMapSelect")?.value || state.playersMap || state.selectedMap;
}

function shortGuid(guid) {
  return guid ? `…${guid.slice(-6)}` : "";
}

function fmtPlaytime(minutes) {
  if (!minutes) return "0m";
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

async function loadPlayers(mapKey) {
  const map = mapKey || playersTargetMap();
  if (!map) return;
  state.playersMap = map;
  const [players, killfeed] = await Promise.all([
    api(`/api/players?map=${encodeURIComponent(map)}`),
    api(`/api/killfeed?map=${encodeURIComponent(map)}`),
  ]);
  state.players = players;
  state.killfeed = killfeed;
  renderPlayers();
}

function renderPlayers() {
  const players = state.players;
  const killfeed = state.killfeed;
  if (players) {
    $("#playersMeta").textContent = `${players.players.length} player(s) across ${players.filesScanned} log file(s)`;
    $("#playerList").innerHTML = players.players.length
      ? players.players
          .map(
            (p) => `
        <div class="mission-item">
          <div class="mission-head"><strong>${escapeText(p.name)}</strong> <span class="muted">${escapeText(shortGuid(p.guid))} · last seen ${escapeText(p.lastSeen || "?")}</span></div>
          <dl class="kv">
            <dt>Kills / Deaths</dt><dd>${p.kills} / ${p.deaths}</dd>
            <dt>Playtime</dt><dd>${escapeText(fmtPlaytime(p.playtimeMinutes))} over ${p.sessions} session(s)</dd>
          </dl>
          <label class="field">Note (private)<input type="text" data-note-guid="${escapeText(p.guid)}" maxlength="500" value="${escapeText(p.note || "")}" placeholder="e.g. friendly regular, or watch for cheating"></label>
          <button data-note-save="${escapeText(p.guid)}" type="button" data-tip="Save this note locally.">Save Note</button>
        </div>`
          )
          .join("")
      : `<p class="muted">No players found in the recent logs for this map.</p>`;
  }
  if (killfeed) {
    $("#killfeedList").innerHTML = killfeed.kills.length
      ? killfeed.kills
          .map((k) => {
            const dist = k.distance != null ? ` · ${k.distance}m` : "";
            const weapon = k.weapon ? ` (${escapeText(k.weapon)})` : "";
            const cls = k.killerType === "player" ? "bad" : k.killerType === "ai" ? "warning" : "";
            return `<div class="status-row"><span class="pill ${cls}">${escapeText(k.killerType)}</span> <span><strong>${escapeText(k.killer || "?")}</strong> → ${escapeText(k.victim)}${weapon}${dist} <span class="muted">${escapeText(k.at)}</span></span></div>`;
          })
          .join("")
      : `<p class="muted">No kills recorded in the recent logs.</p>`;
  }
}

async function savePlayerNote(guid) {
  const input = $(`[data-note-guid="${guid}"]`);
  if (!input) return;
  await api("/api/players/note", {
    method: "POST",
    body: JSON.stringify({ guid, note: input.value.trim() }),
  });
  const button = $(`[data-note-save="${guid}"]`);
  if (button) {
    const original = button.textContent;
    button.textContent = "Saved";
    setTimeout(() => {
      button.textContent = original;
    }, 1200);
  }
}

async function loadUpdatesStatus() {
  const data = await api("/api/updates/status");
  state.updates = data;
  renderUpdatesStatus();
}

function renderUpdatesStatus() {
  const data = state.updates;
  if (!data) return;
  const input = $("#steamUsernameInput");
  if (input && document.activeElement !== input) input.value = data.username || "";
  $("#updatesStatus").innerHTML =
    `<strong>SteamCMD:</strong> ${data.steamcmdFound ? `installed (${escapeText(data.steamcmdPath)})` : "not installed"}. ` +
    `<strong>Username:</strong> ${data.usernameSet ? escapeText(data.username) : "not set"}. ` +
    `<strong>Server app:</strong> ${escapeText(data.serverAppId)}, ${data.modCount} map mod(s). ${escapeText(data.note)}`;
}

async function saveSteamUsername() {
  const username = $("#steamUsernameInput").value.trim();
  const data = await api("/api/updates/settings", {
    method: "POST",
    body: JSON.stringify({ username }),
  });
  state.updates = data;
  renderUpdatesStatus();
}

function countdownText(nextRestart, now) {
  if (!nextRestart) return "off";
  const secs = Math.round(nextRestart - now);
  if (secs <= 0) return "due now";
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  return h > 0 ? `in ${h}h ${m}m` : `in ${m}m`;
}

async function loadSchedules() {
  const data = await api("/api/schedules");
  state.schedules = data;
  renderSchedules();
}

async function loadWatchdog() {
  const data = await api("/api/watchdog");
  state.watchdog = data;
  renderWatchdog();
}

function renderWatchdog() {
  const container = $("#watchdogList");
  if (!container || !state.watchdog) return;
  container.innerHTML = state.watchdog.maps
    .map((w) => {
      const status = w.paused
        ? `<span class="pill bad">paused</span>`
        : w.running
          ? `<span class="pill ok">running</span>`
          : `<span class="pill">stopped</span>`;
      const detail = w.paused
        ? `<span class="muted">${escapeText(w.pausedReason || "")}</span>`
        : w.lastAction
          ? `<span class="muted">${escapeText(w.lastAction)} ${escapeText(w.lastActionAt || "")}</span>`
          : "";
      return `
        <div class="events-row" style="grid-template-columns: minmax(160px,2fr) 120px 60px minmax(0,3fr);">
          <span><strong>${escapeText(w.title)}</strong></span>
          <span>${status}</span>
          <label class="event-active"><input type="checkbox" data-watchdog-map="${escapeText(w.map)}" ${w.enabled ? "checked" : ""}></label>
          <span>${detail}</span>
        </div>`;
    })
    .join("");
}

async function setWatchdog(map, enabled) {
  const data = await api("/api/watchdog/set", {
    method: "POST",
    body: JSON.stringify({ map, enabled }),
  });
  state.watchdog = data;
  renderWatchdog();
}

function renderSchedules() {
  const container = $("#scheduleList");
  if (!container || !state.schedules) return;
  const now = state.schedules.now;
  container.innerHTML = state.schedules.schedules
    .map((s) => {
      const next = s.enabled ? countdownText(s.nextRestart, now) : "off";
      return `
        <div class="mission-item">
          <div class="mission-head"><strong>${escapeText(s.title)}</strong> <span class="muted">${escapeText(s.map)} — next restart ${escapeText(next)}</span></div>
          <div class="form-grid">
            <label><input type="checkbox" data-sched-enabled="${escapeText(s.map)}" ${s.enabled ? "checked" : ""}> Enabled</label>
            <label>Every (hours)<input type="number" data-sched-interval="${escapeText(s.map)}" min="0.05" max="24" step="0.5" value="${s.intervalHours}"></label>
            <label>Warnings (min)<input type="text" data-sched-warnings="${escapeText(s.map)}" value="${escapeText((s.warnings || []).join(","))}"></label>
          </div>
          <div class="action-row">
            <button data-sched-save="${escapeText(s.map)}" type="button" data-tip="Save and (re)start this map's restart timer.">Save</button>
            <button class="ghost" data-sched-remove="${escapeText(s.map)}" type="button" data-tip="Turn off and clear this schedule.">Clear</button>
          </div>
        </div>`;
    })
    .join("");
}

async function saveSchedule(map) {
  const enabled = $(`[data-sched-enabled="${map}"]`)?.checked || false;
  const intervalHours = Number($(`[data-sched-interval="${map}"]`)?.value) || 4;
  const warnings = ($(`[data-sched-warnings="${map}"]`)?.value || "")
    .split(",")
    .map((part) => parseInt(part.trim(), 10))
    .filter((value) => Number.isInteger(value) && value > 0);
  const data = await api("/api/schedules/save", {
    method: "POST",
    body: JSON.stringify({ map, enabled, intervalHours, warnings }),
  });
  state.schedules = data;
  renderSchedules();
}

async function removeSchedule(map) {
  const data = await api("/api/schedules/remove", {
    method: "POST",
    body: JSON.stringify({ map }),
  });
  state.schedules = data;
  renderSchedules();
}

function rconTargetMap() {
  return $("#rconMapSelect")?.value || state.rconMap || state.selectedMap;
}

async function loadRconStatus(mapKey) {
  const map = mapKey || rconTargetMap();
  if (!map) return;
  state.rconMap = map;
  const data = await api(`/api/rcon/status?map=${encodeURIComponent(map)}`);
  state.rcon = data;
  const enabled = data.configured;
  const running = data.running;
  const enableBtn = $("#rconEnableButton");
  if (enableBtn) enableBtn.textContent = enabled ? "Regenerate RCON" : "Enable RCON";
  $("#rconStatus").innerHTML =
    `<strong>${escapeText(map)}:</strong> RCON ${enabled ? "enabled" : "not enabled"} on port ${data.port}. ` +
    `Server ${running ? "running" : "not running"}. ${escapeText(data.note)}`;
}

async function rconEnable() {
  const map = rconTargetMap();
  if (!map) return;
  const regenerate = state.rcon && state.rcon.configured
    ? confirm("RCON is already enabled for this map. Generate a NEW password? You must restart the map afterward.")
    : false;
  if (state.rcon && state.rcon.configured && !regenerate) return;
  const data = await api("/api/rcon/enable", {
    method: "POST",
    body: JSON.stringify({ map, regenerate }),
  });
  $("#rconStatus").innerHTML = `<strong>${escapeText(map)}:</strong> ${escapeText(data.message)}`;
  await loadRconStatus(map);
}

async function rconRun(command, extra) {
  const map = rconTargetMap();
  if (!map) return null;
  try {
    return await api("/api/rcon/run", {
      method: "POST",
      body: JSON.stringify({ map, command, ...(extra || {}) }),
    });
  } catch (error) {
    $("#rconStatus").innerHTML = `<strong>RCON error:</strong> ${escapeText(error.message || String(error))}`;
    return null;
  }
}

async function rconPlayers() {
  const data = await rconRun("players");
  if (data) $("#rconPlayers").textContent = data.output;
}

async function rconSay() {
  const message = $("#rconSayInput").value.trim();
  if (!message) return;
  await rconRun("say", { message });
  $("#rconSayInput").value = "";
  $("#rconStatus").innerHTML = `<strong>Broadcast sent.</strong>`;
}

async function rconKickBan(kind) {
  const id = Number($("#rconPlayerIdInput").value);
  if (!Number.isInteger(id) || id < 0) {
    alert("Enter the player number (#) from the players list.");
    return;
  }
  const reason = $("#rconReasonInput").value.trim();
  if (kind === "ban") {
    const minutes = Number($("#rconBanMinutesInput").value) || 0;
    if (!confirm(`Ban player #${id} for ${minutes === 0 ? "permanent" : minutes + " min"}?`)) return;
    await rconRun("ban", { id, minutes, reason });
  } else {
    await rconRun("kick", { id, reason });
  }
  $("#rconStatus").innerHTML = `<strong>${kind === "ban" ? "Ban" : "Kick"} sent for player #${id}.</strong>`;
  await rconPlayers();
}

const APP_MODES = ["simple", "advanced"];
const APP_MODE_META = {
  simple: { icon: "\u{1F331}", label: "Simple" },
  advanced: { icon: "\u{2699}", label: "Advanced" },
};

function currentAppMode() {
  const mode = localStorage.getItem("cc-mode");
  return APP_MODES.includes(mode) ? mode : "simple";
}

function applyAppMode(mode) {
  document.body.dataset.mode = mode;
  const button = $("#modeToggle");
  if (button) {
    const meta = APP_MODE_META[mode];
    const icon = button.querySelector(".theme-icon");
    const label = button.querySelector(".mode-label");
    if (icon) icon.textContent = meta.icon;
    if (label) label.textContent = meta.label;
    button.title =
      mode === "simple"
        ? "Simple mode: high-risk generation and recovery tools are hidden. Click for Advanced."
        : "Advanced mode: every tool is visible, including high-risk ones. Click for Simple.";
  }
  // If Simple mode hides the active tab, fall back to the Dashboard.
  if (mode === "simple") {
    const active = document.querySelector(".tab.active");
    if (active && active.hasAttribute("data-advanced")) activateTab("dashboard");
  }
}

function setAppMode(mode) {
  if (mode === "advanced") {
    const ok = window.confirm(
      "Advanced mode reveals high-risk tools that can stop servers, wipe imported storage, " +
        "or rebuild generated configs. These require typed confirmation before they run.\n\n" +
        "Enable Advanced mode?"
    );
    if (!ok) return;
  }
  localStorage.setItem("cc-mode", mode);
  applyAppMode(mode);
}

function toggleAppMode() {
  setAppMode(currentAppMode() === "simple" ? "advanced" : "simple");
}

function initAppMode() {
  applyAppMode(currentAppMode());
  $("#modeToggle")?.addEventListener("click", toggleAppMode);
}

const THEME_MODES = ["system", "light", "dark"];
const THEME_META = {
  system: { icon: "\u{1F5A5}", label: "System" },
  light: { icon: "☀", label: "Light" },
  dark: { icon: "\u{1F319}", label: "Dark" },
};

function currentThemeMode() {
  const mode = localStorage.getItem("cc-theme");
  return THEME_MODES.includes(mode) ? mode : "system";
}

function prefersDark() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(mode) {
  const dark = mode === "dark" || (mode === "system" && prefersDark());
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  const button = $("#themeToggle");
  if (!button) return;
  const meta = THEME_META[mode];
  const icon = button.querySelector(".theme-icon");
  const label = button.querySelector(".theme-label");
  if (icon) icon.textContent = meta.icon;
  if (label) label.textContent = meta.label;
  button.title = `Appearance: ${meta.label}. Click to switch (System → Light → Dark). Saved on this computer.`;
}

function cycleTheme() {
  const next = THEME_MODES[(THEME_MODES.indexOf(currentThemeMode()) + 1) % THEME_MODES.length];
  localStorage.setItem("cc-theme", next);
  applyTheme(next);
}

function initTheme() {
  applyTheme(currentThemeMode());
  $("#themeToggle")?.addEventListener("click", cycleTheme);
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const onSystemChange = () => {
    if (currentThemeMode() === "system") applyTheme("system");
  };
  if (media.addEventListener) media.addEventListener("change", onSystemChange);
  else if (media.addListener) media.addListener(onSystemChange);
}

function bindEvents() {
  $$(".tab").forEach((tab) => tab.addEventListener("click", () => activateTab(tab.dataset.tab)));
  document.body.addEventListener("click", (event) => {
    const target = event.target.closest("[data-tab-target]");
    if (!target) return;
    activateTab(target.dataset.tabTarget);
  });
  $("#refreshButton").addEventListener("click", () => refreshAll().catch(showError));
  $("#openValidationButton").addEventListener("click", () => runAction("validate_public_repo").catch(showError));
  $("#mapSelect").addEventListener("change", (event) => selectMap(event.target.value));
  $("#lootPresetSelect").addEventListener("change", renderLootPresetInfo);
  $("#saveLootPresetButton").addEventListener("click", () => saveLootPreset().catch(showError));
  $("#saveZombiesButton").addEventListener("click", () => saveZombies().catch(showError));
  $("#saveAiButton").addEventListener("click", () => saveAi().catch(showError));
  $("#previewConfirmButton").addEventListener("click", () => confirmPreview().catch(showError));
  $("#previewCancelButton").addEventListener("click", hidePreview);
  $("#reloadEventsButton").addEventListener("click", () => loadEvents($("#eventsMapSelect").value).catch(showError));
  $("#saveEventsButton").addEventListener("click", () => saveEvents().catch(showError));
  $("#eventsMapSelect").addEventListener("change", (event) => loadEvents(event.target.value).catch(showError));
  $("#missionMapSelect").addEventListener("change", (event) => loadMissions(event.target.value).catch(showError));
  $("#missionTypeSelect").addEventListener("change", updateMissionTypeUi);
  $("#previewMissionButton").addEventListener("click", () => previewMission().catch(showError));
  $("#reportMapSelect").addEventListener("change", (event) => {
    state.reportScope = event.target.value;
  });
  $("#generateReportButton").addEventListener("click", () => loadReport().catch(showError));
  $("#copyReportButton").addEventListener("click", () => copyReport().catch(showError));
  $("#downloadReportButton").addEventListener("click", downloadReport);
  $("#reloadSnapshotsButton").addEventListener("click", () => loadSnapshots().catch(showError));
  $("#rconMapSelect").addEventListener("change", (event) => loadRconStatus(event.target.value).catch(showError));
  $("#rconEnableButton").addEventListener("click", () => rconEnable().catch(showError));
  $("#rconPlayersButton").addEventListener("click", () => rconPlayers().catch(showError));
  $("#rconSayButton").addEventListener("click", () => rconSay().catch(showError));
  $("#rconKickButton").addEventListener("click", () => rconKickBan("kick").catch(showError));
  $("#rconBanButton").addEventListener("click", () => rconKickBan("ban").catch(showError));
  $("#playersMapSelect").addEventListener("change", (event) => loadPlayers(event.target.value).catch(showError));
  $("#reloadPlayersButton").addEventListener("click", () => loadPlayers().catch(showError));
  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-note-save]");
    if (button) savePlayerNote(button.dataset.noteSave).catch(showError);
  });
  $("#reloadSchedulesButton").addEventListener("click", () => {
    loadWatchdog().catch(showError);
    loadSchedules().catch(showError);
  });
  document.body.addEventListener("change", (event) => {
    const toggle = event.target.closest("input[data-watchdog-map]");
    if (toggle) setWatchdog(toggle.dataset.watchdogMap, toggle.checked).catch(showError);
  });
  $("#reloadUpdatesButton").addEventListener("click", () => loadUpdatesStatus().catch(showError));
  $("#saveSteamUsernameButton").addEventListener("click", () => saveSteamUsername().catch(showError));
  document.body.addEventListener("click", (event) => {
    const saveBtn = event.target.closest("button[data-sched-save]");
    if (saveBtn) { saveSchedule(saveBtn.dataset.schedSave).catch(showError); return; }
    const removeBtn = event.target.closest("button[data-sched-remove]");
    if (removeBtn) removeSchedule(removeBtn.dataset.schedRemove).catch(showError);
  });
  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-restore-snapshot]");
    if (!button) return;
    restoreSnapshot(button.dataset.restoreSnapshot).catch(showError);
  });
  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-mission-action]");
    if (!button) return;
    const id = button.dataset.missionId;
    if (button.dataset.missionAction === "save") saveMissionUpdate(id).catch(showError);
    else if (button.dataset.missionAction === "remove") removeMission(id).catch(showError);
  });
  $("#previewOverlay").addEventListener("click", (event) => {
    if (event.target === $("#previewOverlay")) hidePreview();
  });
  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-ai-preset]");
    if (!button) return;
    applyAiPreset(button.dataset.aiPreset);
  });
  $("#loadLogButton").addEventListener("click", () => loadLog().catch(showError));
  $("#copyOutputButton").addEventListener("click", () => copyOutput().catch(showError));
  $("#clearOutputButton").addEventListener("click", () => ($("#jobOutput").textContent = ""));
  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const source = button.dataset.mapSource;
    let map;
    if (source === "all") map = "all";
    else if (source === "selected") map = state.selectedMap;
    else if (source === "troubleshoot") map = $("#troubleshootMapSelect")?.value || state.selectedMap;
    runAction(button.dataset.action, map).catch(showError);
  });
  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-setup-step]");
    if (!button) return;
    saveSetupStep(button.dataset.setupStep, button.dataset.setupDone === "true").catch(showError);
  });
}

function showError(error) {
  $("#jobOutput").textContent = `ERROR: ${error.message || error}`;
}

async function init() {
  initTheme();
  initAppMode();
  bindEvents();
  await refreshAll();
  await loadLog().catch(() => {});
}

init().catch(showError);
