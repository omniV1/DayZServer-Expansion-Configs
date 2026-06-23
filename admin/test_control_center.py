"""Behavior-locking tests for control_center.py.

Zero-dependency: run from the admin/ folder with

    python -m unittest test_control_center -v

These cover the pure decision logic and the input-validation guards that the
control center relies on for safety (clamping, sanitizing, traversal rejection,
secret redaction, schedule timing). They are written to pin *current* behavior
so the hardening refactors that follow can be verified without hand-testing the
live server.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import control_center as cc


class ClampNumberTests(unittest.TestCase):
    def test_float_in_range(self) -> None:
        self.assertEqual(cc.clamp_number(2.5, "x", 0, 10), 2.5)

    def test_integer_flag_truncates_to_int(self) -> None:
        value = cc.clamp_number("7", "x", 0, 10, integer=True)
        self.assertIsInstance(value, int)
        self.assertEqual(value, 7)

    def test_below_min_raises(self) -> None:
        with self.assertRaises(ValueError):
            cc.clamp_number(-1, "x", 0, 10)

    def test_above_max_raises(self) -> None:
        with self.assertRaises(ValueError):
            cc.clamp_number(11, "x", 0, 10)

    def test_non_number_raises(self) -> None:
        with self.assertRaises(ValueError):
            cc.clamp_number("abc", "x", 0, 10)

    def test_none_raises(self) -> None:
        with self.assertRaises(ValueError):
            cc.clamp_number(None, "x", 0, 10)


class NormalizeWarningsTests(unittest.TestCase):
    def test_sorted_desc_and_deduped(self) -> None:
        # interval 4h -> 240 min window; all valid, dupes collapsed.
        self.assertEqual(cc.normalize_warnings([5, 30, 15, 30, 1], 4.0), [30, 15, 5, 1])

    def test_drops_out_of_window(self) -> None:
        # interval 1h -> 60 min; 90 is >= interval so dropped, 0 is < 1 so dropped.
        self.assertEqual(cc.normalize_warnings([90, 30, 0, 5], 1.0), [30, 5])

    def test_ignores_non_integers(self) -> None:
        self.assertEqual(cc.normalize_warnings(["x", None, 10], 4.0), [10])

    def test_capped_to_max(self) -> None:
        result = cc.normalize_warnings(list(range(1, 50)), 4.0)
        self.assertLessEqual(len(result), cc.SCHEDULE_WARNINGS_MAX)

    def test_empty(self) -> None:
        self.assertEqual(cc.normalize_warnings(None, 4.0), [])


class ScheduleDueActionsTests(unittest.TestCase):
    def test_disabled_returns_nothing(self) -> None:
        self.assertEqual(cc.schedule_due_actions({"enabled": False, "nextRestart": 1}, 100), [])

    def test_no_next_restart_returns_nothing(self) -> None:
        self.assertEqual(cc.schedule_due_actions({"enabled": True}, 100), [])

    def test_past_due_fires_restart(self) -> None:
        actions = cc.schedule_due_actions({"enabled": True, "nextRestart": 100}, 100)
        self.assertEqual(actions, [{"type": "restart"}])

    def test_warning_fires_once_in_window(self) -> None:
        sched = {"enabled": True, "nextRestart": 10000, "warnings": [30, 15, 5], "warnedMinutes": []}
        now = 10000 - 16 * 60  # 16 min out: only the 30-min warning is due
        self.assertEqual(cc.schedule_due_actions(sched, now), [{"type": "warn", "minutes": 30}])

    def test_already_warned_minutes_are_skipped(self) -> None:
        sched = {"enabled": True, "nextRestart": 10000, "warnings": [30, 15, 5], "warnedMinutes": [30]}
        now = 10000 - 16 * 60
        self.assertEqual(cc.schedule_due_actions(sched, now), [])


class RedactTests(unittest.TestCase):
    def test_password_admin(self) -> None:
        self.assertEqual(cc.redact('passwordAdmin="hunter2"'), 'passwordAdmin="<redacted>"')

    def test_generic_password(self) -> None:
        self.assertEqual(cc.redact('password="abc"'), 'password="<redacted>"')

    def test_rcon_password(self) -> None:
        self.assertEqual(cc.redact("RConPassword s3cr3t"), "RConPassword <redacted>")

    def test_steamid(self) -> None:
        self.assertIn("<steamid>", cc.redact("player 76561198000000000 joined"))

    def test_github_token(self) -> None:
        self.assertIn("<token>", cc.redact("auth gho_abcDEF123456"))


class SanitizeRconTextTests(unittest.TestCase):
    def test_newlines_become_spaces(self) -> None:
        self.assertEqual(cc.sanitize_rcon_text("hello\r\nworld"), "hello  world")

    def test_truncates_to_limit(self) -> None:
        self.assertEqual(cc.sanitize_rcon_text("a" * 500, limit=10), "a" * 10)

    def test_none_is_empty(self) -> None:
        self.assertEqual(cc.sanitize_rcon_text(None), "")


class ValidateSnapshotNameTests(unittest.TestCase):
    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            cc.validate_snapshot_name({"snapshot": ""})

    def test_parent_traversal_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cc.validate_snapshot_name({"snapshot": "../evil.zip"})

    def test_backslash_traversal_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cc.validate_snapshot_name({"snapshot": "..\\evil.zip"})

    def test_non_zip_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cc.validate_snapshot_name({"snapshot": "configs.txt"})

    def test_valid_name_but_missing_is_not_found(self) -> None:
        # A clean name passes the traversal/extension guards and then fails on
        # existence -- still a ValueError, never an escape.
        with self.assertRaises(ValueError):
            cc.validate_snapshot_name({"snapshot": "definitely-not-here-12345.zip"})


class MissionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_map_configs = cc.map_configs
        cc.map_configs = lambda: {"chernarus": {"title": "Chernarus"}}  # type: ignore[assignment]

    def tearDown(self) -> None:
        cc.map_configs = self._orig_map_configs  # type: ignore[assignment]

    def test_unknown_map_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cc.validate_mission_payload({"map": "atlantis", "type": "infected_clear", "title": "x"})

    def test_unknown_type_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cc.validate_mission_payload({"map": "chernarus", "type": "bogus", "title": "x"})

    def test_missing_title_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cc.validate_mission_payload({"map": "chernarus", "type": "infected_clear", "title": "  "})

    def test_title_too_long_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cc.validate_mission_payload(
                {"map": "chernarus", "type": "infected_clear", "title": "x" * 81}
            )

    def test_payout_clamped_and_int(self) -> None:
        spec = cc.validate_mission_payload(
            {"map": "chernarus", "type": "infected_clear", "title": "Hunt", "payout": "250"}
        )
        self.assertEqual(spec["payout"], 250)
        self.assertIsInstance(spec["payout"], int)

    def test_payout_over_max_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cc.validate_mission_payload(
                {"map": "chernarus", "type": "infected_clear", "title": "Hunt", "payout": 9_999_999}
            )

    def test_ai_type_requires_location(self) -> None:
        with self.assertRaises(ValueError):
            cc.validate_mission_payload({"map": "chernarus", "type": "ai_clear", "title": "Raid"})

    def test_ai_type_with_location_ok(self) -> None:
        spec = cc.validate_mission_payload(
            {"map": "chernarus", "type": "ai_clear", "title": "Raid", "location": [1, 2, 3]}
        )
        self.assertEqual(spec["location"], [1.0, 2.0, 3.0])

    def test_item_reward_classname_capped(self) -> None:
        spec = cc.validate_mission_payload(
            {
                "map": "chernarus",
                "type": "infected_clear",
                "title": "Hunt",
                "itemReward": {"className": "C" * 500, "amount": 2},
            }
        )
        self.assertLessEqual(len(spec["itemReward"]["className"]), 128)


class MissionUpdateFieldsTests(unittest.TestCase):
    def test_payout_clamped(self) -> None:
        self.assertEqual(cc.mission_update_fields({"payout": "100"}), {"payout": 100})

    def test_booleans_become_ints(self) -> None:
        self.assertEqual(
            cc.mission_update_fields({"active": True, "repeatable": False}),
            {"active": 1, "repeatable": 0},
        )

    def test_absent_fields_omitted(self) -> None:
        self.assertEqual(cc.mission_update_fields({}), {})


class RconMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig = cc.map_configs
        cc.map_configs = lambda: {"chernarus": {"title": "Chernarus"}}  # type: ignore[assignment]

    def tearDown(self) -> None:
        cc.map_configs = self._orig  # type: ignore[assignment]

    def test_lowercases(self) -> None:
        self.assertEqual(cc.rcon_map({"map": "CHERNARUS"}), "chernarus")

    def test_unknown_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cc.rcon_map({"map": "atlantis"})


class ActionRegistryTests(unittest.TestCase):
    """The action registry is the security boundary -- lock its shape."""

    def test_known_actions_present(self) -> None:
        specs = cc.action_specs()
        for key in ("status_all", "start_map", "stop_map", "restart_map", "full_generation_refresh"):
            self.assertIn(key, specs)

    def test_high_risk_actions_require_confirmation(self) -> None:
        specs = cc.action_specs()
        for key, spec in specs.items():
            if spec.risk == "high":
                self.assertTrue(spec.confirm, f"high-risk action {key} must define confirm text")

    def test_map_modes_are_valid(self) -> None:
        valid = {"none", "all", "one", "imported"}
        for key, spec in cc.action_specs().items():
            self.assertIn(spec.map_mode, valid, f"{key} has bad map_mode {spec.map_mode}")


class ReadJsonResilienceTests(unittest.TestCase):
    """A corrupt/half-written config must degrade to default, never crash startup."""

    def setUp(self) -> None:
        import tempfile

        self._dir = tempfile.mkdtemp(prefix="cc-readjson-")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self._dir, ignore_errors=True)

    def test_missing_returns_default(self) -> None:
        self.assertEqual(cc.read_json(Path(self._dir) / "nope.json", {"d": 1}), {"d": 1})

    def test_valid_json_parsed(self) -> None:
        p = Path(self._dir) / "ok.json"
        p.write_text('{"a": 2}', encoding="utf-8")
        self.assertEqual(cc.read_json(p, {}), {"a": 2})

    def test_corrupt_json_returns_default(self) -> None:
        p = Path(self._dir) / "bad.json"
        p.write_text('{"a": 2', encoding="utf-8")  # truncated / half-written
        self.assertEqual(cc.read_json(p, {"fallback": True}), {"fallback": True})

    def test_garbage_returns_default(self) -> None:
        p = Path(self._dir) / "junk.json"
        p.write_text("not json at all \x00\xff", encoding="latin-1")
        self.assertEqual(cc.read_json(p, []), [])


class BackupStorageTests(unittest.TestCase):
    """backup_storage.py: retention pruning and mission resolution."""

    def setUp(self) -> None:
        import tempfile

        import backup_storage as bs

        self.bs = bs
        self._dir = Path(tempfile.mkdtemp(prefix="cc-backup-"))

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self._dir, ignore_errors=True)

    def test_prune_keeps_newest_n(self) -> None:
        import os, time

        folder = self._dir / "chernarus"
        folder.mkdir()
        for i in range(5):
            f = folder / f"chernarus_{i}.zip"
            f.write_text("x")
            os.utime(f, (time.time() + i, time.time() + i))  # i=4 newest
        removed = self.bs.prune(folder, retention=2)
        remaining = sorted(p.name for p in folder.glob("*.zip"))
        self.assertEqual(len(remaining), 2)
        self.assertEqual(remaining, ["chernarus_3.zip", "chernarus_4.zip"])
        self.assertEqual(len(removed), 3)

    def test_prune_retention_floor_is_one(self) -> None:
        folder = self._dir / "m"
        folder.mkdir()
        (folder / "a.zip").write_text("x")
        self.bs.prune(folder, retention=0)  # clamped to 1, keeps the newest
        self.assertEqual(len(list(folder.glob("*.zip"))), 1)

    def test_mission_for_reads_template(self) -> None:
        orig_root = self.bs.ROOT
        try:
            self.bs.ROOT = self._dir
            cfg = self._dir / "serverDZ.cfg"
            cfg.write_text('hostname = "x";\ntemplate = "dayzOffline.chernarusplus";\n', encoding="utf-8")
            self.assertEqual(self.bs.mission_for("serverDZ.cfg"), "dayzOffline.chernarusplus")
            self.assertEqual(self.bs.mission_for("missing.cfg"), "")
            self.assertEqual(self.bs.mission_for(""), "")
        finally:
            self.bs.ROOT = orig_root


class RestoreStorageTests(unittest.TestCase):
    """restore_storage.py: backup selection and name-traversal guard."""

    def setUp(self) -> None:
        import tempfile

        import restore_storage as rs

        self.rs = rs
        self._orig_root = rs.BACKUP_ROOT
        self._dir = Path(tempfile.mkdtemp(prefix="cc-restore-"))
        rs.BACKUP_ROOT = self._dir

    def tearDown(self) -> None:
        import shutil

        self.rs.BACKUP_ROOT = self._orig_root
        shutil.rmtree(self._dir, ignore_errors=True)

    def _make(self, name: str, when: float) -> None:
        import os

        folder = self._dir / "chernarus"
        folder.mkdir(exist_ok=True)
        f = folder / name
        f.write_text("x")
        os.utime(f, (when, when))

    def test_picks_newest_by_default(self) -> None:
        self._make("chernarus_1.zip", 1000)
        self._make("chernarus_2.zip", 2000)
        self.assertEqual(self.rs.pick_backup("chernarus", None).name, "chernarus_2.zip")

    def test_picks_named_backup(self) -> None:
        self._make("chernarus_1.zip", 1000)
        self._make("chernarus_2.zip", 2000)
        self.assertEqual(self.rs.pick_backup("chernarus", "chernarus_1.zip").name, "chernarus_1.zip")

    def test_rejects_path_traversal_name(self) -> None:
        self._make("chernarus_1.zip", 1000)
        self.assertIsNone(self.rs.pick_backup("chernarus", "../escape.zip"))
        self.assertIsNone(self.rs.pick_backup("chernarus", "notazip.txt"))

    def test_none_when_no_backups(self) -> None:
        self.assertIsNone(self.rs.pick_backup("chernarus", None))


class ParseStorageHealthTests(unittest.TestCase):
    """Stream-damage / failed-item detection over CE load output."""

    def test_clean_log_is_zero(self) -> None:
        lines = [
            "[CE][Storage] Restoring file dynamic_000.bin 1853 items.",
            "  373 items loaded. (0 failed)",
        ]
        h = cc.parse_storage_health(lines)
        self.assertEqual(h, {"damageEvents": 0, "itemsLoaded": 373, "itemsFailed": 0})

    def test_counts_damage_events(self) -> None:
        lines = [
            "!!! Serious stream damage detected during load, file offset: 45b3a",
            "!!! Serious stream damage detected during load, file offset: 54202",
            "normal line",
        ]
        self.assertEqual(cc.parse_storage_health(lines)["damageEvents"], 2)

    def test_sums_failed_across_files(self) -> None:
        lines = [
            "  5666 items loaded. (4 failed)",
            "  4352 items loaded. (4 failed)",
            "  5012 items loaded. (1 failed)",
        ]
        h = cc.parse_storage_health(lines)
        self.assertEqual(h["itemsFailed"], 9)
        self.assertEqual(h["itemsLoaded"], 5666 + 4352 + 5012)

    def test_real_log_excerpt(self) -> None:
        excerpt = """10:26:08 !!! Serious stream damage detected during load, file offset: 45b3a
