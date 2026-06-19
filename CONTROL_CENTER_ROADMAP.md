# DayZ Server Control Center Roadmap

This roadmap keeps Control Center work small, versioned, and releasable. Each feature
slice gets validation, a focused commit, a push to `main`, and a GitHub release when
the EXE changes. The goal is the most comprehensive but beginner-friendly local DayZ
server setup and tuning app, shipped incrementally without risky big-bang rewrites.

## Working Principles

- One feature group per minor version; small slices inside it, each its own commit.
- Never batch unrelated features into one commit.
- Validate before every commit; build/tag/release only on green.
- Local-only by default: bind `127.0.0.1`, no arbitrary shell endpoint, no public secrets.
- Every write action snapshots first and is previewable; high-risk actions need typed confirmation.
- Generated release assets stay out of git tracking (`dist/` is ignored).
- Public-safe always: never track logs, storage, profiles, keys, binaries, or Workshop content.

## Version Path

- `v0.1.2` - SHIPPED. Friendlier UI: Start Here guide, tooltips, risk explanations, map advice, balance field help, copyable job output.
- `v0.2.0` - SHIPPED. First-run setup wizard for server root, private configs, missions, mods, VPP, and safe validation.
- `v0.3.0` - SHIPPED. Troubleshooting center organized by symptoms and safe repair paths.
- `v0.4.0` - SHIPPED. Better editors: loot preset explanations, AI difficulty presets and recommended ranges, zombie/animal controls, and preview-before-save.
- `v0.4.1` - SHIPPED. Vehicle, event, and airdrop controls (db/events.xml) with preview-before-save.
- `v0.5.0` - SHIPPED. Mission builder for every map: infected/AI clear, payouts, enemies, preview, install.
- `v0.5.1` - SHIPPED. Mission manager: list, edit payout/active/repeatable, and safely remove generated missions.
- `v0.6.0` - SHIPPED. Appearance and desktop polish: System/Light/Dark theme toggle, version display, and a latest-release link.
- `v0.7.0` - SHIPPED. Redacted support reports: public-safe report for one map or all, with copy and download.
- `v0.7.1` - SHIPPED. Simple vs Advanced mode (hide high-risk tools by default) and first-launch clarity.
- `v0.8.0` - SHIPPED. Backup and restore center: browse snapshots, guarded restore (typed RESTORE, snapshot-first).
- `v0.9.0` - SHIPPED. Server lifecycle: guarded start/stop/restart per map, live Dashboard polling, firewall repair.
- `v1.0.0` - Public stable release after docs, screenshots, validation, EXE smoke tests, and a public-safe repo audit.

## v0.4.1 - Vehicle, Event, And Airdrop Controls

Goal: let admins tune world events without hand-editing `db/events.xml`.

- Backend: read/write helpers for `db/events.xml` event entries (active flag, nominal,
  min, max, lifetime, restock) for known event groups (vehicles, heli crashes,
  police/ambulance/train static events, animals, and rare airdrop/loot events).
- New API: `GET /api/events?map=<map>` and `POST /api/events/preview` + `POST /api/events/save`
  reusing the preview-before-save contract (files changed, maps affected, restart required).
- UI: an Events card group in Balance (or a dedicated Events tab) with plain-English labels,
  recommended ranges, and enable/disable toggles per event group.
- Safety: clamp counts and lifetimes; snapshot before save; never touch storage.

Acceptance: preview lists `db/events.xml` per affected map; save round-trips; values clamp;
no storage or profile files are written.

## v0.5.0 - Mission Builder

The mission builder should let admins create map-specific money-making missions without
hand-editing Expansion quest JSON.

Minimum capability:

- Choose target map or all supported maps.
- Pick mission type: infected clear, AI clear, delivery, fetch, travel, or custom marker mission.
- Set title, description, location, radius, difficulty, cooldown, repeatability, and payout.
- Configure Hryvnia reward and optional item rewards.
- Configure enemy type and count where supported.
- Preview generated quest files before writing.
- Snapshot configs before install.
- Validate generated JSON/XML after install.

Safety defaults:

- Never overwrite existing custom quests without preview and confirmation.
- Keep generated mission IDs stable and readable.
- Do not require storage wipes.
- Keep all generated files public-safe unless they contain local-only secrets.

Suggested slices:

