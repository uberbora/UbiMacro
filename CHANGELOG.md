# Changelog

## 1.3.0

A redesign on the Ubi design system, and a lot of new features.

- **Auto-clicker** mode: set clicks a second, left or right button, F7 as on/off or hold, click where the mouse is or at a fixed spot, with slight speed variation.
- **Library tab**: every recording is kept as its own macro, with search, favourites, rename, duplicate, import/export, delete, and **a hotkey per macro** that plays it straight away.
- **Timeline editor** on the Events tab: drag bars to move them or change how long a key is held, edit start / held / pause times, record a new take from any point, test from any point (the list view is still there).
- **Stop everything** key (End).
- **Safety:** pause when you touch the mouse or keyboard (picks up again after a few quiet seconds), stop and alert you if Roblox closes, only play while Roblox is in front.
- **Notifications:** start/stop sounds and an optional Discord webhook message when Roblox closes or a run finishes.
- **Mini mode:** a small always-on-top bar with the timer and a start/stop button (F9).
- **Stats:** loops, clicks and time today.
- Close to the tray, start in mini mode, update check, playback settings shown as chips on Home.
- Removed the experimental background playback from 1.2 (Roblox doesn't accept input that way).
- Your 1.2 macro moves into the Library automatically.

## 1.2.0

- **Play in the background (experimental):** sends keys and clicks straight to one window (e.g. Roblox) with window messages, so it can sit on another screen or behind your work while you use your PC. Settings → Background.
- **Background test** button: jump, walk forward 1 s and click 3 times in the chosen window while another window is in front, so you can see whether your game accepts background input. Try it with "Make the window think it's active" on and off.
- Clicks are now also recorded relative to the game window, so background clicks land in the right spot even after you move the window to another screen.
- **New magenta colours** (violet is reserved for UbiClipper). UbiMacro is now part of the Ubi design system.

## 1.1.0

- **Türkçe** language, plus English. Picks your Windows language the first time; switch any time in Settings.
- **Event editor** (new Events tab): change an event's time or the pause before it, remove the start delay, shorten long pauses, delete, and undo with Ctrl+Z.
- The delay before the first event is now removed automatically after recording (can be turned off).
- **New look** on the Ubi design system: Ubi fonts, violet accent, status hero card, toasts.
- **Dark and light theme** (or follow Windows), with a quick toggle at the top.
- **Settings tab** for language, theme, hotkeys, recording, playback and window options.
- Pressing Play in the window now **switches to Roblox** first (falls back to a countdown).
- **Stop after X minutes** time limit for playback.
- "Clear" asks for a second click instead of a dialog, and Undo brings the macro back.
- Decimal commas work in number fields (`0,5`).

## 1.0.0

- Record keyboard and mouse, replay on F8/F6 hotkeys, loops, speed, humanize, save/load, Anti-AFK preset.
