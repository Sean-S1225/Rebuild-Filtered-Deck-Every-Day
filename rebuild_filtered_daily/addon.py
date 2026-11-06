from __future__ import annotations

from collections import deque

import aqt
from aqt import gui_hooks
from aqt.operations.scheduling import rebuild_filtered_deck
from aqt.qt import (
    QDialog, QDialogButtonBox, QLabel, QListWidget, QListWidgetItem,
    QTimer, QVBoxLayout, Qt,
)
from aqt.utils import showWarning

MODULE = __package__


class DailyRebuilder:
    def __init__(self, mw):
        self.mw = mw
        self.busy = False
        self.timer = QTimer(mw)
        self.timer.setInterval(30_000)
        self.timer.timeout.connect(self.check)

    def settings(self):
        config = self.mw.addonManager.getConfig(MODULE) or {}
        profiles = config.setdefault("profiles", {})
        settings = profiles.setdefault(
            self.mw.pm.name, {"enabled": [], "last_rebuilt": {}}
        )
        return config, settings

    def filtered_decks(self):
        return sorted(
            (d for d in self.mw.col.decks.all() if d.get("dyn")),
            key=lambda d: (d["name"].casefold(), d["id"]),
        )

    def profile_opened(self):
        self.timer.start()
        QTimer.singleShot(0, self.check)

    def profile_closed(self):
        self.timer.stop()

    def check(self, *_args):
        if self.busy or not self.mw.col or not self.mw.pm.name:
            return
        col = self.mw.col
        profile = self.mw.pm.name
        today = col.sched.today
        _, settings = self.settings()
        enabled = {str(did) for did in settings.get("enabled", [])}
        last = settings.get("last_rebuilt", {})
        pending = deque(
            (d["id"], d["name"]) for d in self.filtered_decks()
            if str(d["id"]) in enabled and last.get(str(d["id"])) != today
        )
        if not pending:
            return
        self.busy = True
        errors = []

        def advance():
            # A queued callback must never operate on a newly opened profile.
            if self.mw.col is not col or self.mw.pm.name != profile:
                self.busy = False
                return
            if not pending:
                self.busy = False
                if errors:
                    # Pause automatic retries until the next profile open, so a
                    # broken search cannot produce a popup every 30 seconds.
                    self.timer.stop()
                    showWarning(
                        "Some filtered decks could not be rebuilt:\n\n"
                        + "\n".join(errors)
                        + "\n\nFix their searches, then reopen the profile to retry.",
                        parent=self.mw,
                    )
                return
            did, name = pending.popleft()
            _, current = self.settings()
            deck = col.decks.get(did, default=False)
            if str(did) not in {str(i) for i in current.get("enabled", [])} or not deck or not deck.get("dyn"):
                advance()
                return

            def success(_result):
                if self.mw.col is col and self.mw.pm.name == profile:
                    config, current = self.settings()
                    current.setdefault("last_rebuilt", {})[str(did)] = today
                    self.mw.addonManager.writeConfig(MODULE, config)
                advance()

            def failure(error):
                errors.append(f"{name}: {error}")
                advance()

            rebuild_filtered_deck(parent=self.mw, deck_id=did).success(
                success
            ).failure(failure).run_in_background()

        advance()

    def configure(self):
        if not self.mw.col:
            showWarning("Open a profile before configuring filtered decks.", parent=self.mw)
            return
        col = self.mw.col
        profile = self.mw.pm.name
        _, settings = self.settings()
        enabled = {str(did) for did in settings.get("enabled", [])}
        dialog = QDialog(self.mw)
        dialog.setWindowTitle("Rebuild Filtered Deck Every Day")
        dialog.resize(500, 400)
        layout = QVBoxLayout(dialog)
        label = QLabel(
            "Choose the filtered decks to rebuild each study day.\n"
            "Uses your rollover time in Anki Preferences.\n"
            "New selections start rebuilding on the next study day."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        listing = QListWidget()
        layout.addWidget(listing)
        decks = self.filtered_decks()
        if not decks:
            layout.addWidget(QLabel("No filtered decks yet. Create one in Anki first."))
        for deck in decks:
            item = QListWidgetItem(deck["name"], listing)
            item.setData(Qt.ItemDataRole.UserRole, str(deck["id"]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if str(deck["id"]) in enabled
                else Qt.CheckState.Unchecked
            )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if not dialog.exec():
            return
        if self.mw.col is not col or self.mw.pm.name != profile:
            return
        selected = [
            listing.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(listing.count())
            if listing.item(i).checkState() == Qt.CheckState.Checked
        ]
        config, current = self.settings()
        last = current.get("last_rebuilt", {})
        today = col.sched.today
        current["enabled"] = selected
        current["last_rebuilt"] = {
            did: last.get(did, today) if did in enabled else today
            for did in selected
        }
        self.mw.addonManager.writeConfig(MODULE, config)


def setup():
    mw = aqt.mw
    controller = DailyRebuilder(mw)
    # Keep the controller and its timer alive for the application's lifetime.
    mw._rebuild_filtered_daily = controller
    mw.addonManager.setConfigAction(MODULE, controller.configure)
    gui_hooks.profile_did_open.append(controller.profile_opened)
    gui_hooks.profile_will_close.append(controller.profile_closed)
    rollover = getattr(gui_hooks, "on_day_rollover", None)
    if rollover is not None:
        rollover.append(controller.check)
