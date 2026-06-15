# Balance Guide

The default target is public-friendly PvE with meaningful danger and generous progression.

## AI

- Medium difficulty
- Solid gear through `PvPLoadout`
- Typical patrol groups: 2-4 AI
- Accuracy target: `0.42-0.68`
- More patrols than sparse vanilla-style PvE, but not every town
- Quest AI should stay alive long enough for players to reach the objective

## Loot

- Active preset: `arcade`
- Higher item availability for casual/progression-friendly play
- Generated `mod_ce` adds boosted loot and selected weapon/optic support
- Public users can lower intensity by changing `admin/loot_config.json` and rerunning `apply_loot.py`

## Money And Vendors

- Expansion Market and Hryvnia contracts are the main money loop
- Repeatable infected and AI-clear contracts are installed by `admin/install_money_quests.py`
- The goal is to let players earn enough money to buy Expansion gear without grinding forever

## Events

- More heli crashes and static world events where each map supports them
- Airdrops are rare, roughly six hours apart
- No constant airdrop spam

## Animals And Vehicles

- Wildlife is boosted for survival gameplay and hunting
- Vehicles are more common where the map has usable event definitions
- Predators are controlled so wolves and bears do not dominate every trip

## Imported Maps

Deer Isle, Banov, Esseker, Rostow, Iztek, and Alteria use seeded COT-style locations from `mapgrouppos.xml` for first-pass patrols. These are usable defaults, but server owners can refine them by creating/exporting real COT locations in-game and rerunning the imported map generator.

Generated P2P traders, personal storage objects, trader zones, and map-specific Expansion missions are disabled on imported maps until their coordinates are verified in-game. This avoids custom-map boot loops caused by objects being placed outside usable terrain.

Imported maps also run `admin/tune_imported_ce_safety.py` after loot generation. That keeps loot generous, but lowers initial placement pressure and disables risky static/boat events that can spam CE search overtime or reference missing classes on community terrains.
