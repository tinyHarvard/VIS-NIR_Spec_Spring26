from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from nicegui import ui

from backend.api.routes import build_api_router
from backend.api.websocket import build_websocket_router
from backend.core.command_service import CommandService
from backend.core.session_manager import SessionManager
from backend.core.state_manager import StateManager
from backend.device.serial_transport import SerialTransport
from backend.processing.calibration_manager import CalibrationManager
from backend.processing.spectrum_builder import SpectrumBuilder
from backend.storage.calibration_store import CalibrationStore
from backend.storage.config_store import ConfigStore
from frontend.nicegui_app import build_ui

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

LOGGER = logging.getLogger("vis_nir_spec")
PROJECT_ROOT = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    config_store = ConfigStore(
        default_path=PROJECT_ROOT / "configs" / "default_user.json",
        active_path=PROJECT_ROOT / "configs" / "user.json",
    )
    calibration_store = CalibrationStore(
        default_path=PROJECT_ROOT / "configs" / "default_calibration.json",
        active_path=PROJECT_ROOT / "configs" / "calibration.json",
    )

    user_config = config_store.load()
    calibration_config = calibration_store.load()

    state_manager = StateManager(
        user_config=user_config,
        calibration_config=calibration_config,
    )
    session_manager = SessionManager(
        export_dir=PROJECT_ROOT / "exports",
        max_frames=user_config.ui.max_session_frames,
    )
    calibration_manager = CalibrationManager(calibration_config)
    spectrum_builder = SpectrumBuilder(calibration_manager, user_config.device)
    transport = SerialTransport()
    command_service = CommandService(
        state_manager=state_manager,
        session_manager=session_manager,
        transport=transport,
        calibration_manager=calibration_manager,
        spectrum_builder=spectrum_builder,
        logger=LOGGER,
    )
    state_manager.set_session_status(session_manager.status())

    app = FastAPI(title="VIS-NIR Spectrometer Control")
    app.include_router(
        build_api_router(
            state_manager=state_manager,
            command_service=command_service,
            session_manager=session_manager,
            config_store=config_store,
            calibration_store=calibration_store,
        )
    )
    app.include_router(build_websocket_router(state_manager))

    app.state.state_manager = state_manager
    app.state.session_manager = session_manager
    app.state.command_service = command_service

    build_ui(
        state_manager=state_manager,
        command_service=command_service,
        session_manager=session_manager,
        config_store=config_store,
        calibration_store=calibration_store,
    )
    ui.run_with(app, storage_secret="vis-nir-spec-storage")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8080, reload=False)
