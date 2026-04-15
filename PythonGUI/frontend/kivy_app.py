from __future__ import annotations

from collections import deque
from time import perf_counter
from typing import Sequence

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from backend.core.runtime import AppRuntime
from backend.models.config import CalibrationConfig


class Card(BoxLayout):
    def __init__(self, **kwargs) -> None:
        super().__init__(orientation="vertical", spacing=dp(8), padding=dp(12), **kwargs)
        with self.canvas.before:
            Color(0.97, 0.95, 0.90, 0.96)
            self._background = RoundedRectangle(radius=[18])
        self.bind(pos=self._update_background, size=self._update_background)

    def _update_background(self, *_args) -> None:
        self._background.pos = self.pos
        self._background.size = self.size


class SpectrumPlot(Widget):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._x_values: Sequence[int] = ()
        self._y_values: Sequence[int] = ()
        self._adc_min = 0.0
        self._adc_max = 4095.0
        self.bind(pos=self._redraw, size=self._redraw)

    def set_series(self, x_values: Sequence[int], y_values: Sequence[int]) -> None:
        self._x_values = x_values
        self._y_values = y_values
        self._redraw()

    def set_adc_range(self, adc_min: int, adc_max: int) -> None:
        self._adc_min = float(adc_min)
        self._adc_max = float(max(adc_max, adc_min + 1))
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.clear()
        with self.canvas:
            Color(1.0, 0.995, 0.975, 1.0)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[16])

            Color(0.82, 0.78, 0.69, 1.0)
            Line(rounded_rectangle=[self.x, self.y, self.width, self.height, 16], width=1.0)

            if not self._x_values or not self._y_values or self.width <= dp(24) or self.height <= dp(24):
                return

            left = self.x + dp(12)
            bottom = self.y + dp(12)
            plot_width = max(self.width - dp(24), 1.0)
            plot_height = max(self.height - dp(24), 1.0)

            points: list[float] = []
            x_min = float(self._x_values[0])
            x_max = float(self._x_values[-1]) if len(self._x_values) > 1 else float(self._x_values[0] + 1)
            if x_max <= x_min:
                x_max = x_min + 1.0
            x_scale = plot_width / (x_max - x_min)
            y_scale = plot_height / (self._adc_max - self._adc_min)

            for x_value, sample in zip(self._x_values, self._y_values):
                clamped_sample = min(max(float(sample), self._adc_min), self._adc_max)
                x_pos = left + ((float(x_value) - x_min) * x_scale)
                y_pos = bottom + ((clamped_sample - self._adc_min) * y_scale)
                points.extend((x_pos, y_pos))

            Color(0.82, 0.86, 0.82, 0.8)
            mid_y = bottom + (plot_height * 0.5)
            Line(points=[left, bottom, left + plot_width, bottom], width=1.0)
            Line(points=[left, mid_y, left + plot_width, mid_y], width=1.0)
            Line(points=[left, bottom + plot_height, left + plot_width, bottom + plot_height], width=1.0)
            Line(points=[left, bottom, left, bottom + plot_height], width=1.0)

            Color(0.06, 0.46, 0.43, 1.0)
            for chunk in self._iter_line_chunks(points, max_vertices=384):
                Line(points=chunk, width=1.2)

    @staticmethod
    def _iter_line_chunks(points: list[float], *, max_vertices: int) -> list[list[float]]:
        if len(points) <= max_vertices * 2:
            return [points]

        chunks: list[list[float]] = []
        step = max(2, max_vertices * 2)
        start = 0
        last_pair_start = len(points) - 2

        while start < len(points):
            end = min(start + step, len(points))
            chunk = points[start:end]
            if start > 0:
                chunk = points[start - 2:start] + chunk
            if len(chunk) >= 4:
                chunks.append(chunk)
            if end >= len(points):
                break
            start = min(end, last_pair_start)

        return chunks or [points]


