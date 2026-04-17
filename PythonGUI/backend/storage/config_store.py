from __future__ import annotations

import json
from pathlib import Path

from backend.models.config import UserConfig


class ConfigStore:
    """Purpose: load and save user config JSON files. Rationale: file persistence should stay outside the UI and service code."""
    def __init__(self, default_path: Path, active_path: Path) -> None:
        """Purpose: remember config file locations. Rationale: reads and writes should use the same pair of paths consistently."""
        self._default_path = default_path
        self._active_path = active_path

    def load(self) -> UserConfig:
        """Purpose: load the user config from disk. Rationale: the app should prefer the active config but fall back to defaults."""
        path = self._active_path if self._active_path.exists() else self._default_path
        data = json.loads(path.read_text(encoding="utf-8"))
        return UserConfig.model_validate(data)

    def save(self, config: UserConfig) -> Path:
        """Purpose: save the user config to disk. Rationale: UI changes should persist across app restarts."""
        self._active_path.parent.mkdir(parents=True, exist_ok=True)
        self._active_path.write_text(
            json.dumps(config.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return self._active_path
