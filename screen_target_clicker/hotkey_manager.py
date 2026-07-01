"""Global hotkey registration for start/stop toggle."""

from __future__ import annotations

import threading
from collections.abc import Callable


class HotkeyManager:
    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._combo: str | None = None
        self._using_keyboard = False

    @property
    def combo(self) -> str | None:
        return self._combo

    def register(self, combo: str) -> tuple[bool, str]:
        """Register a global hotkey. Returns (success, message)."""
        self.unregister()
        combo = combo.strip().lower()
        if not combo:
            return False, "No hotkey specified."

        try:
            import keyboard

            keyboard.add_hotkey(combo, self._invoke, suppress=False)
            self._combo = combo
            self._using_keyboard = True
            return True, f"Hotkey set: {format_hotkey(combo)}"
        except ImportError:
            return False, "Install the 'keyboard' package for global hotkeys."
        except Exception as exc:
            return False, f"Could not register hotkey: {exc}"

    def unregister(self) -> None:
        if not self._combo or not self._using_keyboard:
            self._combo = None
            return
        try:
            import keyboard

            keyboard.remove_hotkey(self._combo)
        except Exception:
            pass
        self._combo = None
        self._using_keyboard = False

    def _invoke(self) -> None:
        self._callback()

    @staticmethod
    def capture_async(on_result: Callable[[str | None, str | None], None]) -> None:
        """Listen for the next key combination in a background thread."""

        def worker() -> None:
            try:
                import keyboard

                combo = keyboard.read_hotkey(suppress=False)
                on_result(combo, None)
            except ImportError:
                on_result(None, "Install the 'keyboard' package for hotkey capture.")
            except Exception as exc:
                on_result(None, str(exc))

        threading.Thread(target=worker, daemon=True).start()


def format_hotkey(combo: str) -> str:
    parts = [part.strip().upper() for part in combo.split("+") if part.strip()]
    return " + ".join(parts)