10:26:09 !!! Serious stream damage detected during load, file offset: 1fbd3
10:26:13   5666 items loaded. (4 failed)
10:26:18   4352 items loaded. (4 failed)
10:26:42   373 items loaded. (0 failed)""".splitlines()
        h = cc.parse_storage_health(excerpt)
        self.assertEqual(h["damageEvents"], 2)
        self.assertEqual(h["itemsFailed"], 8)


class FindFatalLineTests(unittest.TestCase):
    """Crash-cause extraction for the watchdog."""

    def test_none_when_clean(self) -> None:
        self.assertIsNone(cc.find_fatal_line(["10:00 normal", "10:01 [CE] loaded"]))

    def test_finds_crash(self) -> None:
        line = cc.find_fatal_line(["start", "ENGINE  (F): Crashed: bad alloc", "after"])
        self.assertIn("Crashed", line)

    def test_returns_most_recent_match(self) -> None:
        lines = [
            "SCRIPT ERROR first one",
            "noise",
            "NO VALID SPAWNS no valid regular player spawn points",
        ]
        # reversed scan -> the spawns line (last) wins
        self.assertIn("NO VALID SPAWNS", cc.find_fatal_line(lines))

    def test_detects_missing_pbo(self) -> None:
        self.assertIsNotNone(cc.find_fatal_line(["cannot open file foo.pbo not found"]))


class QueryHelperTests(unittest.TestCase):
    def test_query_map_lowercases(self) -> None:
        self.assertEqual(cc.query_map({"map": ["CherNarus"]}), "chernarus")

    def test_query_map_absent_is_empty(self) -> None:
        self.assertEqual(cc.query_map({}), "")

    def test_query_int_parses(self) -> None:
        self.assertEqual(cc.query_int({"lines": ["50"]}, "lines", 200), 50)

    def test_query_int_default_on_missing(self) -> None:
        self.assertEqual(cc.query_int({}, "lines", 200), 200)

    def test_query_int_default_on_junk(self) -> None:
        self.assertEqual(cc.query_int({"lines": ["abc"]}, "lines", 200), 200)


class RequireMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig = cc.map_configs
        cc.map_configs = lambda: {"chernarus": {}}  # type: ignore[assignment]

    def tearDown(self) -> None:
        cc.map_configs = self._orig  # type: ignore[assignment]

    def test_lowercases_and_returns(self) -> None:
        self.assertEqual(cc.require_map("CHERNARUS"), "chernarus")

    def test_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            cc.require_map("atlantis")

    def test_none_raises(self) -> None:
        with self.assertRaises(ValueError):
            cc.require_map(None)


class LifecycleConcurrencyTests(unittest.TestCase):
    """Two lifecycle actions for the same map must never run at once."""

    def setUp(self) -> None:
        self._orig_map_configs = cc.map_configs
        cc.map_configs = lambda: {"chernarus": {"title": "Chernarus", "port": 2302}}  # type: ignore[assignment]
        cc._INFLIGHT_MAPS.clear()

    def tearDown(self) -> None:
        cc.map_configs = self._orig_map_configs  # type: ignore[assignment]
        cc._INFLIGHT_MAPS.clear()

    def test_reserve_then_double_reserve_raises(self) -> None:
        cc._reserve_lifecycle("start_map", "chernarus")
        with self.assertRaises(ValueError):
            cc._reserve_lifecycle("restart_map", "chernarus")

    def test_release_frees_the_map(self) -> None:
        cc._reserve_lifecycle("start_map", "chernarus")
        cc._release_lifecycle("start_map", "chernarus")
        cc._reserve_lifecycle("restart_map", "chernarus")  # should not raise
        self.assertIn("chernarus", cc._INFLIGHT_MAPS)

    def test_non_lifecycle_action_is_not_reserved(self) -> None:
        cc._reserve_lifecycle("status_all", None)
        cc._reserve_lifecycle("apply_loot_current", None)
        self.assertEqual(cc._INFLIGHT_MAPS, set())

    def test_start_action_refuses_busy_map(self) -> None:
        # Pre-reserve so start_action hits the guard and raises *before* it ever
        # builds a command or spawns a thread.
        cc._INFLIGHT_MAPS.add("chernarus")
        with self.assertRaises(ValueError):
            cc.start_action({"action": "start_map", "map": "chernarus"})


class PostRouteTableTests(unittest.TestCase):
    """The POST route table is now the single source of truth -- lock its shape."""

    def test_all_handlers_callable(self) -> None:
        for path, handler in cc.POST_HANDLERS.items():
            self.assertTrue(callable(handler), f"{path} handler is not callable")

    def test_actions_run_is_special_cased_not_in_table(self) -> None:
        # /api/actions/run returns 202 and is dispatched separately; it must not
        # be in the 200-returning table or it would be double-handled.
        self.assertNotIn(cc.ACTIONS_RUN_PATH, cc.POST_HANDLERS)

    def test_expected_routes_present(self) -> None:
        for path in (
            "/api/balance/save",
            "/api/missions/install",
            "/api/missions/remove",
            "/api/setup/save",
            "/api/rcon/run",
            "/api/schedules/save",
            "/api/watchdog/set",
        ):
            self.assertIn(path, cc.POST_HANDLERS)


class SendErrorJsonRedactionTests(unittest.TestCase):
    """Client-facing errors must not leak secrets even when an exception carries them."""

    def _handler(self):
        handler = cc.Handler.__new__(cc.Handler)  # skip socket setup
        captured: dict = {}
        handler.send_json = lambda status, data: captured.update(status=status, data=data)  # type: ignore[method-assign]
        return handler, captured

    def test_redacts_rcon_password_in_error(self) -> None:
        handler, captured = self._handler()
        handler.send_error_json(500, "boom RConPassword s3cr3t while reading")
        self.assertEqual(captured["status"], 500)
        self.assertIn("<redacted>", captured["data"]["error"])
        self.assertNotIn("s3cr3t", captured["data"]["error"])

    def test_plain_message_passes_through(self) -> None:
        handler, captured = self._handler()
        handler.send_error_json(404, "Job not found.")
        self.assertEqual(captured["data"]["error"], "Job not found.")


if __name__ == "__main__":
    unittest.main()
