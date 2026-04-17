from __future__ import annotations

import json
from pathlib import Path

from backend.models.config import CalibrationConfig


class CalibrationStore:
    """Purpose: load and save calibration JSON files. Rationale: calibration persistence should follow the same pattern as user settings."""
    def __init__(self, default_path: Path, active_path: Path) -> None:
        """Purpose: remember calibration file locations. Rationale: defaults and active overrides should be handled in one place."""
        self._default_path = default_path
        self._active_path = active_path

    def load(self) -> CalibrationConfig:
        """Purpose: load calibration settings from disk. Rationale: saved user calibrations should override packaged defaults."""
        path = self._active_path if self._active_path.exists() else self._default_path
        data = json.loads(path.read_text(encoding="utf-8"))
        return CalibrationConfig.model_validate(data)

    def save(self, config: CalibrationConfig) -> Path:
        """Purpose: save calibration settings to disk. Rationale: calibration edits should survive restarts and standalone builds."""
        self._active_path.parent.mkdir(parents=True, exist_ok=True)
        self._active_path.write_text(
            json.dumps(config.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return self._active_path