class DesktopSpectrometerApp(App):
    def __init__(self, runtime: AppRuntime, **kwargs) -> None:
        super().__init__(**kwargs)
        self.runtime = runtime
        self.title = "VIS-NIR Spectrometer"
        self.port_spinner: Spinner | None = None
        self.baud_input: TextInput | None = None
        self.command_input: TextInput | None = None
        self.wavelength_input: TextInput | None = None
        self.dark_checkbox: CheckBox | None = None
        self.intensity_checkbox: CheckBox | None = None
        self.status_label: Label | None = None
        self.banner_label: Label | None = None
        self.stream_label: Label | None = None
        self.frame_label: Label | None = None
        self.layout_label: Label | None = None
        self.edge_label: Label | None = None
        self.refresh_rate_label: Label | None = None
        self.session_label: Label | None = None
        self.notice_label: Label | None = None
        self.log_area: TextInput | None = None
        self.plot: SpectrumPlot | None = None
        self.plot_y_max_label: Label | None = None
        self.plot_y_mid_label: Label | None = None
        self.plot_y_min_label: Label | None = None
        self.plot_x_start_label: Label | None = None
        self.plot_x_mid_label: Label | None = None
        self.plot_x_end_label: Label | None = None
        self._last_plot_signature: tuple[int | None, int, int | None, int | None] | None = None
        self._plot_update_times: deque[float] = deque(maxlen=48)

    def build(self) -> BoxLayout:
        user_config = self.runtime.state_manager.get_user_config()
        calibration_config = self.runtime.state_manager.get_calibration_config()

        root = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            padding=dp(12),
        )

        header = Card(size_hint_y=None, height=dp(96))
        header.add_widget(
            Label(
                text="[b]VIS-NIR Spectrometer[/b]",
                markup=True,
                font_size="24sp",
                color=(0.13, 0.19, 0.24, 1.0),
                size_hint_y=None,
                height=dp(40),
                halign="left",
                valign="middle",
            )
        )
        self.notice_label = Label(
            text="Waiting for the spectrometer stream.",
            color=(0.17, 0.21, 0.26, 1.0),
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=dp(28),
        )
        header.add_widget(self.notice_label)
        root.add_widget(header)

        body = BoxLayout(spacing=dp(12))
        root.add_widget(body)

        left_column = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            size_hint_x=0.34,
        )
        body.add_widget(left_column)

        right_column = BoxLayout(
            orientation="vertical",
            spacing=dp(12),
            size_hint_x=0.66,
        )
        body.add_widget(right_column)

        connection_card = Card()
        connection_card.add_widget(self._section_title("Connection"))
        self.port_spinner = Spinner(
            text=user_config.serial.port or "Select COM Port",
            values=(),
            size_hint_y=None,
            height=dp(38),
        )
        connection_card.add_widget(self.port_spinner)
        self.baud_input = TextInput(
            text=str(user_config.serial.baudrate),
            multiline=False,
            hint_text="Baud rate",
            size_hint_y=None,
            height=dp(38),
        )
        connection_card.add_widget(self.baud_input)
        connection_buttons = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        connection_buttons.add_widget(self._button("Refresh Ports", self.refresh_ports))
        connection_buttons.add_widget(self._button("Connect", self.connect_device))
        connection_buttons.add_widget(self._button("Disconnect", self.disconnect_device))
        connection_card.add_widget(connection_buttons)
        connection_card.add_widget(self._button("Save User Config", self.save_user_config, size_hint_y=None, height=dp(40)))
        self.status_label = self._info_label("Status: disconnected")
        self.banner_label = self._info_label("Firmware: waiting for banner")
        connection_card.add_widget(self.status_label)
        connection_card.add_widget(self.banner_label)
        left_column.add_widget(connection_card)

        calibration_card = Card()
        calibration_card.add_widget(self._section_title("Calibration"))
        self.wavelength_input = TextInput(
            text=", ".join(str(value) for value in calibration_config.wavelength_coefficients),
            multiline=False,
            hint_text="Wavelength coefficients",
            size_hint_y=None,
            height=dp(38),
        )
        calibration_card.add_widget(self.wavelength_input)
        self.dark_checkbox = CheckBox(active=calibration_config.apply_dark_subtraction)
        calibration_card.add_widget(self._checkbox_row("Apply dark subtraction", self.dark_checkbox))
        self.intensity_checkbox = CheckBox(active=calibration_config.apply_intensity_correction)
        calibration_card.add_widget(self._checkbox_row("Apply intensity correction", self.intensity_checkbox))
        calibration_card.add_widget(self._button("Save Calibration", self.save_calibration, size_hint_y=None, height=dp(40)))
        calibration_card.add_widget(
            self._small_label(
                "The desktop plot shows the 3648 effective CCD pixels when full frames are available. "
                "If the device only streams the old 4-sample preview, the app now calls that out directly."
            )
        )
        left_column.add_widget(calibration_card)

        command_card = Card()
        command_card.add_widget(self._section_title("Session And Commands"))
        self.command_input = TextInput(
            text="",
            multiline=False,
            hint_text="Raw USB CDC command",
            size_hint_y=None,
            height=dp(38),
        )
        command_card.add_widget(self.command_input)
        command_card.add_widget(self._button("Send Raw Command", self.send_raw_command, size_hint_y=None, height=dp(40)))
        session_buttons = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        session_buttons.add_widget(self._button("Export Session CSV", self.export_session))
        session_buttons.add_widget(self._button("Reset Session", self.reset_session))
        command_card.add_widget(session_buttons)
        left_column.add_widget(command_card)

        plot_card = Card()
        plot_card.add_widget(self._section_title("Live Spectrum"))
        self.stream_label = Label(
            text="[color=#6b7280]Waiting for data stream[/color]",
            markup=True,
            size_hint_y=None,
            height=dp(28),
            halign="left",
            valign="middle",
        )
        plot_card.add_widget(self.stream_label)
        plot_shell = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=1.0)
        y_axis_column = BoxLayout(
            orientation="vertical",
            spacing=dp(0),
            size_hint_x=None,
            width=dp(58),
        )
        self.plot_y_max_label = self._axis_label("4095", valign="top")
        self.plot_y_mid_label = self._axis_label("2048", valign="middle")
        self.plot_y_min_label = self._axis_label("0", valign="bottom")
        y_axis_column.add_widget(self.plot_y_max_label)
        y_axis_column.add_widget(Widget())
        y_axis_column.add_widget(self.plot_y_mid_label)
        y_axis_column.add_widget(Widget())
        y_axis_column.add_widget(self.plot_y_min_label)
        plot_shell.add_widget(y_axis_column)

        plot_column = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=1.0)
        self.plot = SpectrumPlot(size_hint_y=1.0)
        adc_max_count = (1 << user_config.device.adc_resolution_bits) - 1
        self.plot.set_adc_range(0, adc_max_count)
        plot_column.add_widget(self.plot)

        x_axis_row = BoxLayout(size_hint_y=None, height=dp(20))
        self.plot_x_start_label = self._axis_label("0", halign="left")
        self.plot_x_mid_label = self._axis_label("0", halign="center")
        self.plot_x_end_label = self._axis_label("0", halign="right")
        x_axis_row.add_widget(self.plot_x_start_label)
        x_axis_row.add_widget(self.plot_x_mid_label)
        x_axis_row.add_widget(self.plot_x_end_label)
        plot_column.add_widget(x_axis_row)

        plot_shell.add_widget(plot_column)
        plot_card.add_widget(plot_shell)
        self.frame_label = self._info_label("Frame: n/a")
        self.layout_label = self._info_label("Layout: n/a")
        self.edge_label = self._info_label("Edge samples: n/a")
        self.refresh_rate_label = self._info_label("Graph Refresh: n/a")
        self.session_label = self._info_label("Session: n/a")
        plot_card.add_widget(self.frame_label)
        plot_card.add_widget(self.layout_label)
        plot_card.add_widget(self.edge_label)
        plot_card.add_widget(self.refresh_rate_label)
        plot_card.add_widget(self.session_label)
        right_column.add_widget(plot_card)

        log_card = Card(size_hint_y=0.34)
        log_card.add_widget(self._section_title("Diagnostics"))
        self.log_area = TextInput(readonly=True, multiline=True)
        log_card.add_widget(self.log_area)
        right_column.add_widget(log_card)

        return root

    def on_start(self) -> None:
        self.refresh_ports()
        plot_refresh_s = min(
            max(self.runtime.state_manager.get_user_config().ui.refresh_interval_ms / 1000.0, 0.001),
            1.0 / 125.0,
        )
        status_refresh_s = max(0.1, plot_refresh_s * 12.0)
        Clock.schedule_interval(self.refresh_plot, plot_refresh_s)
        Clock.schedule_interval(self.refresh_status, status_refresh_s)
        self.refresh_view()
        if self.runtime.state_manager.get_user_config().serial.reconnect_on_start:
            Clock.schedule_once(lambda *_args: self.connect_device(), 0.1)
        try:
            from kivy.core.window import Window

            Window.maximize()
        except Exception:
            pass

    def on_stop(self) -> None:
        if self.runtime.transport.is_connected():
            self.runtime.command_service.disconnect()

    def refresh_ports(self, *_args) -> None:
        ports = self.runtime.command_service.list_serial_ports()
        devices = [item["device"] for item in ports]
        if self.port_spinner is None:
            return

        self.port_spinner.values = devices
        remembered = self.runtime.state_manager.get_user_config().serial.port
        current = self.port_spinner.text if self.port_spinner.text in devices else None
        if remembered in devices:
            self.port_spinner.text = remembered
        elif current is not None:
            self.port_spinner.text = current
        elif devices:
            self.port_spinner.text = devices[0]
        else:
            self.port_spinner.text = "No COM Ports Found"

        self.set_notice(f"Detected {len(devices)} serial port(s).")

    def connect_device(self, *_args) -> None:
        port = None if self.port_spinner is None else self.port_spinner.text
        if port == "No COM Ports Found":
            port = None
        baudrate = 115200
        if self.baud_input is not None:
            try:
                baudrate = int(self.baud_input.text.strip() or "115200")
            except ValueError:
                self.set_notice("Baud rate must be an integer.")
                return

        result = self.runtime.command_service.connect(port=port, baudrate=baudrate)
        self.set_notice(result.message)
        self.refresh_view()

    def disconnect_device(self, *_args) -> None:
        result = self.runtime.command_service.disconnect()
        self.set_notice(result.message)
        self.refresh_view()

    def save_user_config(self, *_args) -> None:
        if self.port_spinner is None or self.baud_input is None:
            return

        config = self.runtime.state_manager.get_user_config()
        config.serial.port = None if self.port_spinner.text == "No COM Ports Found" else self.port_spinner.text
        try:
            config.serial.baudrate = int(self.baud_input.text.strip() or str(config.serial.baudrate))
        except ValueError:
            self.set_notice("Baud rate must be an integer.")
            return

        path = self.runtime.config_store.save(config)
        self.runtime.command_service.apply_user_config(config)
        self.set_notice(f"Saved user config to {path}.")

    def save_calibration(self, *_args) -> None:
        if (
            self.wavelength_input is None
            or self.dark_checkbox is None
            or self.intensity_checkbox is None
        ):
            return

        try:
            coefficients = [
                float(part.strip())
                for part in self.wavelength_input.text.split(",")
                if part.strip()
            ]
        except ValueError:
            self.set_notice("Calibration coefficients must be comma-separated numbers.")
            return

        existing = self.runtime.state_manager.get_calibration_config()
        config = CalibrationConfig(
            apply_dark_subtraction=bool(self.dark_checkbox.active),
            apply_intensity_correction=bool(self.intensity_checkbox.active),
            wavelength_coefficients=coefficients,
            dark_offset_counts=existing.dark_offset_counts,
            intensity_correction=existing.intensity_correction,
        )
        path = self.runtime.calibration_store.save(config)
        self.runtime.command_service.apply_calibration_config(config)
        self.set_notice(f"Saved calibration config to {path}.")

    def export_session(self, *_args) -> None:
        path = self.runtime.session_manager.export_csv()
        self.runtime.command_service.refresh_session_status()
        self.set_notice(f"Exported session to {path}.")
        self.refresh_view()

    def reset_session(self, *_args) -> None:
        self.runtime.session_manager.reset()
        self.runtime.command_service.refresh_session_status()
        self.set_notice("Session buffer cleared.")
        self.refresh_view()

    def send_raw_command(self, *_args) -> None:
        if self.command_input is None:
            return
        result = self.runtime.command_service.send_raw_command(self.command_input.text)
        self.set_notice(result.message)
        self.refresh_view()

    def refresh_status(self, *_args) -> None:
        snapshot = self.runtime.state_manager.snapshot(include_spectrum=False)

        if self.status_label is not None:
            port_text = snapshot.device.port or ""
            self.status_label.text = f"Status: {snapshot.device.connection_state.value} {port_text}".strip()

        if self.banner_label is not None:
            banner_text = (
                snapshot.device.firmware_messages[-1]
                if snapshot.device.firmware_messages
                else "waiting for banner"
            )
            self.banner_label.text = f"Firmware: {banner_text}"

        if self.frame_label is not None:
            self.frame_label.text = (
                f"Frame: {snapshot.device.frame_counter} | samples={snapshot.device.sample_count} "
                f"| missed={snapshot.device.missed_frames} | flags=0x{snapshot.device.last_frame_flags:04X}"
            )

        if self.session_label is not None:
            self.session_label.text = (
                f"Session {snapshot.session.session_id} | buffered={snapshot.session.frames_buffered} "
                f"| dropped={snapshot.session.dropped_frames}"
            )

        if self.edge_label is not None:
            self.edge_label.text = f"Edge samples: {snapshot.device.sample_preview or 'n/a'}"

        if self.log_area is not None:
            self.log_area.text = "\n".join(snapshot.logs[-20:])

    def refresh_plot(self, *_args) -> None:
        spectrum = self.runtime.state_manager.latest_spectrum()
        device_config = self.runtime.state_manager.get_user_config().device
        expected_samples = device_config.sample_count
        adc_max_count = (1 << device_config.adc_resolution_bits) - 1
        effective_start_default = device_config.effective_start_index
        effective_end_default = max(
            effective_start_default + device_config.effective_sample_count - 1,
            effective_start_default,
        )

        display_indices: list[int] = []
        display_values: list[int] = []
        layout_text = "Layout: waiting for stream"
        stream_markup = "[color=#6b7280]Waiting for data stream[/color]"

        if spectrum is not None:
            total_samples = len(spectrum.adc_counts)
            full_frame_ready = total_samples >= expected_samples

            if full_frame_ready:
                start = spectrum.effective_start_index
                end = min(
                    start + spectrum.effective_sample_count,
                    total_samples,
                )
                display_indices = range(start, end)
                display_values = spectrum.adc_counts[start:end]
                stream_markup = (
                    "[color=#1c7c54]Full-frame stream detected[/color]  "
                    f"Plotting effective pixels {start} to {max(end - 1, start)}."
                )
                layout_text = (
                    f"Layout: total={total_samples} | effective={len(display_values)} "
                    f"| leading dummy={start} | trailing dummy={max(total_samples - end, 0)}"
                )
            else:
                display_indices = range(total_samples)
                display_values = spectrum.adc_counts
                stream_markup = (
                    "[color=#bb3e03]Preview-only stream detected[/color]  "
                    f"The STM32 is sending {total_samples} samples, not {expected_samples}. "
                    "Flash the updated firmware to view the full 3694-pixel line."
                )
                layout_text = (
                    f"Layout: preview stream with {total_samples} samples received. "
                    "The app is plotting exactly what the device sent."
                )

            if display_values:
                saturated_samples = sum(1 for value in display_values if value >= adc_max_count)
                if saturated_samples > 0:
                    stream_markup += (
                        "  "
                        f"[color=#b91c1c]{saturated_samples} sample(s) are pinned at the ADC maximum.[/color]"
                    )

        if self.stream_label is not None:
            self.stream_label.text = stream_markup
        if self.layout_label is not None:
            self.layout_label.text = layout_text
        if self.plot_y_max_label is not None:
            self.plot_y_max_label.text = str(adc_max_count)
        if self.plot_y_mid_label is not None:
            self.plot_y_mid_label.text = str(adc_max_count // 2)
        if self.plot_y_min_label is not None:
            self.plot_y_min_label.text = "0"
        if display_indices:
            x_start = display_indices[0]
            x_mid = display_indices[len(display_indices) // 2]
            x_end = display_indices[-1]
        else:
            x_start = effective_start_default
            x_mid = (effective_start_default + effective_end_default) // 2
            x_end = effective_end_default
        if self.plot_x_start_label is not None:
            self.plot_x_start_label.text = str(x_start)
        if self.plot_x_mid_label is not None:
            self.plot_x_mid_label.text = str(x_mid)
        if self.plot_x_end_label is not None:
            self.plot_x_end_label.text = str(x_end)
        if self.plot is not None:
            self.plot.set_adc_range(0, adc_max_count)
            plot_signature = (
                spectrum.frame_id if spectrum is not None else None,
                len(display_values),
                display_indices[0] if display_indices else None,
                display_indices[-1] if display_indices else None,
            )
            if plot_signature != self._last_plot_signature:
                self.plot.set_series(display_indices, display_values)
                self._last_plot_signature = plot_signature
                self._record_plot_update()
        if self.refresh_rate_label is not None:
            refresh_hz = self._current_plot_refresh_hz()
            self.refresh_rate_label.text = (
                f"Graph Refresh: {refresh_hz:.1f} Hz"
                if refresh_hz > 0.0
                else "Graph Refresh: n/a"
            )

    def refresh_view(self, *_args) -> None:
        self.refresh_status()
        self.refresh_plot()

    def _record_plot_update(self) -> None:
        self._plot_update_times.append(perf_counter())

    def _current_plot_refresh_hz(self) -> float:
        if len(self._plot_update_times) < 2:
            return 0.0

        newest = self._plot_update_times[-1]
        oldest = self._plot_update_times[0]
        if perf_counter() - newest > 0.25:
            return 0.0

        elapsed_s = newest - oldest
        if elapsed_s <= 0.0:
            return 0.0

        return (len(self._plot_update_times) - 1) / elapsed_s

    def set_notice(self, message: str) -> None:
        if self.notice_label is not None:
            self.notice_label.text = message

    @staticmethod
    def _section_title(text: str) -> Label:
        return Label(
            text=f"[b]{text}[/b]",
            markup=True,
            font_size="18sp",
            color=(0.13, 0.19, 0.24, 1.0),
            size_hint_y=None,
            height=dp(28),
            halign="left",
            valign="middle",
        )

    @staticmethod
    def _info_label(text: str) -> Label:
        return Label(
            text=text,
            color=(0.16, 0.20, 0.24, 1.0),
            size_hint_y=None,
            height=dp(24),
            halign="left",
            valign="middle",
        )

    @staticmethod
    def _small_label(text: str) -> Label:
        return Label(
            text=text,
            color=(0.28, 0.32, 0.36, 1.0),
            font_size="12sp",
            size_hint_y=None,
            height=dp(56),
            halign="left",
            valign="top",
        )

    @staticmethod
    def _axis_label(
        text: str,
        *,
        halign: str = "right",
        valign: str = "middle",
    ) -> Label:
        return Label(
            text=text,
            color=(0.28, 0.32, 0.36, 1.0),
            font_size="11sp",
            halign=halign,
            valign=valign,
        )

    @staticmethod
    def _button(text: str, handler, **kwargs) -> Button:
        button = Button(
            text=text,
            background_normal="",
            background_color=(0.06, 0.46, 0.43, 1.0),
            color=(1.0, 1.0, 1.0, 1.0),
            **kwargs,
        )
        button.bind(on_release=handler)
        return button

    @staticmethod
    def _checkbox_row(text: str, checkbox: CheckBox) -> BoxLayout:
        row = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(8))
        row.add_widget(checkbox)
        row.add_widget(
            Label(
                text=text,
                color=(0.16, 0.20, 0.24, 1.0),
                halign="left",
                valign="middle",
            )
        )
        return row


def run_desktop_app(runtime: AppRuntime) -> None:
    DesktopSpectrometerApp(runtime).run()
