from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from backend.core.command_service import CommandService
from backend.core.session_manager import SessionManager
from backend.core.state_manager import StateManager
from backend.device.serial_transport import SerialTransport
from backend.models.config import ensure_pixel_mode_without_mapping
from backend.processing.calibration_manager import CalibrationManager
from backend.processing.spectrum_builder import SpectrumBuilder
from backend.storage.calibration_store import CalibrationStore
from backend.storage.config_store import ConfigStore


@dataclass(frozen=True)
class RuntimePaths:
    """Purpose: hold important runtime filesystem paths. Rationale: startup code should pass one path bundle around."""
    bundle_root: Path
    project_root: Path
    log_dir: Path
    log_file: Path
    is_frozen: bool


@dataclass(frozen=True)
class AppRuntime:
    """Purpose: hold the main application services. Rationale: the entrypoint and UI should receive one wired runtime object."""
    paths: RuntimePaths
    logger: logging.Logger
    config_store: ConfigStore
    calibration_store: CalibrationStore
    state_manager: StateManager
    session_manager: SessionManager
    calibration_manager: CalibrationManager
    spectrum_builder: SpectrumBuilder
    transport: SerialTransport
    command_service: CommandService


def resolve_runtime_paths(app_root: Path) -> RuntimePaths:
    """Purpose: resolve config, log, and project paths. Rationale: source runs and packaged runs store files differently."""
    is_frozen = bool(getattr(sys, "frozen", False))
    bundle_root = Path(getattr(sys, "_MEIPASS", app_root.resolve()))
    project_root = Path(sys.executable).resolve().parent if is_frozen else app_root.resolve()
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return RuntimePaths(
        bundle_root=bundle_root,
        project_root=project_root,
        log_dir=log_dir,
        log_file=log_dir / "vis_nir_spec.log",
        is_frozen=is_frozen,
    )


def configure_logging(log_file: Path) -> logging.Logger:
    """Purpose: configure file and console logging. Rationale: debugging needs one shared logging setup for the whole app."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(stream=sys.stdout),
        ],
        force=True,
    )
    return logging.getLogger("vis_nir_spec")


def build_runtime(paths: RuntimePaths, logger: logging.Logger | None = None) -> AppRuntime:
    """Purpose: create and connect the app services. Rationale: centralizing wiring keeps startup predictable and maintainable."""
    resolved_logger = logger or logging.getLogger("vis_nir_spec")
    config_store = ConfigStore(
        default_path=paths.bundle_root / "configs" / "default_user.json",
        active_path=paths.project_root / "configs" / "user.json",
    )
    calibration_store = CalibrationStore(
        default_path=paths.bundle_root / "configs" / "default_calibration.json",
        active_path=paths.project_root / "configs" / "calibration.json",
    )

    user_config = config_store.load()
    calibration_config = ensure_pixel_mode_without_mapping(calibration_store.load())

    state_manager = StateManager(
        user_config=user_config,
        calibration_config=calibration_config,
    )
    calibration_manager = CalibrationManager(calibration_config)
    spectrum_builder = SpectrumBuilder(calibration_manager, user_config.device)
    session_manager = SessionManager(
        export_dir=paths.project_root / "exports",
        max_frames=user_config.ui.max_session_frames,
        spectrum_builder=spectrum_builder,
    )
    transport = SerialTransport()
    command_service = CommandService(
        state_manager=state_manager,
        session_manager=session_manager,
        transport=transport,
        calibration_manager=calibration_manager,
        spectrum_builder=spectrum_builder,
        logger=resolved_logger,
    )
    state_manager.set_session_status(session_manager.status())

    return AppRuntime(
        paths=paths,
        logger=resolved_logger,
        config_store=config_store,
        calibration_store=calibration_store,
        state_manager=state_manager,
        session_manager=session_manager,
        calibration_manager=calibration_manager,
        spectrum_builder=spectrum_builder,
        transport=transport,
        command_service=command_service,
    )
