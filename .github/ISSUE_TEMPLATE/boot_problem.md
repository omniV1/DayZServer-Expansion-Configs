---
name: Server boot problem
about: Report a map/server launch issue
title: "Boot problem: "
labels: support
---

## Map

- Map key:
- Launch command used:

## What Happened

Describe the failure.

## Checks

Paste relevant output:

```text
powershell -ExecutionPolicy Bypass -File admin\check_map_launch.ps1 -Map all
python admin\validate_public_repo.py
```

## Logs

Paste only short relevant RPT snippets. Do not upload full logs with private data.
