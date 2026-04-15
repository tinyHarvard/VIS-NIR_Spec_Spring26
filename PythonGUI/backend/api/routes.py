from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.core.command_service import CommandService
from backend.core.session_manager import SessionManager
from backend.core.state_manager import StateManager
from backend.models.config import CalibrationConfig, UserConfig
from backend.storage.calibration_store import CalibrationStore
from backend.storage.config_store import ConfigStore


class ConnectRequest(BaseModel):
    port: str | None = None
    baudrate: int | None = None


class RawCommandRequest(BaseModel):
    text: str


def build_api_router(
    *,
    state_manager: StateManager,
    command_service: CommandService,
    session_manager: SessionManager,
    config_store: ConfigStore,
    calibration_store: CalibrationStore,
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["spectrometer"])

    @router.get("/status")
    def get_status() -> dict:
        return state_manager.snapshot().model_dump(mode="json")

    @router.get("/ports")
    def get_ports() -> list[dict[str, str]]:
        return command_service.list_serial_ports()

    @router.post("/connect")
    def connect_device(request: ConnectRequest | None = None) -> dict:
        payload = request or ConnectRequest()
        result = command_service.connect(port=payload.port, baudrate=payload.baudrate)
        return result.model_dump(mode="json")

    @router.post("/disconnect")
    def disconnect_device() -> dict:
        return command_service.disconnect().model_dump(mode="json")

    @router.post("/commands/raw")
    def send_raw_command(request: RawCommandRequest) -> dict:
        return command_service.send_raw_command(request.text).model_dump(mode="json")

    @router.get("/session")
    def get_session() -> dict:
        return session_manager.status().model_dump(mode="json")

    @router.post("/session/reset")
    def reset_session() -> dict:
        session_manager.reset()
        command_service.refresh_session_status()
        return {
            "ok": True,
            "session": session_manager.status().model_dump(mode="json"),
        }

    @router.post("/session/export")
    def export_session() -> dict:
        path = session_manager.export_csv()
        command_service.refresh_session_status()
        return {
            "ok": True,
            "path": str(path),
            "session": session_manager.status().model_dump(mode="json"),
        }

    @router.get("/config/user")
    def get_user_config() -> dict:
        return state_manager.get_user_config().model_dump(mode="json")

    @router.put("/config/user")
    def save_user_config(config: UserConfig) -> dict:
        path = config_store.save(config)
        command_service.apply_user_config(config)
        return {
            "ok": True,
            "path": str(path),
            "config": config.model_dump(mode="json"),
        }

    @router.get("/config/calibration")
    def get_calibration_config() -> dict:
        return state_manager.get_calibration_config().model_dump(mode="json")

    @router.put("/config/calibration")
    def save_calibration_config(config: CalibrationConfig) -> dict:
        path = calibration_store.save(config)
        command_service.apply_calibration_config(config)
        return {
            "ok": True,
            "path": str(path),
            "config": config.model_dump(mode="json"),
        }

    return router
