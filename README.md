# Rebuild Filtered Deck Every Day

An Anki desktop add-on that automatically rebuilds your chosen filtered decks
when the study day changes. It reuses each deck's existing search, limits,
ordering, and rescheduling settings.

## Installation

1. In Anki, open **Tools → Add-ons → Install from file**.
2. Select `dist/rebuild_filtered_daily.ankiaddon` from this project.
3. Restart Anki.
4. In **Tools → Add-ons**, select **Rebuild Filtered Deck Every Day** and click
   **Config**. Check the filtered decks you want and click **Save**.

Selections start on the next study day. Cancel discards changes. The list is
refreshed whenever Config opens; ordinary decks are excluded. Settings belong
to each Anki profile and use deck IDs, so renaming a deck preserves its toggle.

## Behavior

- Uses Anki's scheduler day, including your configured rollover hour.
- Checks every 30 seconds while a profile is open, including after sleep.
- Catches up on profile open if Anki was closed at rollover. It rebuilds once
  for the current day, without replaying every missed day.
- Records successful rebuilds so reopening Anki does not repeat them that day.
- Skips deleted decks. If a rebuild fails, other selected decks still run;
  an error explains which failed. Reopen the profile after fixing the search
  to retry.
- Uses Anki's background collection operations, including normal UI refresh
  and undo handling. Overlapping filters run in deck-name order; cards already
  in another filtered deck follow Anki's usual rebuild rules.

Targets modern Qt 6 Anki desktop (23.10+). AnkiMobile and AnkiDroid do not run
desktop add-ons. The current upstream Python API has no `on_day_rollover`
hook; the add-on subscribes if one is available and otherwise relies on its
scheduler-day check. It does not patch Anki internals.

## Development

Run `python3 -m unittest discover -s tests -v` for scheduling tests using Anki
adapters. These verify rollover, deduplication, profile isolation, missing and
disabled decks, and failures. Live Anki/Qt behavior needs a manual smoke test:
install, select a filtered deck, reopen Config to confirm persistence, then
cross a study-day boundary and confirm its contents refresh only once.

To rebuild the installation archive:

```sh
python3 build.py
```
