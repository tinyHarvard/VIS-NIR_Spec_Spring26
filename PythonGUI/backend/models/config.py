from __future__ import annotations

from pydantic import BaseModel, Field


class SerialConfig(BaseModel):
    port: str | None = None
    baudrate: int = 115200
    timeout_s: float = 0.1
    reconnect_on_start: bool = False


class DeviceConfig(BaseModel):
    sample_count: int = 3694
    preview_points: int = 4
    adc_resolution_bits: int = 12
    adc_reference_volts: float = 3.3


class UIConfig(BaseModel):
    refresh_interval_ms: int = 500
    max_session_frames: int = 2000


class UserConfig(BaseModel):
    serial: SerialConfig = Field(default_factory=SerialConfig)
    device: DeviceConfig = Field(default_factory=DeviceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


class CalibrationConfig(BaseModel):
    apply_dark_subtraction: bool = True
    apply_intensity_correction: bool = True
    wavelength_coefficients: list[float] = Field(default_factory=lambda: [0.0, 1.0])
    dark_offset_counts: list[float] = Field(default_factory=list)
    intensity_correction: list[float] = Field(default_factory=list)
