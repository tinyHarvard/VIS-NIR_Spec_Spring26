from __future__ import annotations

import ctypes
import os
from pathlib import Path

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
os.environ.setdefault("KCFG_GRAPHICS_MAXFPS", "125")

from kivy.config import Config

Config.set("graphics", "maxfps", "125")

from backend.core.runtime import build_runtime, configure_logging, resolve_runtime_paths
from frontend.kivy_app import run_desktop_app


def hide_console_window() -> None:
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
    paths = resolve_runtime_paths(Path(__file__).resolve().parent)
    logger = configure_logging(paths.log_file)
    runtime = build_runtime(paths, logger)
    hide_console_window()
    run_desktop_app(runtime)


if __name__ == "__main__":
    main()
