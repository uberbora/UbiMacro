# UbiMacro

Somewhat of an autoclicker with more features packed into it.

Record your keyboard (W/A/S/D, jump, anything) and mouse clicks once, then
replay them on a hotkey, looped as long as you want. Made mainly to keep
Roblox from kicking you for being idle while you AFK grind.

## Getting it

**Easiest:** go to the repo's **Releases** page and download `UbiMacro.exe`. No install
needed, just run it. (Every push to `main` also builds an exe under
**Actions → latest run → Artifacts**.)

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

Don't want to record anything? Click **Anti-AFK preset**. It loads a tiny
jump + step-forward + step-back macro that repeats every 60 seconds. That's plenty
to beat Roblox's 20-minute idle kick.

## Features

| | |
|---|---|
| Global hotkeys | Record/stop and play/stop work while the game is focused. Click **Change** to pick any key. |
| Game-friendly input | On Windows, playback sends hardware **scancodes** through `SendInput`, which Roblox actually picks up (lots of macro tools send keys that games ignore). |
| Looping | Repeat N times or forever (`0`), with a wait between loops. |
| Speed | Play at 0.25× to 10× speed. |
| Humanize | Randomizes the timing by ± a percentage so it looks less robotic. |
| Mouse | Records clicks (with position) and scroll. Mouse movement recording is optional. |
| Save / Load | Save macros as `.json` files (playback settings included). Your last recording is auto-saved and comes back next launch. |
| Event list | See every recorded event and delete the ones you don't want. |
| Safe stop | Stopping always releases any held keys/buttons, so W never gets stuck down. |
| Countdown | If you start recording with the button instead of the hotkey, you get a few seconds to switch to the game. The click on Stop isn't recorded either. |
| Always on top | Optional, so you can see the status over the game. |

Settings and macros are stored in `%APPDATA%\UbiMacro`.

## Tips

- Roblox needs to be the **focused window** for the playback to reach it.
- If your camera spins weirdly during playback, untick **Move mouse to recorded
  click positions** (useful in first-person / shift-lock).
- For AFK, short macros with a long wait between loops work best and keep you
  in place: e.g. walk forward, then walk back the same amount.
- Holding a key works normally. The recorder ignores Windows' auto-repeat, so
  holding W for 3 seconds plays back as one 3-second hold.
- If something isn't registering in-game, try running UbiMacro as administrator.

## Heads up

Roblox's terms don't love automation. Simple anti-idle movement is very common,
but use it at your own risk, and avoid using macros to gain an unfair
advantage over other players.

## Project layout

```
run.py                 entry point
ubimacro/app.py        the window, hotkeys, settings
ubimacro/recorder.py   recording
ubimacro/player.py     playback thread (loops, speed, humanize)
ubimacro/backends.py   Windows SendInput scancode backend (+ pynput fallback)
ubimacro/macro.py      save/load + Anti-AFK preset
tests/                 python -m unittest discover -s tests
```
