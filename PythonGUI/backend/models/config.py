from __future__ import annotations

from pydantic import BaseModel, Field

DEFAULT_SERIAL_TIMEOUT_S = 0.1
DEFAULT_TOTAL_SAMPLE_COUNT = 3694
DEFAULT_EFFECTIVE_START_INDEX = 32
DEFAULT_EFFECTIVE_SAMPLE_COUNT = 3648
DEFAULT_TRAILING_DUMMY_COUNT = 14
DEFAULT_ADC_RESOLUTION_BITS = 12
DEFAULT_ADC_REFERENCE_VOLTS = 3.3
DEFAULT_UI_REFRESH_INTERVAL_MS = 8
DEFAULT_MAX_SESSION_FRAMES = 500
DEFAULT_WAVELENGTH_COEFFICIENTS = [0.0, 1.0]


class SerialConfig(BaseModel):
    """Purpose: store serial connection settings. Rationale: COM-port behavior should be configurable without code changes."""
    port: str | None = None
    timeout_s: float = DEFAULT_SERIAL_TIMEOUT_S
    reconnect_on_start: bool = False


class DeviceConfig(BaseModel):
    """Purpose: describe the expected CCD frame layout and ADC properties. Rationale: stream parsing depends on fixed geometry."""
    sample_count: int = DEFAULT_TOTAL_SAMPLE_COUNT
    effective_start_index: int = DEFAULT_EFFECTIVE_START_INDEX
    effective_sample_count: int = DEFAULT_EFFECTIVE_SAMPLE_COUNT
    trailing_dummy_count: int = DEFAULT_TRAILING_DUMMY_COUNT
    adc_resolution_bits: int = DEFAULT_ADC_RESOLUTION_BITS
    adc_reference_volts: float = DEFAULT_ADC_REFERENCE_VOLTS


class UIConfig(BaseModel):
    """Purpose: store UI timing and session buffer settings. Rationale: performance-related choices should be easy to tune."""
    refresh_interval_ms: int = DEFAULT_UI_REFRESH_INTERVAL_MS
    max_session_frames: int = DEFAULT_MAX_SESSION_FRAMES


class UserConfig(BaseModel):
    """Purpose: group user-editable app settings together. Rationale: loading and saving is simpler with one top-level object."""
    serial: SerialConfig = Field(default_factory=SerialConfig)
    device: DeviceConfig = Field(default_factory=DeviceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)


class CalibrationConfig(BaseModel):
    """Purpose: store calibration choices and correction arrays. Rationale: signal correction should be data-driven, not hard-coded."""
    apply_dark_subtraction: bool = True
    apply_intensity_correction: bool = True
    wavelength_coefficients: list[float] = Field(default_factory=lambda: list(DEFAULT_WAVELENGTH_COEFFICIENTS))
    dark_offset_counts: list[float] = Field(default_factory=list)
    intensity_correction: list[float] = Field(default_factory=list)
