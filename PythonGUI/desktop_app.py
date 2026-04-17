from __future__ import annotations

import ctypes
import os
from pathlib import Path

KIVY_NO_ARGS_ENV = "KIVY_NO_ARGS"
KIVY_NO_CONSOLELOG_ENV = "KIVY_NO_CONSOLELOG"
KIVY_MAXFPS_ENV = "KCFG_GRAPHICS_MAXFPS"
DEFAULT_UI_MAX_FPS = "125"

os.environ.setdefault(KIVY_NO_ARGS_ENV, "1")
os.environ.setdefault(KIVY_NO_CONSOLELOG_ENV, "1")
os.environ.setdefault(KIVY_MAXFPS_ENV, DEFAULT_UI_MAX_FPS)

from kivy.config import Config

Config.set("graphics", "maxfps", DEFAULT_UI_MAX_FPS)

from backend.core.runtime import build_runtime, configure_logging, resolve_runtime_paths
from frontend.kivy_app import run_desktop_app


def hide_console_window() -> None:
    """Purpose: hide the extra Windows console. Rationale: keep the desktop app focused on the GUI."""
    if os.name != "nt":
        return

    try:
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        console_window = kernel32.GetConsoleWindow()
        if console_window:
            user32.ShowWindow(console_window, 0)
    except Exception:
        pass


def main() -> None:
    """Purpose: build the runtime and launch the desktop UI. Rationale: keep startup wiring in one clear entrypoint."""
    paths = resolve_runtime_paths(Path(__file__).resolve().parent)
    logger = configure_logging(paths.log_file)
    runtime = build_runtime(paths, logger)
    hide_console_window()
    run_desktop_app(runtime)


if __name__ == "__main__":
    main()
