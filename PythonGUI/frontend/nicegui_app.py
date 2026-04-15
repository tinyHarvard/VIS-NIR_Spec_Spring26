from __future__ import annotations

from nicegui import ui

from backend.core.command_service import CommandService
from backend.core.session_manager import SessionManager
from backend.core.state_manager import StateManager
from backend.models.config import CalibrationConfig
from backend.storage.calibration_store import CalibrationStore
from backend.storage.config_store import ConfigStore


def parse_float_list(value: str) -> list[float]:
    cleaned = value.strip()
    if not cleaned:
        return []
    return [float(part.strip()) for part in cleaned.split(",") if part.strip()]


def build_ui(
    *,
    state_manager: StateManager,
    command_service: CommandService,
    session_manager: SessionManager,
    config_store: ConfigStore,
    calibration_store: CalibrationStore,
) -> None:
    ui.add_css(
        """
        :root {
            --paper: #f6f1e7;
            --ink: #21313c;
            --accent: #0f766e;
            --line: #d8cfbe;
        }
        body {
            background:
                radial-gradient(circle at top left, #fff9f0 0%, rgba(255, 249, 240, 0.95) 24%, transparent 55%),
                linear-gradient(180deg, #f5efe3 0%, #efe9dd 100%);
            color: var(--ink);
            font-family: "Trebuchet MS", "Segoe UI", sans-serif;
        }
        .glass-card {
            background: rgba(255, 255, 255, 0.78);
            border: 1px solid var(--line);
            border-radius: 18px;
            box-shadow: 0 16px 34px rgba(33, 49, 60, 0.08);
        }
        .metric {
            font-family: "Consolas", "Courier New", monospace;
        }
        """
    )

    @ui.page("/")
    def index() -> None:
        user_config = state_manager.get_user_config()
        calibration_config = state_manager.get_calibration_config()

        with ui.column().classes("w-full items-center gap-4 p-4"):
            with ui.column().classes("glass-card w-full max-w-7xl gap-2 p-6"):
                ui.label("VIS-NIR Spectrometer Console").classes("text-3xl font-bold")
                ui.label(
                    "USB CDC monitor and calibration shell matched to the current STM32 "
                    "ASCII COM-port stream."
                ).classes("text-base")

            with ui.row().classes("w-full max-w-7xl items-stretch gap-4"):
                with ui.column().classes("glass-card w-full max-w-md gap-3 p-5"):
                    ui.label("Connection").classes("text-xl font-semibold")
                    port_select = ui.select(options={}, label="COM Port").props("outlined")
                    baud_input = ui.number(
                        label="Baud",
                        value=user_config.serial.baudrate,
                        format="%.0f",
                    ).props("outlined")
                    with ui.row().classes("gap-2"):
                        ui.button("Refresh Ports", on_click=lambda: refresh_ports()).props("outline")
                        ui.button("Connect", on_click=lambda: connect_device())
                        ui.button("Disconnect", on_click=lambda: disconnect_device()).props("outline")
                    ui.button("Save User Config", on_click=lambda: save_user_config()).props("outline")
                    status_label = ui.label("Status: disconnected").classes("metric text-base")
                    banner_label = ui.label("Firmware: waiting for banner").classes("text-sm")

                with ui.column().classes("glass-card w-full gap-3 p-5"):
                    ui.label("Calibration").classes("text-xl font-semibold")
                    wavelength_input = ui.input(
                        label="Wavelength Coefficients",
                        value=", ".join(str(value) for value in calibration_config.wavelength_coefficients),
                    ).props("outlined")
                    dark_checkbox = ui.checkbox(
                        "Apply dark subtraction",
                        value=calibration_config.apply_dark_subtraction,
                    )
                    intensity_checkbox = ui.checkbox(
                        "Apply intensity correction",
                        value=calibration_config.apply_intensity_correction,
                    )
                    ui.button("Save Calibration", on_click=lambda: save_calibration()).props("outline")
                    ui.label(
                        "Per-pixel dark and intensity arrays can live in the JSON calibration files now. "
                        "The MCU is only sending a 4-point preview, so the UI keeps the editor lightweight."
                    ).classes("text-sm")

            with ui.column().classes("glass-card w-full max-w-7xl gap-3 p-5"):
                ui.label("Live Preview").classes("text-xl font-semibold")
                ui.markdown(
                    "The firmware in "
                    "`CCD-Driver-Code/STM32F411_Basic/Core/Src/main.c` currently sends only "
                    "`frame=... samples=a,b,c,d half=... full=...` text lines, so this chart shows the "
                    "4-sample preview rather than a full 3694-pixel spectrum."
                )
                chart = ui.echart(
                    {
                        "animation": False,
                        "grid": {"left": 48, "right": 16, "top": 18, "bottom": 42},
                        "xAxis": {"type": "category", "name": "Sample / nm", "data": []},
                        "yAxis": {"type": "value", "name": "Intensity"},
                        "series": [
                            {
                                "type": "line",
                                "smooth": True,
                                "showSymbol": True,
                                "symbolSize": 9,
                                "lineStyle": {"width": 3, "color": "#0f766e"},
                                "itemStyle": {"color": "#0f766e"},
                                "areaStyle": {"color": "rgba(15,118,110,0.10)"},
                                "data": [],
                            }
                        ],
                    }
                ).classes("w-full h-96")
                frame_label = ui.label("Frame: n/a").classes("metric text-base")
                preview_label = ui.label("Preview: n/a").classes("metric text-base")
                session_label = ui.label("Session: n/a").classes("metric text-base")

            with ui.row().classes("w-full max-w-7xl items-stretch gap-4"):
                with ui.column().classes("glass-card w-full max-w-md gap-3 p-5"):
                    ui.label("Commands").classes("text-xl font-semibold")
                    command_input = ui.input(
                        label="Raw USB CDC command",
                        placeholder="example: set_integration_us 500",
                    ).props("outlined")
                    ui.button("Send Raw Command", on_click=lambda: send_raw_command())
                    ui.label(
                        "This write path is ready on the PC side, but `CDC_Receive_FS` does not yet feed "
                        "commands into the STM32 application."
                    ).classes("text-sm")
                    with ui.row().classes("gap-2"):
                        ui.button("Export Session CSV", on_click=lambda: export_session()).props("outline")
                        ui.button("Reset Session", on_click=lambda: reset_session()).props("outline")

                with ui.column().classes("glass-card w-full gap-3 p-5"):
                    ui.label("Diagnostics").classes("text-xl font-semibold")
                    log_area = ui.textarea(label="Recent log").props("outlined readonly autogrow")
                    log_area.classes("w-full")

        def refresh_ports() -> None:
            ports = command_service.list_serial_ports()
            port_select.options = {
                item["device"]: (
                    item["device"]
                    if not item.get("description")
                    else f"{item['device']} - {item['description']}"
                )
                for item in ports
            }
            if port_select.options and not port_select.value:
                remembered = state_manager.get_user_config().serial.port
                port_select.value = remembered if remembered in port_select.options else next(iter(port_select.options))
            port_select.update()

        def connect_device() -> None:
            result = command_service.connect(
                port=port_select.value or None,
                baudrate=int(baud_input.value or 115200),
            )
            ui.notify(result.message, type="positive" if result.ok else "negative")

        def disconnect_device() -> None:
            result = command_service.disconnect()
            ui.notify(result.message, type="positive" if result.ok else "negative")

        def save_user_config() -> None:
            config = state_manager.get_user_config()
            config.serial.port = port_select.value or None
            config.serial.baudrate = int(baud_input.value or config.serial.baudrate)
            path = config_store.save(config)
            command_service.apply_user_config(config)
            ui.notify(f"Saved user config to {path}", type="positive")

        def save_calibration() -> None:
            try:
                existing = state_manager.get_calibration_config()
                config = CalibrationConfig(
                    apply_dark_subtraction=bool(dark_checkbox.value),
                    apply_intensity_correction=bool(intensity_checkbox.value),
                    wavelength_coefficients=parse_float_list(str(wavelength_input.value)),
                    dark_offset_counts=existing.dark_offset_counts,
                    intensity_correction=existing.intensity_correction,
                )
            except ValueError:
                ui.notify("Calibration coefficients must be comma-separated numbers.", type="negative")
                return

            path = calibration_store.save(config)
            command_service.apply_calibration_config(config)
            ui.notify(f"Saved calibration config to {path}", type="positive")

        def export_session() -> None:
            path = session_manager.export_csv()
            command_service.refresh_session_status()
            ui.notify(f"Exported session to {path}", type="positive")

        def reset_session() -> None:
            session_manager.reset()
            command_service.refresh_session_status()
            ui.notify("Session buffer cleared.", type="positive")

        def send_raw_command() -> None:
            result = command_service.send_raw_command(str(command_input.value or ""))
            ui.notify(result.message, type="positive" if result.ok else "negative")

        def update_view() -> None:
            snapshot = state_manager.snapshot()
            status_label.text = (
                f"Status: {snapshot.device.connection_state.value} "
                f"{snapshot.device.port or ''}"
            ).strip()
            status_label.update()

            banner_text = (
                snapshot.device.firmware_messages[-1]
                if snapshot.device.firmware_messages
                else "waiting for banner"
            )
            banner_label.text = f"Firmware: {banner_text}"
            banner_label.update()

            frame_label.text = (
                f"Frame: {snapshot.device.frame_counter} | "
                f"half={snapshot.device.dma_half_count} full={snapshot.device.dma_full_count}"
            )
            frame_label.update()

            preview_label.text = f"Preview: {snapshot.device.sample_preview or 'n/a'}"
            preview_label.update()

            session_label.text = (
                f"Session {snapshot.session.session_id} | buffered={snapshot.session.frames_buffered} "
                f"dropped={snapshot.session.dropped_frames}"
            )
            session_label.update()

            if snapshot.spectrum is not None:
                x_values = (
                    [round(value, 3) for value in snapshot.spectrum.wavelengths_nm]
                    if snapshot.spectrum.wavelengths_nm
                    else snapshot.spectrum.sample_indices
                )
                y_values = (
                    [round(value, 6) for value in snapshot.spectrum.processed_intensity]
                    if snapshot.spectrum.processed_intensity
                    else snapshot.spectrum.adc_counts
                )
                chart.options["xAxis"]["data"] = x_values
                chart.options["series"][0]["data"] = y_values
                chart.update()

            log_area.value = "\n".join(snapshot.logs[-20:])
            log_area.update()

        refresh_ports()
        update_view()
        ui.timer(state_manager.get_user_config().ui.refresh_interval_ms / 1000.0, update_view)
