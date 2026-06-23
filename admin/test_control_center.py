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


if __name__ == "__main__":
    unittest.main()
