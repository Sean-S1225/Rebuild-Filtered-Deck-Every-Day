"""Exercise scheduling with lightweight Anki adapters; no collection is touched."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest


def load_addon():
    for name in ("aqt", "aqt.operations", "aqt.operations.scheduling", "aqt.qt", "aqt.utils"):
        sys.modules[name] = ModuleType(name)
    sys.modules["aqt"].gui_hooks = SimpleNamespace()
    sys.modules["aqt.operations.scheduling"].rebuild_filtered_deck = None
    for name in ("QDialog", "QDialogButtonBox", "QLabel", "QListWidget", "QListWidgetItem", "QTimer", "QVBoxLayout", "Qt"):
        setattr(sys.modules["aqt.qt"], name, object)
    sys.modules["aqt.utils"].showWarning = lambda *args, **kwargs: None
    path = Path(__file__).resolve().parents[1] / "rebuild_filtered_daily" / "addon.py"
    spec = importlib.util.spec_from_file_location("daily_addon", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


addon = load_addon()


class RolloverTests(unittest.TestCase):
    def setUp(self):
        self.config = {"profiles": {"A": {"enabled": ["2", "3", "99"], "last_rebuilt": {"2": 10, "3": 10}}}}
        self.decks = [
            {"id": 1, "name": "Normal", "dyn": 0},
            {"id": 2, "name": "Backlog", "dyn": 1},
            {"id": 3, "name": "Recent", "dyn": 1},
            {"id": 4, "name": "Disabled", "dyn": 1},
        ]
        self.calls = []
        self.fail = set()
        self.controller = addon.DailyRebuilder.__new__(addon.DailyRebuilder)
        self.controller.busy = False
        self.controller.timer = SimpleNamespace(stop=lambda: None)
        self.controller.mw = SimpleNamespace(
            pm=SimpleNamespace(name="A"),
            col=SimpleNamespace(
                sched=SimpleNamespace(today=11),
                decks=SimpleNamespace(
                    all=lambda: self.decks,
                    get=lambda did, default: next((d for d in self.decks if d["id"] == did), None),
                ),
            ),
            addonManager=SimpleNamespace(
                getConfig=lambda _: self.config,
                writeConfig=lambda _, config: None,
            ),
        )
        outer = self

        class Operation:
            def success(self, callback):
                self.ok = callback
                return self

            def failure(self, callback):
                self.error = callback
                return self

            def run_in_background(self):
                outer.calls.append(self.did)
                if self.did in outer.fail:
                    self.error(ValueError("Invalid search"))
                else:
                    self.ok(None)

        def rebuild(*, parent, deck_id):
            op = Operation()
            op.did = deck_id
            return op

        addon.rebuild_filtered_deck = rebuild

    def test_rollover_rebuilds_only_enabled_existing_filtered_decks_once(self):
        self.controller.check()
        self.controller.check()
        self.assertEqual(self.calls, [2, 3])
        self.controller.mw.col.sched.today = 12
        self.controller.check()
        self.assertEqual(self.calls, [2, 3, 2, 3])

    def test_same_day_does_nothing(self):
        self.controller.mw.col.sched.today = 10
        self.controller.check()
        self.assertEqual(self.calls, [])

    def test_failure_does_not_mark_success_or_prevent_other_decks(self):
        self.fail.add(2)
        self.controller.check()
        self.assertEqual(self.calls, [2, 3])
        self.assertEqual(self.config["profiles"]["A"]["last_rebuilt"], {"2": 10, "3": 11})
        self.assertFalse(self.controller.busy)

    def test_profiles_are_isolated(self):
        self.controller.mw.pm.name = "B"
        self.controller.check()
        self.assertEqual(self.calls, [])

    def test_closed_collection_and_overlapping_checks_are_ignored(self):
        self.controller.busy = True
        self.controller.check()
        self.controller.busy = False
        self.controller.mw.col = None
        self.controller.check()
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
