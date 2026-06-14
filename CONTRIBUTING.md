# Contributing

Thanks for helping make this useful for more DayZ server owners.

## Safety Rules

Do not commit:

- real `serverDZ*.cfg` files
- passwords, tokens, Steam IDs, or private admin values
- Workshop `@ModName` folders
- `.pbo`, `.bisign`, `.bikey`, `.dll`, `.exe`, or Steam files
- logs, crash dumps, RPT files, storage, player data, group data, ATM data, or profile persistence

Run before opening a pull request:

```powershell
python admin\validate_public_repo.py
python admin\status_all.py
```

## Good Contributions

- New map launch examples
- Safer generator behavior
- Better documentation
- Balance presets
- Fixes for invalid JSON/XML
- Better public-safe validation
- Reproducible scripts instead of manual one-off edits

## Map Requests

Include:

- Workshop link or ID
- Mission template source
- Required mods and load order
- Server-only mods, if any
- Known caveats

## Balance Changes

Describe the player experience you want, not just the numbers. For example: "more patrols around military routes, fewer in tiny villages" is more useful than "increase AI."
