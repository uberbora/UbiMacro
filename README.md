# UbiMacro

Somewhat of an autoclicker with more features packed into it.

Record your keyboard and mouse once and replay it on a hotkey, or let the
auto-clicker click for you. Made mainly to keep Roblox from kicking you for
being idle while you AFK grind.

English and Türkçe · dark and light theme · built on the Ubi design system.

## Getting it

**Easiest:** open the repo's **Releases** page and download `UbiMacro.exe`. No install
needed, just run it. Windows SmartScreen may warn because the exe isn't signed: click
*More info → Run anyway*.

**From source:** install [Python 3.10+](https://www.python.org/downloads/) (tick
"Add Python to PATH"), then double-click `run.bat`, or:

```
pip install -r requirements.txt
python run.py
```

## Quick start

**Macro:** click into Roblox, press **F8**, do your moves, press **F8** again. Press **F6**
to play it (it loops forever by default) and **F6** again to stop.

**Auto-clicker:** on Home switch to **Auto-clicker**, set the speed, then press **F7** in
the game to start and stop clicking.

**Stop everything:** **End**, whatever is running.

## Hotkeys

| Key | What it does |
|---|---|
| F8 | Record / stop recording (a new recording goes into the Library) |
| F6 | Play / stop the current macro |
| F7 | Auto-clicker on / off (or hold it, if you choose Hold) |
| F9 | Mini mode on / off |
| End | Stop everything |
| your own | Each macro in the Library can have its own key that plays it straight away |

All of them work while the game is focused, and all can be changed in Settings.

## The tabs

**Home:** the status card (with a live timer while running), Macro / Auto-clicker,
the current macro, Loops / Clicks / Today, and the playback settings
(repeat, wait between loops, speed, humanize, stop after).

**Library:** every macro you've recorded. Search, favourites, a hotkey per macro,
and right-click (or ⋯) to rename, duplicate, change the key, export or delete.
**Import…** brings in a macro file someone shared. The built-in **Anti-AFK** preset
(jump, step forward, step back every 60 s) is here too.

**Events:** the macro as a timeline, one lane per key or mouse button.

- Drag a bar to move it, drag its ends to hold longer or shorter. Ctrl+scroll zooms.
- Pick one and type its **Starts at**, **Held for** or **Pause before** (set a pause to 0 to remove it).
- **Remove start delay** drops the dead time before the first event (also done automatically after recording).
- **Shorten long pauses** squeezes every wait longer than the limit in Settings.
- **Record from here** records a new take and inserts it after the selected event.
- **Test from here** plays the macro once from the selected event.
- **List** view shows every event as a row. **Undo** with Ctrl+Z.

**Settings:**

- **Safety:** pause when you touch the mouse or keyboard and pick up again after a few quiet seconds; stop and alert you if Roblox closes; only play while Roblox is in front.
- **Recording:** record mouse movement, remove the start delay, countdown, long-pause limit.
- **Playback:** switch to Roblox when you press Play in the window; move the mouse to recorded click spots.
- **Notifications:** start/stop sounds, a **Discord webhook** (Discord: Server settings › Integrations › Webhooks › New webhook › Copy link) and your **Discord user ID** so alerts can @mention you and make your phone buzz.
- **Discord alerts:** switch each one on or off, edit its message, choose whether it pings you, and send a test:
  - **Roblox closed:** the window closed or crashed.
  - **Disconnected:** kicked, server shut down, lost connection, or the 20-minute idle kick. UbiMacro reads this from Roblox's own log file (`%LOCALAPPDATA%\Roblox\logs`), because the window stays open when you're disconnected. Leaving a game yourself doesn't count.
  - **Finished**, **Status update** (every N minutes), **Paused for a while**, **Started**, **Stopped**.
  - Messages can use `{macro}` `{time}` `{loops}` `{clicks}` `{reason}` `{date}` and `**bold**`.
- **Window:** keep on top, start in mini mode, close to the tray.
- **Updates:** check for a newer release on start.
- **Language:** English / Türkçe. **Theme:** System / Light / Dark.

**Recent runs** (bottom of the Library): what ran, when, for how long, how many loops or clicks, and how it
ended (finished, time's up, stopped, Roblox closed, disconnected). The last 100 runs are kept.

**Mini mode:** a small bar that stays on top of the game with the status, the
timer and a start/stop button. Drag it anywhere, and press ⤢ or F9 to get the full window back.

## Good to know

- Roblox has to be the **window in front** for input to reach it: Windows sends keyboard
  and mouse input to the active window only, and Roblox ignores input while it's in the
  background. UbiMacro can't get around that, so the Safety options are there to make
  sure it never types into your other windows by mistake.
- Pausing when you touch the mouse/keyboard and "only play when Roblox is in front" need
  Windows (they rely on Windows telling real input apart from UbiMacro's own).
- The update check asks GitHub for the newest release. It only works while this
  repository is public; for a private repo it quietly finds nothing.
- Your macros and settings live in `%APPDATA%\UbiMacro` (Settings › Storage › Open folder).
  Macros saved by older versions show up in the Library automatically.
- If something isn't registering in-game, try running UbiMacro as administrator.

Roblox's terms don't love automation. Use it at your own risk.

## Design

UbiMacro uses the **Ubi** design system shared by the Ubi apps: Bricolage Grotesque
for titles and numbers, Figtree for text, DM Mono for small labels, flat cards with
hairline borders and one accent colour (magenta for UbiMacro). Every text colour pair
passes 4.5:1 contrast in both themes. The fonts ship inside the app under the SIL
Open Font License (see `ubimacro/assets/fonts`).

## Project layout

```
run.py                    entry point
ubimacro/app.py           controller: state, hotkeys, record/play/click, pausing, alerts, stats
ubimacro/ui/              the window: shell, home, library, events (timeline), settings, mini, tray
ubimacro/ui/kit.py        Ubi widgets (cards, chips, switches, buttons)
ubimacro/ui/icons.py      line icons drawn with Pillow
ubimacro/player.py        macro playback (loops, speed, humanize, time limit, pause)
ubimacro/clicker.py       the auto-clicker
ubimacro/timing.py        shared precise waiting with stop / pause / time limit
ubimacro/recorder.py      recording
ubimacro/library.py       the macro library (one .json per macro)
ubimacro/macro.py         macro files, timeline model and editing helpers
ubimacro/backends.py      Windows SendInput scancode backend (+ pynput fallback)
ubimacro/notify.py        sounds, Discord alerts (cards, templates, pings), update check
ubimacro/robloxlog.py     reads Roblox's log to notice disconnects
ubimacro/history.py       recent runs
ubimacro/winfocus.py      finding / focusing the Roblox window, system language
ubimacro/theme.py         Ubi colours and fonts
ubimacro/i18n.py          English and Turkish text
tests/                    python -m unittest discover -s tests
```
