from __future__ import annotations

from backend.models.config import DeviceConfig
from backend.models.frames import SpectrumFrame, StatusPacket
from backend.processing.calibration_manager import CalibrationManager


class SpectrumBuilder:
    def __init__(
        self,
        calibration_manager: CalibrationManager,
        device_config: DeviceConfig,
    ) -> None:
        self._calibration_manager = calibration_manager
        self._device_config = device_config

    def update_device_config(self, device_config: DeviceConfig) -> None:
        self._device_config = device_config

    def build_from_status_packet(self, packet: StatusPacket) -> SpectrumFrame:
        sample_indices = list(range(len(packet.sample_preview)))
        wavelengths, volts, intensity = self._calibration_manager.apply(
            sample_indices=sample_indices,
            adc_counts=packet.sample_preview,
            device_config=self._device_config,
        )

        return SpectrumFrame(
            frame_id=packet.frame_counter,
            timestamp=packet.timestamp,
            source="status_preview",
            expected_sample_count=self._device_config.sample_count,
            sample_indices=sample_indices,
            adc_counts=list(packet.sample_preview),
            volts=volts.tolist(),
            wavelengths_nm=wavelengths.tolist(),
            processed_intensity=intensity.tolist(),
            notes=(
                "Current STM32 firmware streams a 4-sample ASCII preview over USB CDC. "
                "Swap in a full-frame packet parser when the MCU begins sending all "
                f"{self._device_config.sample_count} pixels."
            ),
        )