- `0.5.0a` Backend: quest schema model + generator that emits Expansion quest objective/reward JSON for one map, plus a dry-run preview.
- `0.5.0b` Backend API: `GET /api/missions?map=`, `POST /api/missions/preview`, `POST /api/missions/install`.
- `0.5.0c` UI: Mission Builder tab (type picker, fields, reward editor, enemy config, preview modal).
- `0.5.0d` Multi-map apply + validation wiring + docs.

## v0.5.1 - Mission Manager

- List generated missions per map with type, payout, and enabled state.
- Edit payout/cooldown/enabled and re-preview before save.
- Safe remove of only Control-Center-generated missions (tagged by stable ID prefix).

## v0.6.0 - Appearance And Desktop Polish (SHIPPED)

- System/Light/Dark theme toggle in the header, persisted locally and applied before first
  paint to avoid a flash; follows the OS preference when set to System.
- App version pill (from `/api/app`) plus a "Latest Release" link to the GitHub releases page.
- All UI surfaces driven by CSS variables so both themes stay readable.

## v0.7.0 - Reports And Sharing (SHIPPED)

- Redacted support report for one map or all maps: app version, configs, ports (with active/idle
  state), missions, missing mods, profiles dir, latest-log summary, and recent blockers.
  No secrets, player, or storage data.
- `GET /api/report?map=<map>` plus a Reports tab with Generate, Copy, and Download (.txt).
- Reuses existing redaction (passwords, Steam IDs, tokens) on the whole report text.

## v0.7.1 - Simple Vs Advanced Mode (SHIPPED)

- Simple mode (default) hides high-risk generation/recovery tools (Generation tab, high-risk
  action cards, Recover Imported); Advanced reveals them after a typed warning. Saved locally.
- First-launch clarity: clearer root-picker dialog copy and a one-screen "you're ready" Setup
  state with quick links to the Dashboard and a smoke test.

## v0.8.0 - Backup And Restore Center (SHIPPED)

- `GET /api/snapshots` lists zips under `admin/backups` with label, timestamp, size, and file count.
- Backups tab: browse snapshots, create one on demand, and restore (Advanced-mode only).
- Restore reuses `snapshot_configs.py --restore <zip> --yes` via an allowlisted `restore_snapshot`
  action: high-risk, typed `RESTORE` confirmation, and a snapshot of current state first.
- Snapshot names are validated (no path traversal; must exist under `admin/backups`).

## v0.9.0 - Server Lifecycle Controls (SHIPPED)

- `admin/server_lifecycle.ps1` wraps `Launch-DayZMap.ps1` (no arbitrary commands): start spawns a
  detached console; stop/restart target only the map's `DayZServer_x64` process, matched by its
  `-port=<gamePort>` command line so a still-booting server (ports not yet bound) is handled too.
- Allowlisted actions: `start_map` (guarded), `stop_map` (high, `STOP`), `restart_map` (high,
  `RESTART`), `repair_firewall` (guarded). Stop/Restart appear only in Advanced mode.
- Map Detail gains a Server Controls row; the Dashboard auto-refreshes `/api/status` every few
  seconds while open so ports/process counts update live.

## v1.0.0 - Public Stable

- Full docs pass, screenshots if available, public-safe repo audit.
- EXE smoke tests across all endpoints and one guarded action.
- Tag and release as the first public-friendly stable build.

## Required Validation Per Slice

- `python -m py_compile admin\control_center.py`
- `node --check admin\control_center\app.js`
- `python admin\validate_public_repo.py`
- `python admin\validate_imported_maps.py`
- `powershell -ExecutionPolicy Bypass -File admin\check_map_launch.ps1 -Map all`
- For admin-tooling changes: `powershell -ExecutionPolicy Bypass -File admin\check_admin_tooling.ps1 -Map all -IncludeClientProfiles -CheckDesktop`

## Definition Of Done Per Release (EXE milestones)

- Build the release zip with `admin\build_control_center_exe.ps1 -Version <x>`.
- Start the bundled EXE; verify it serves `/`, `/app.js`, `/styles.css`, and the live APIs
  (`/api/app`, `/api/status`, `/api/maps`, `/api/actions`, `/api/balance`, plus any new ones).
- Run one read-only action and any new preview endpoint through the bundled EXE; confirm
  preview/read paths write nothing.
- Confirm `git status --short` is clean (no private or generated files tracked).
- Commit, push `main`, tag `v<x>`, and create the GitHub release with the zip asset.
