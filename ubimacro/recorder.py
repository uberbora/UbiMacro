"""Records keyboard and mouse events into a timed event list.

Keyboard events are fed in by the app (it owns the single global keyboard
listener so hotkeys work at the same time). The mouse listener is started
here only while recording.
"""

import threading
import time

from .keys import key_id


class Recorder:
    def __init__(self, record_moves=False, move_interval=1 / 60, clock=time.perf_counter):
        self.record_moves = record_moves
        self.move_interval = move_interval
        self._clock = clock
        self._lock = threading.Lock()
        self._events = []
        self._held_keys = {}
        self._held_buttons = {}
        self._t0 = 0.0
        self._last_move = -1.0
        self._mouse_listener = None
        self.active = False

    # ---- lifecycle -------------------------------------------------------
    def start(self, use_mouse_listener=True):
        with self._lock:
            self._events = []
            self._held_keys = {}
            self._held_buttons = {}
            self._t0 = self._clock()
            self._last_move = -1.0
            self.active = True
        if use_mouse_listener:
            from pynput import mouse

            self._mouse_listener = mouse.Listener(
                on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll
            )
            self._mouse_listener.start()

    def stop(self, trim_trailing_clicks=False):
        """Stop recording and return the events.

        ``trim_trailing_clicks`` removes the click(s) used to press the Stop
        button in the app window, so they don't end up in the macro.
        """
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        with self._lock:
            self.active = False
            now = self._now()
            events = self._events
            if trim_trailing_clicks:
                while events and events[-1]["type"] in ("click", "move") and now - events[-1]["t"] < 1.5:
                    ev = events.pop()
                    if ev["type"] == "click":
                        self._held_buttons.pop(ev["button"], None)
            # Close anything still held so playback never leaves keys stuck.
            for k in list(self._held_keys.values()):
                events.append({"t": now, "type": "key", "action": "up", "key": k})
            for b, (x, y) in list(self._held_buttons.items()):
                events.append({"t": now, "type": "click", "action": "up", "button": b, "x": x, "y": y})
            self._held_keys = {}
            self._held_buttons = {}
            self._events = []
            return events

    def _now(self):
        return round(self._clock() - self._t0, 4)

    # ---- inputs ----------------------------------------------------------
    def key(self, keydict, pressed):
        with self._lock:
            if not self.active:
                return
            kid = key_id(keydict)
            if pressed:
                if kid in self._held_keys:  # OS auto-repeat while holding: ignore
                    return
                self._held_keys[kid] = keydict
            else:
                if kid not in self._held_keys:
                    return
                del self._held_keys[kid]
            self._events.append(
                {"t": self._now(), "type": "key", "action": "down" if pressed else "up", "key": keydict}
            )

    def on_click(self, x, y, button, pressed, injected=False):
        if injected:
            return
        name = getattr(button, "name", str(button))
        with self._lock:
            if not self.active:
                return
            if pressed:
                self._held_buttons[name] = (int(x), int(y))
            else:
                self._held_buttons.pop(name, None)
            ev = {
                "t": self._now(),
                "type": "click",
                "action": "down" if pressed else "up",
                "button": name,
                "x": int(x),
                "y": int(y),
            }
            self._events.append(ev)

    def on_move(self, x, y, injected=False):
        if injected or not self.record_moves:
            return
        with self._lock:
            if not self.active:
                return
            t = self._now()
            if t - self._last_move < self.move_interval:
                return
            self._last_move = t
            self._events.append({"t": t, "type": "move", "x": int(x), "y": int(y)})

    def on_scroll(self, x, y, dx, dy, injected=False):
        if injected:
            return
        with self._lock:
            if not self.active:
                return
            self._events.append(
                {"t": self._now(), "type": "scroll", "dx": int(dx), "dy": int(dy), "x": int(x), "y": int(y)}
            )

    @property
    def event_count(self):
        with self._lock:
            return len(self._events)
