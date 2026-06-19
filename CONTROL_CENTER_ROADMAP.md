# DayZ Server Control Center Roadmap

This roadmap keeps Control Center work small, versioned, and releasable. Each feature slice gets validation, a focused commit, a push to `main`, and a GitHub release when the EXE changes.

## Version Path

- `v0.1.2` - Friendlier current UI: Start Here guide, tooltips, risk explanations, map advice, balance field help, and copyable job output.
- `v0.2.0` - First-run setup wizard for server root, private configs, missions, mods, VPP, and safe validation.
- `v0.3.0` - Troubleshooting center organized by symptoms and safe repair paths.
- `v0.4.0` - Better editors for loot, AI, zombies, animals, vehicles, events, and preview-before-save.
- `v0.5.0` - Mission builder for every map, including rewards, objectives, enemy counts, difficulty, and Expansion quest install/export.
- `v0.6.0` - Redacted support reports and sharing tools.
- `v0.7.0` - Polished desktop release details: app version display, release links, and first-launch clarity.
- `v1.0.0` - Public stable release after docs, validation, EXE smoke tests, and public-safe repo audit.

## Mission Builder Goals

The mission builder should let admins create map-specific money-making missions without hand-editing Expansion quest JSON.

Minimum v0.5.0 capability:

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

## Required Validation Per Slice

- `python -m py_compile admin\control_center.py`
- `node --check admin\control_center\app.js`
- `python admin\validate_public_repo.py`
- `python admin\validate_imported_maps.py`
- `powershell -ExecutionPolicy Bypass -File admin\check_map_launch.ps1 -Map all`
- EXE releases must build, launch locally, serve `/`, `/api/status`, `/api/maps`, `/api/actions`, and `/api/balance`, and run one read-only action plus snapshot through the bundled EXE.
