# UbiMacro

Somewhat of an autoclicker with more features packed into it.

Record your keyboard (W/A/S/D, jump, anything) and mouse clicks once, then
replay them on a hotkey, looped as long as you want. Made mainly to keep
Roblox from kicking you for being idle while you AFK grind.

English and Türkçe · dark and light theme · built on the Ubi design system.

## Getting it

**Easiest:** go to the repo's **Releases** page and download `UbiMacro.exe`. No install
needed, just run it.

Windows SmartScreen may warn because the exe isn't signed. Click *More info → Run anyway*.

**From source:** install [Python 3.10+](https://www.python.org/downloads/) (tick
"Add Python to PATH"), then double-click `run.bat`. Or:

```
pip install -r requirements.txt
python run.py
```

## How to use

1. Open Roblox and UbiMacro.
2. Click into the game and press **F8** to start recording.
3. Do your moves: walk, jump, click, etc.
4. Press **F8** again to stop.
5. Press **F6** to play it. It loops forever by default. Press **F6** again to stop.

Pressing **Play** inside UbiMacro switches to the Roblox window for you first.

Don't want to record anything? Click **Anti-AFK preset**. It loads a tiny
jump + step-forward + step-back macro that repeats every 60 seconds. That's plenty
to beat Roblox's 20-minute idle kick.

## The three tabs

**Home**: status, Record / Play / Stop, and the playback settings.

| Setting | What it does |
|---|---|
| Repeat | How many times to play. `0` = forever. |
| Wait between | Seconds to wait between loops. |
| Speed | `1` = normal, `2` = twice as fast. |
| Humanize | Randomizes the timing by ± that %, so it looks less robotic. |
| Stop after | Stop playing after this many minutes. `0` = never. |

**Events**: every recorded key and click with its time and the pause before it.
Pick one to edit it:

- **Time**: when the event happens. With *Move the events after it too* on, everything after moves along so holds stay the same length.
- **Pause before**: the gap since the previous event. Set it to `0` to remove a pause.
- **Remove start delay**: drops the dead time before the first event (the 0.121 s from clicking late). This also happens automatically after every recording; you can turn that off in Settings.
- **Shorten pauses longer than X s**: squeezes every long wait down to X seconds in one go.
- **Delete** and **Undo** (Ctrl+Z). Undo also brings back a cleared macro.

**Settings**: language (English / Türkçe), theme (System / Light / Dark, also
the ◐ button at the top), hotkeys, recording and playback options, keep on top,
and a button that opens the folder with your macros.

## Background playback (experimental)

Want Roblox to keep going on another screen, or behind your other windows, while
you work? Settings → **Background**:

1. Open Roblox and pick it under **Send input to** (press Refresh if it's not listed).
2. Press **Run background test**, then click into another window within 5 seconds.
3. Watch Roblox: it should jump, walk forward and click 3 times.
4. Try again with **Make the window think it's active** switched the other way.

If it works, turn on **Play in the background** and F6 plays your macro in
Roblox while your keyboard and mouse stay yours. Not every game accepts input
this way (many only listen while they are the active window), which is why it's
marked experimental.

## Features

| | |
|---|---|
| Global hotkeys | Record/stop and play/stop work while the game is focused. Change them in Settings. |
| Game-friendly input | On Windows, playback sends hardware **scancodes** through `SendInput`, which Roblox actually picks up (lots of macro tools send keys that games ignore). |
| Switches to Roblox | Pressing Play in the window brings Roblox to the front first. If Roblox isn't open, you get a countdown instead. |
| Event editor | Change any event's time or the pause before it, remove the start delay, shorten long pauses, delete, undo. |
| Looping | Repeat N times or forever, with a wait between loops and an optional time limit. |
| Speed and humanize | Play faster or slower, and add random timing variation. |
| Mouse | Records clicks (with position) and scroll. Mouse movement recording is optional. |
| Save / Load | Save macros as `.json` files (playback settings included). Your last recording is auto-saved and comes back next launch. |
| Safe stop | Stopping always releases any held keys/buttons, so W never gets stuck down. |
| Two languages | English and Turkish; it picks your Windows language the first time. |
| Dark and light | Dark by default, as in every Ubi desktop app. |
| Background mode | Experimental: send input to one window while you use the PC. |

Settings and macros are stored in `%APPDATA%\UbiMacro`.

## Tips

- Roblox needs to be the **focused window** for the playback to reach it.
- If your camera spins weirdly during playback, turn off **Move the mouse to
  where you clicked** in Settings (useful in first-person / shift-lock).
- For AFK, short macros with a long wait between loops work best and keep you
  in place: e.g. walk forward, then walk back the same amount.
- Holding a key works normally. The recorder ignores Windows' auto-repeat, so
  holding W for 3 seconds plays back as one 3-second hold.
- If something isn't registering in-game, try running UbiMacro as administrator.

## Design

UbiMacro uses the **Ubi** design system shared by the Ubi apps: Bricolage
Grotesque for titles and numbers, Figtree for text, DM Mono for small labels,
flat cards with hairline borders and one accent colour. UbiMacro's accent is
magenta. Its `macro-*` colours are in `ubimacro/theme.py`; every text colour pair
passes 4.5:1 contrast in both themes. The fonts ship inside the app under the
SIL Open Font License (see `ubimacro/assets/fonts`).

## Heads up

Roblox's terms don't love automation. Use it at your own risk.

## Project layout

```
run.py                 entry point
ubimacro/app.py        the window (CustomTkinter): tabs, hotkeys, editor, settings
ubimacro/theme.py      Ubi colours, fonts and radius scale
ubimacro/i18n.py       English and Turkish text
ubimacro/recorder.py   recording
ubimacro/player.py     playback thread (loops, speed, humanize, time limit)
ubimacro/backends.py   Windows SendInput scancode backend (+ pynput fallback)
ubimacro/macro.py      save/load, editing helpers, Anti-AFK preset
ubimacro/winfocus.py   finding/switching windows, system language
ubimacro/background.py window-message backend for background playback
tests_windows/         Windows-only check that window messages arrive
tests/                 python -m unittest discover -s tests
```
