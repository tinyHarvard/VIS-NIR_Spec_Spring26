from __future__ import annotations

from collections import deque
from time import perf_counter
from typing import Sequence

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from backend.core.runtime import AppRuntime
from backend.models.config import (
    CalibrationConfig,
    DEFAULT_WAVELENGTH_COEFFICIENTS,
    PixelMappingPoint,
    SpectralResponsePoint,
)
from backend.processing.wavelength_map import indices_to_wavelengths

# Shared layout metrics.
# Format:
# - `*_GAP`, `*_PAD`, `*_HEIGHT`, `*_WIDTH` use Kivy `dp(...)` units so the UI
#   keeps roughly the same physical sizing across displays.
APP_GAP = dp(12)
CARD_GAP = dp(8)
CARD_PAD = dp(12)
CONTROL_HEIGHT = dp(38)
BUTTON_HEIGHT = dp(40)
INFO_LABEL_HEIGHT = dp(24)
SMALL_LABEL_HEIGHT = dp(56)
AXIS_COLUMN_WIDTH = dp(58)
X_AXIS_HEIGHT = dp(20)
CHECKBOX_ROW_HEIGHT = dp(32)
PLOT_INNER_PAD = dp(12)
PLOT_MIN_DRAW_SIZE = dp(24)
NARROW_CONTROL_HEIGHT = dp(34)
NARROW_BUTTON_HEIGHT = dp(36)
NARROW_INFO_LABEL_HEIGHT = dp(34)
NARROW_SMALL_LABEL_HEIGHT = dp(88)
NARROW_CHECKBOX_ROW_HEIGHT = dp(52)
BUTTON_TEXT_PAD_X = dp(10)
BUTTON_TEXT_PAD_Y = dp(6)

# Main layout proportions and breakpoints.
# Format:
# - ratio values are fractional shares of available space and should usually add
#   up to about 1.0 for sibling containers.
# - `RESPONSIVE_BREAKPOINT` is the window width where the app switches from a
#   side-by-side layout to a stacked layout.
SIDEBAR_RATIO_WIDE = 0.28
DETAIL_RATIO_WIDE = 0.72
LOG_RATIO_WIDE = 0.25
RESPONSIVE_BREAKPOINT = dp(1200)
COMPACT_BREAKPOINT = dp(900)
VERY_COMPACT_BREAKPOINT = dp(720)
SHORT_HEIGHT_BREAKPOINT = dp(760)
VERY_SHORT_HEIGHT_BREAKPOINT = dp(620)
BUTTON_STACK_BREAKPOINT = dp(430)

# UI refresh timing.
# Format:
# - values ending in `_S` are seconds.
# - values ending in `_HZ` are refresh-rate caps in updates per second.
MIN_WIDE_STATUS_REFRESH_S = 0.1
MAX_PLOT_REFRESH_HZ = 30.0
PLOT_REFRESH_STALE_S = 0.25

# Responsive-only fallback sizes.
# Format:
# - these are used when the layout is forced into the narrow stacked mode.
NARROW_LOG_CARD_HEIGHT = dp(220)
NOTICE_MIN_TEXT_WIDTH = dp(200)

# Plot rendering controls.
# Format:
# - vertex counts are plain integers.
# - line widths are canvas stroke widths in pixels.
PLOT_CHUNK_MAX_VERTICES = 384
PLOT_LINE_WIDTH = 1.2
PLOT_BORDER_WIDTH = 1.0
GUIDE_LINE_WIDTH = 1.0
PLOT_CURSOR_LINE_WIDTH = 1.0
PLOT_CURSOR_MARKER_SIZE = dp(4)

# Theme colors.
# Format:
# - RGBA tuples use normalized floats from 0.0 to 1.0 in the order
#   `(red, green, blue, alpha)`.
CARD_BACKGROUND_RGBA = (0.97, 0.95, 0.90, 0.96)
APP_BACKGROUND_RGBA = (1.0, 0.995, 0.975, 1.0)
CARD_BORDER_RGBA = (0.82, 0.78, 0.69, 1.0)
GUIDE_LINE_RGBA = (0.82, 0.86, 0.82, 0.8)
PLOT_LINE_RGBA = (0.06, 0.46, 0.43, 1.0)
PLOT_CURSOR_RGBA = (0.72, 0.19, 0.17, 0.95)
PLOT_CURSOR_GUIDE_RGBA = (0.72, 0.19, 0.17, 0.55)
TEXT_PRIMARY_RGBA = (0.13, 0.19, 0.24, 1.0)
TEXT_SECONDARY_RGBA = (0.16, 0.20, 0.24, 1.0)
TEXT_TERTIARY_RGBA = (0.28, 0.32, 0.36, 1.0)
NOTICE_RGBA = (0.17, 0.21, 0.26, 1.0)
BUTTON_BACKGROUND_RGBA = (0.06, 0.46, 0.43, 1.0)
BUTTON_TEXT_RGBA = (1.0, 1.0, 1.0, 1.0)

# Shared typography.
TITLE_FONT_SP = 24
SECTION_TITLE_FONT_SP = 18
BODY_FONT_SP = 14
SMALL_FONT_SP = 12
AXIS_FONT_SP = 11
COMPACT_TITLE_FONT_SP = 20
COMPACT_SECTION_TITLE_FONT_SP = 16
COMPACT_BODY_FONT_SP = 12
COMPACT_SMALL_FONT_SP = 11
COMPACT_AXIS_FONT_SP = 10

# Header card parameters.
# Format:
# - text values control visible wording in the header.
# - height/font values control the card title and notice line.
HEADER_CARD_TITLE_TEXT = "[b]VIS-NIR Spectrometer[/b]"
HEADER_CARD_INITIAL_NOTICE_TEXT = "Waiting for the spectrometer stream."
HEADER_CARD_HEIGHT = dp(96)
HEADER_CARD_HEIGHT_COMPACT = dp(84)
HEADER_TITLE_HEIGHT = dp(40)
HEADER_NOTICE_HEIGHT = dp(28)
HEADER_NOTICE_HEIGHT_COMPACT = dp(44)
HEADER_NOTICE_MIN_TEXT_WIDTH = dp(200)

# Connection card parameters.
# Format:
# - these values control all visible text and sizing for the connection card.
CONNECTION_CARD_TITLE_TEXT = "Connection"
CONNECTION_CARD_PORT_PLACEHOLDER = "Select COM Port"
CONNECTION_CARD_NO_PORTS_TEXT = "No COM Ports Found"
CONNECTION_CARD_STATUS_TEXT = "Status: disconnected"
CONNECTION_CARD_FIRMWARE_TEXT = "Firmware: waiting for banner"
CONNECTION_CARD_REFRESH_BUTTON_TEXT = "Refresh Ports"
CONNECTION_CARD_CONNECT_BUTTON_TEXT = "Connect"
CONNECTION_CARD_DISCONNECT_BUTTON_TEXT = "Disconnect"
CONNECTION_CARD_SAVE_BUTTON_TEXT = "Save User Config"

# Calibration card parameters.
# Format:
# - these values control the calibration card wording, hint text, and helper copy.
CALIBRATION_CARD_TITLE_TEXT = "Calibration"
CALIBRATION_CARD_BACKGROUND_RGBA = (0.94, 0.92, 0.84, 0.98)
CALIBRATION_CARD_BORDER_RGBA = (0.54, 0.47, 0.24, 1.0)
CALIBRATION_CARD_WAVELENGTH_HINT = "Wavelength coefficients"
CALIBRATION_CARD_DARK_TEXT = "Apply dark subtraction"
CALIBRATION_CARD_INTENSITY_TEXT = "Apply intensity correction"
CALIBRATION_CARD_SAVE_BUTTON_TEXT = "Save Calibration"
CALIBRATION_CARD_OPEN_MANAGER_BUTTON_TEXT = "Open Calibration Manager"
CALIBRATION_CARD_HELPER_TEXT = (
    "Use the calibration manager to run guided routines, review wavelength terms, and prepare sensor corrections."
)

# Calibration manager parameters.
# Format:
# - these values control the full-screen calibration workflow shown in the main content area.
CALIBRATION_MANAGER_TITLE_TEXT = "Calibration Manager"
CALIBRATION_MANAGER_SUBTITLE_TEXT = (
    "Run guided calibration steps here without squeezing them into the side panel."
)
CALIBRATION_MANAGER_BACK_BUTTON_TEXT = "Return To Live Spectrum"
CALIBRATION_MANAGER_LIST_TITLE_TEXT = "Calibration Routines"
CALIBRATION_MANAGER_SETTINGS_TITLE_TEXT = "Calibration Settings"
CALIBRATION_MANAGER_PIXEL_MAPPING_TEXT = "Run Pixel Mapping"
CALIBRATION_MANAGER_PIXEL_MAPPING_DESC = "Capture several reference light sources and fit pixel positions to known peaks."
CALIBRATION_MANAGER_DARK_REFERENCE_TEXT = "Capture Dark Reference"
CALIBRATION_MANAGER_DARK_REFERENCE_DESC = "Measure covered-sensor baseline counts for later subtraction."
CALIBRATION_MANAGER_INTENSITY_REFERENCE_TEXT = "Capture Intensity Reference"
CALIBRATION_MANAGER_INTENSITY_REFERENCE_DESC = "Record a flat-field style reference for response correction."
CALIBRATION_MANAGER_WAVELENGTH_REVIEW_TEXT = "Review Wavelength Fit"
CALIBRATION_MANAGER_WAVELENGTH_REVIEW_DESC = "Check polynomial coefficients and update the wavelength map."

# Session and command card parameters.
# Format:
# - these values control the command/session card wording and button captions.
COMMAND_CARD_TITLE_TEXT = "Session And Commands"
COMMAND_CARD_HINT_TEXT = "Raw USB CDC command"
COMMAND_CARD_SEND_BUTTON_TEXT = "Send Raw Command"
COMMAND_CARD_EXPORT_BUTTON_TEXT = "Export Session CSV"
COMMAND_CARD_RESET_BUTTON_TEXT = "Reset Session"

# Spectrum card parameters.
# Format:
# - these values control the graph card labels, placeholder text, and status wording.
SPECTRUM_CARD_TITLE_TEXT = "Live Spectrum"
SPECTRUM_CARD_WAITING_STREAM_MARKUP = "[color=#6b7280]Waiting for data stream[/color]"
SPECTRUM_CARD_STREAM_WAITING_TEXT = "Layout: waiting for stream"
SPECTRUM_CARD_FRAME_LABEL_TEXT = "Frame: n/a"
SPECTRUM_CARD_LAYOUT_LABEL_TEXT = "Layout: n/a"
SPECTRUM_CARD_EDGE_LABEL_TEXT = "Edge samples: n/a"
SPECTRUM_CARD_REFRESH_LABEL_TEXT = "Graph Refresh: n/a"
SPECTRUM_CARD_SESSION_LABEL_TEXT = "Session: n/a"
SPECTRUM_CARD_CURSOR_LABEL_TEXT = "Cursor: none"
SPECTRUM_CARD_FULL_FRAME_MARKUP_TEMPLATE = (
    "[color=#1c7c54]Full-frame stream detected[/color]  "
    "Plotting effective pixels {start} to {end}."
)
SPECTRUM_CARD_PREVIEW_MARKUP_TEMPLATE = (
    "[color=#bb3e03]Preview-only stream detected[/color]  "
    "The STM32 is sending {actual} samples, not {expected}. "
    "Flash the updated firmware to view the full 3694-pixel line."
)
SPECTRUM_CARD_SATURATION_MARKUP_TEMPLATE = (
    "  [color=#b91c1c]{count} sample(s) are pinned at the ADC maximum.[/color]"
)
SPECTRUM_CARD_LAYOUT_FULL_TEMPLATE = (
    "Layout: total={total} | effective={effective} | leading dummy={leading} | trailing dummy={trailing}"
)
SPECTRUM_CARD_LAYOUT_PREVIEW_TEMPLATE = (
    "Layout: preview stream with {total} samples received. The app is plotting exactly what the device sent."
)

# Diagnostics card parameters.
# Format:
# - these values control the diagnostics/log panel.
DIAGNOSTICS_CARD_TITLE_TEXT = "Diagnostics"
DIAGNOSTICS_CARD_TEXT_HEIGHT = dp(220)
DIAGNOSTICS_CARD_TEXT_HEIGHT_COMPACT = dp(180)
CALIBRATION_EDITOR_HEIGHT = dp(120)
CALIBRATION_EDITOR_HEIGHT_COMPACT = dp(96)

# Calibration manager settings card parameters.
# Format:
# - these values control the top-level toggles and shared calibration settings.
CALIBRATION_SETTINGS_CARD_TITLE_TEXT = "Processing Pipeline"
CALIBRATION_SETTINGS_CARD_FIT_ORDER_HINT = "Wavelength fit order"
CALIBRATION_SETTINGS_CARD_QE_TEXT = "Apply QE / response correction"
CALIBRATION_SETTINGS_CARD_NORMALIZATION_LABEL_TEXT = "Display normalization mode"
CALIBRATION_SETTINGS_CARD_NORMALIZATION_AUTO_TEXT = "Auto Range"
CALIBRATION_SETTINGS_CARD_NORMALIZATION_ABSOLUTE_TEXT = "Absolute Saturation"
CALIBRATION_SETTINGS_CARD_APPLY_BUTTON_TEXT = "Preview Calibration"
CALIBRATION_SETTINGS_CARD_SAVE_BUTTON_TEXT = "Save Calibration"
CALIBRATION_SETTINGS_CARD_HELPER_TEXT = (
    "These toggles control the live processed spectrum. Additive terms are removed before multiplicative response terms."
)

# Calibration manager bias/dark card parameters.
# Format:
# - these values control the Bp and master-dark capture/editing section.
CALIBRATION_BIAS_CARD_TITLE_TEXT = "Bias And Dark Terms"
CALIBRATION_BIAS_CARD_HELPER_TEXT = (
    "Capture B_p with the CCD fully blacked out. The frame-wise dark offset beta_f still comes from shielded pixels 16 to 28 in each live frame."
)
CALIBRATION_BIAS_CAPTURE_COUNT_HINT = "Frames to average for B_p"
CALIBRATION_BIAS_CAPTURE_BUTTON_TEXT = "Capture B_p From Latest Frames"
CALIBRATION_BIAS_VECTOR_HINT = "Master bias B_p counts (comma or whitespace separated)"
CALIBRATION_DARK_VECTOR_HINT = "Master dark D_p(T,t) counts (comma or whitespace separated)"
CALIBRATION_BIAS_SUMMARY_TEMPLATE = "Stored B_p samples: {count}"
CALIBRATION_DARK_SUMMARY_TEMPLATE = "Stored master-dark samples: {count}"

# Calibration manager wavelength card parameters.
# Format:
# - these values control the pixel-mapping and polynomial fitting section.
CALIBRATION_WAVELENGTH_CARD_TITLE_TEXT = "Wavelength Mapping"
CALIBRATION_WAVELENGTH_CARD_HELPER_TEXT = (
    "Enter reference peaks as pixel,wavelength pairs. The fit button updates the polynomial used for the wavelength map."
)
CALIBRATION_WAVELENGTH_GUIDED_HELPER_TEXT = (
    "Guided diode mapping: enter the laser wavelengths, then for each step shine that diode, click its peak on the plot, and capture the selected pixel."
)
CALIBRATION_WAVELENGTH_POINTS_HINT = "Pixel mapping points: one per line as pixel,wavelength_nm"
CALIBRATION_WAVELENGTH_GUIDED_LASERS_HINT = "Laser diode wavelengths in nm, e.g. 405, 450, 520, 635, 780, 850"
CALIBRATION_WAVELENGTH_GUIDED_START_BUTTON_TEXT = "Start Guided Mapping"
CALIBRATION_WAVELENGTH_GUIDED_CAPTURE_BUTTON_TEXT = "Capture Selected Peak"
CALIBRATION_WAVELENGTH_GUIDED_RESET_BUTTON_TEXT = "Reset Guided Mapping"
CALIBRATION_WAVELENGTH_GUIDED_STATUS_IDLE_TEXT = "Guided mapping idle. Enter diode wavelengths and start the routine."
CALIBRATION_WAVELENGTH_GUIDED_SELECTION_IDLE_TEXT = "Selected peak: none"
CALIBRATION_WAVELENGTH_GUIDED_STATUS_TEMPLATE = (
    "Step {step} of {total}: shine the {wavelength:.3f} nm diode, click its peak on the plot, then capture that selected peak."
)
CALIBRATION_WAVELENGTH_GUIDED_SELECTION_TEMPLATE = (
    "Selected peak for {wavelength:.3f} nm: pixel={pixel} value={value:.4f}"
)
CALIBRATION_WAVELENGTH_GUIDED_CAPTURED_TEMPLATE = (
    "Captured {captured} of {total} guided laser mapping points."
)
CALIBRATION_WAVELENGTH_GUIDED_COMPLETE_TEMPLATE = (
    "Guided mapping complete. Captured {captured} wavelength references."
)
CALIBRATION_WAVELENGTH_FIT_BUTTON_TEXT = "Fit Coefficients From Pixel Map"
CALIBRATION_WAVELENGTH_SUMMARY_TEMPLATE = "Pixel mapping references: {count}"
CALIBRATION_WAVELENGTH_PLOT_HEIGHT = dp(260)
CALIBRATION_WAVELENGTH_PLOT_HEIGHT_COMPACT = dp(210)

# Calibration manager flat-field card parameters.
# Format:
# - these values control the per-pixel flat-field / PRNU correction input.
CALIBRATION_FLAT_FIELD_CARD_TITLE_TEXT = "Flat-Field / PRNU"
CALIBRATION_FLAT_FIELD_CARD_HELPER_TEXT = (
    "Enter multiplicative per-pixel correction factors if you have measured a flat-field or PRNU calibration."
)
CALIBRATION_FLAT_FIELD_VECTOR_HINT = "Flat-field correction factors (comma or whitespace separated)"
CALIBRATION_FLAT_FIELD_SUMMARY_TEMPLATE = "Stored flat-field factors: {count}"

# Calibration manager QE card parameters.
# Format:
# - these values control the wavelength-dependent QE / response curve section.
CALIBRATION_QE_CARD_TITLE_TEXT = "QE / Response Curve"
CALIBRATION_QE_CARD_HELPER_TEXT = (
    "Enter wavelength,response pairs to correct detector and optical throughput. Values are normalized at the chosen reference wavelength."
)
CALIBRATION_QE_POINTS_HINT = "QE / response points: one per line as wavelength_nm,relative_value"
CALIBRATION_QE_NORMALIZATION_HINT = "QE normalization wavelength (nm)"
CALIBRATION_QE_SUMMARY_TEMPLATE = "QE reference points: {count}"

CALIBRATION_CHECKBOX_BOX_WIDTH = dp(42)
CALIBRATION_CHECKBOX_BOX_HEIGHT = dp(32)
CALIBRATION_CHECKBOX_SIZE = dp(22)
CALIBRATION_CHECKBOX_BORDER_RGBA = (0.38, 0.31, 0.10, 1.0)
CALIBRATION_CHECKBOX_BACKGROUND_RGBA = (1.0, 0.99, 0.94, 1.0)
CALIBRATION_CHECKBOX_STATE_ON_TEXT = "ON"
CALIBRATION_CHECKBOX_STATE_OFF_TEXT = "OFF"
CALIBRATION_CHECKBOX_STATE_ON_RGBA = (0.14, 0.42, 0.24, 1.0)
CALIBRATION_CHECKBOX_STATE_OFF_RGBA = (0.55, 0.26, 0.16, 1.0)

HEADER_SIDE_PANEL_BUTTON_TEXT = "Hide Side Panel"
HEADER_SIDE_PANEL_BUTTON_TEXT_HIDDEN = "Show Side Panel"
HEADER_SIDE_PANEL_BUTTON_WIDTH = dp(160)


class Card(BoxLayout):
    """Purpose: render a styled panel container. Rationale: shared card styling keeps the UI layout consistent."""
    """Purpose: render a styled panel container. Rationale: shared card styling keeps the UI layout consistent."""
    def __init__(self, **kwargs) -> None:
        """Purpose: build the card layout and background. Rationale: reusable visual framing should be created once in one widget."""
        background_rgba = kwargs.pop("background_rgba", CARD_BACKGROUND_RGBA)
        border_rgba = kwargs.pop("border_rgba", CARD_BORDER_RGBA)
        # Every card is a vertical stack with shared spacing and padding so the
        # content blocks line up consistently across the app.
        super().__init__(orientation="vertical", spacing=CARD_GAP, padding=CARD_PAD, **kwargs)
        """Purpose: build the card layout and background. Rationale: reusable visual framing should be created once in one widget."""
        background_rgba = kwargs.pop("background_rgba", CARD_BACKGROUND_RGBA)
        border_rgba = kwargs.pop("border_rgba", CARD_BORDER_RGBA)
        # Every card is a vertical stack with shared spacing and padding so the
        # content blocks line up consistently across the app.
        super().__init__(orientation="vertical", spacing=CARD_GAP, padding=CARD_PAD, **kwargs)
        with self.canvas.before:
            Color(*background_rgba)
            Color(*background_rgba)
            self._background = RoundedRectangle(radius=[18])
            Color(*border_rgba)
            self._border = Line(rounded_rectangle=[0, 0, 0, 0, 18], width=1.0)
            Color(*border_rgba)
            self._border = Line(rounded_rectangle=[0, 0, 0, 0, 18], width=1.0)
        self.bind(pos=self._update_background, size=self._update_background)

    def _update_background(self, *_args) -> None:
        """Purpose: resize the rounded background to match the widget. Rationale: Kivy canvas shapes do not track widget size automatically."""
        """Purpose: resize the rounded background to match the widget. Rationale: Kivy canvas shapes do not track widget size automatically."""
        self._background.pos = self.pos
        self._background.size = self.size
        self._border.rounded_rectangle = [self.x, self.y, self.width, self.height, 18]
        self._border.rounded_rectangle = [self.x, self.y, self.width, self.height, 18]


class SpectrumPlot(Widget):
    """Purpose: draw the live spectrum line. Rationale: a custom plot widget gives full control over axes, scaling, and rendering speed."""
    """Purpose: draw the live spectrum line. Rationale: a custom plot widget gives full control over axes, scaling, and rendering speed."""
    def __init__(self, **kwargs) -> None:
        """Purpose: initialize plot state and redraw bindings. Rationale: the plot should react whenever data or size changes."""
        """Purpose: initialize plot state and redraw bindings. Rationale: the plot should react whenever data or size changes."""
        super().__init__(**kwargs)
        # The plot stores raw x/y series and maps them into screen coordinates
        # during `_redraw`.
        # The plot stores raw x/y series and maps them into screen coordinates
        # during `_redraw`.
        self._x_values: Sequence[int] = ()
        self._y_values: Sequence[int] = ()
        self._adc_min = 0.0
        self._adc_max = float((1 << 12) - 1)
        self._cursor_index: int | None = None
        self._cursor_callback = None
        self._plot_bounds: tuple[float, float, float, float] | None = None
        self._adc_max = float((1 << 12) - 1)
        self._cursor_index: int | None = None
        self._cursor_callback = None
        self._plot_bounds: tuple[float, float, float, float] | None = None
        self.bind(pos=self._redraw, size=self._redraw)

    def set_series(self, x_values: Sequence[int], y_values: Sequence[int]) -> None:
        """Purpose: store the current x/y series. Rationale: the UI should update the plot by replacing data, not drawing directly."""
        """Purpose: store the current x/y series. Rationale: the UI should update the plot by replacing data, not drawing directly."""
        self._x_values = x_values
        self._y_values = y_values
        self._redraw()

    def set_cursor_callback(self, callback) -> None:
        """Purpose: register a cursor-selection callback. Rationale: the parent UI needs the selected point details without owning the plot math."""
        self._cursor_callback = callback

    def current_cursor_value(self) -> tuple[int, float] | None:
        """Purpose: report the currently selected sample. Rationale: the parent UI should be able to refresh the cursor readout as live data changes."""
        if (
            self._cursor_index is None
            or self._cursor_index < 0
            or self._cursor_index >= len(self._x_values)
            or self._cursor_index >= len(self._y_values)
        ):
            return None
        return int(self._x_values[self._cursor_index]), float(self._y_values[self._cursor_index])

    def set_adc_range(self, adc_min: int, adc_max: int) -> None:
        """Purpose: store the y-axis bounds. Rationale: the graph should use the fixed ADC scale chosen by the device config."""
        """Purpose: store the y-axis bounds. Rationale: the graph should use the fixed ADC scale chosen by the device config."""
        self._adc_min = float(adc_min)
        self._adc_max = float(max(adc_max, adc_min + 1))
        self._redraw()

    def _redraw(self, *_args) -> None:
        """Purpose: redraw the plot canvas. Rationale: Kivy plots are manual, so any visual update must be rendered explicitly."""
        """Purpose: redraw the plot canvas. Rationale: Kivy plots are manual, so any visual update must be rendered explicitly."""
        self.canvas.clear()
        with self.canvas:
            # Plot background panel.
            Color(*APP_BACKGROUND_RGBA)
            # Plot background panel.
            Color(*APP_BACKGROUND_RGBA)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[16])

            # Plot border so the graph area reads like a chart, not empty space.
            Color(*CARD_BORDER_RGBA)
            Line(rounded_rectangle=[self.x, self.y, self.width, self.height, 16], width=PLOT_BORDER_WIDTH)
            # Plot border so the graph area reads like a chart, not empty space.
            Color(*CARD_BORDER_RGBA)
            Line(rounded_rectangle=[self.x, self.y, self.width, self.height, 16], width=PLOT_BORDER_WIDTH)

            if (
                not self._x_values
                or not self._y_values
                or self.width <= PLOT_MIN_DRAW_SIZE
                or self.height <= PLOT_MIN_DRAW_SIZE
            ):
            if (
                not self._x_values
                or not self._y_values
                or self.width <= PLOT_MIN_DRAW_SIZE
                or self.height <= PLOT_MIN_DRAW_SIZE
            ):
                return

            left = self.x + PLOT_INNER_PAD
            bottom = self.y + PLOT_INNER_PAD
            plot_width = max(self.width - (PLOT_INNER_PAD * 2), 1.0)
            plot_height = max(self.height - (PLOT_INNER_PAD * 2), 1.0)
            self._plot_bounds = (left, bottom, plot_width, plot_height)

            # Convert sample coordinates into widget pixel coordinates.
            left = self.x + PLOT_INNER_PAD
            bottom = self.y + PLOT_INNER_PAD
            plot_width = max(self.width - (PLOT_INNER_PAD * 2), 1.0)
            plot_height = max(self.height - (PLOT_INNER_PAD * 2), 1.0)
            self._plot_bounds = (left, bottom, plot_width, plot_height)

            # Convert sample coordinates into widget pixel coordinates.
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

            # Reference lines for min, midpoint, max, and the left axis.
            Color(*GUIDE_LINE_RGBA)
            # Reference lines for min, midpoint, max, and the left axis.
            Color(*GUIDE_LINE_RGBA)
            mid_y = bottom + (plot_height * 0.5)
            Line(points=[left, bottom, left + plot_width, bottom], width=GUIDE_LINE_WIDTH)
            Line(points=[left, mid_y, left + plot_width, mid_y], width=GUIDE_LINE_WIDTH)
            Line(points=[left, bottom + plot_height, left + plot_width, bottom + plot_height], width=GUIDE_LINE_WIDTH)
            Line(points=[left, bottom, left, bottom + plot_height], width=GUIDE_LINE_WIDTH)
            Line(points=[left, bottom, left + plot_width, bottom], width=GUIDE_LINE_WIDTH)
            Line(points=[left, mid_y, left + plot_width, mid_y], width=GUIDE_LINE_WIDTH)
            Line(points=[left, bottom + plot_height, left + plot_width, bottom + plot_height], width=GUIDE_LINE_WIDTH)
            Line(points=[left, bottom, left, bottom + plot_height], width=GUIDE_LINE_WIDTH)

            # The spectrum is drawn in chunks because very long single Kivy lines
            # can render unreliably or become sluggish.
            Color(*PLOT_LINE_RGBA)
            for chunk in self._iter_line_chunks(points, max_vertices=PLOT_CHUNK_MAX_VERTICES):
                Line(points=chunk, width=PLOT_LINE_WIDTH)

            if (
                self._cursor_index is not None
                and 0 <= self._cursor_index < len(self._x_values)
                and 0 <= self._cursor_index < len(self._y_values)
            ):
                cursor_x_value = float(self._x_values[self._cursor_index])
                cursor_y_value = min(max(float(self._y_values[self._cursor_index]), self._adc_min), self._adc_max)
                cursor_x = left + ((cursor_x_value - x_min) * x_scale)
                cursor_y = bottom + ((cursor_y_value - self._adc_min) * y_scale)
                Color(*PLOT_CURSOR_GUIDE_RGBA)
                Line(points=[cursor_x, bottom, cursor_x, bottom + plot_height], width=PLOT_CURSOR_LINE_WIDTH)
                Color(*PLOT_CURSOR_RGBA)
                Line(circle=(cursor_x, cursor_y, PLOT_CURSOR_MARKER_SIZE), width=PLOT_CURSOR_LINE_WIDTH)

    def on_touch_down(self, touch) -> bool:
        """Purpose: place or move the plot cursor. Rationale: users should be able to inspect one plotted point interactively."""
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        return self._update_cursor_from_touch(touch) or super().on_touch_down(touch)

    def on_touch_move(self, touch) -> bool:
        """Purpose: drag the plot cursor across the graph. Rationale: cursor inspection should work smoothly while dragging."""
        if touch.grab_current is self:
            return self._update_cursor_from_touch(touch) or True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch) -> bool:
        """Purpose: release the cursor drag state. Rationale: grabbed touches should be released cleanly after interaction."""
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)

    def _update_cursor_from_touch(self, touch) -> bool:
        """Purpose: convert a touch position into the nearest plotted sample. Rationale: cursor selection should snap to real sample points."""
        if not self._x_values or not self._y_values or self._plot_bounds is None:
            return False

        left, _bottom, plot_width, _plot_height = self._plot_bounds
        if plot_width <= 0:
            return False

        relative_x = min(max(touch.x, left), left + plot_width) - left
        fraction = relative_x / plot_width
        nearest_index = int(round(fraction * max(len(self._x_values) - 1, 0)))
        nearest_index = min(max(nearest_index, 0), len(self._x_values) - 1)
        self._cursor_index = nearest_index
        touch.grab(self)
        self._redraw()

        if self._cursor_callback is not None:
            self._cursor_callback(
                int(self._x_values[nearest_index]),
                float(self._y_values[nearest_index]),
            )
        return True
            # The spectrum is drawn in chunks because very long single Kivy lines
            # can render unreliably or become sluggish.
            Color(*PLOT_LINE_RGBA)
            for chunk in self._iter_line_chunks(points, max_vertices=PLOT_CHUNK_MAX_VERTICES):
                Line(points=chunk, width=PLOT_LINE_WIDTH)

            if (
                self._cursor_index is not None
                and 0 <= self._cursor_index < len(self._x_values)
                and 0 <= self._cursor_index < len(self._y_values)
            ):
                cursor_x_value = float(self._x_values[self._cursor_index])
                cursor_y_value = min(max(float(self._y_values[self._cursor_index]), self._adc_min), self._adc_max)
                cursor_x = left + ((cursor_x_value - x_min) * x_scale)
                cursor_y = bottom + ((cursor_y_value - self._adc_min) * y_scale)
                Color(*PLOT_CURSOR_GUIDE_RGBA)
                Line(points=[cursor_x, bottom, cursor_x, bottom + plot_height], width=PLOT_CURSOR_LINE_WIDTH)
                Color(*PLOT_CURSOR_RGBA)
                Line(circle=(cursor_x, cursor_y, PLOT_CURSOR_MARKER_SIZE), width=PLOT_CURSOR_LINE_WIDTH)

    def on_touch_down(self, touch) -> bool:
        """Purpose: place or move the plot cursor. Rationale: users should be able to inspect one plotted point interactively."""
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        return self._update_cursor_from_touch(touch) or super().on_touch_down(touch)

    def on_touch_move(self, touch) -> bool:
        """Purpose: drag the plot cursor across the graph. Rationale: cursor inspection should work smoothly while dragging."""
        if touch.grab_current is self:
            return self._update_cursor_from_touch(touch) or True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch) -> bool:
        """Purpose: release the cursor drag state. Rationale: grabbed touches should be released cleanly after interaction."""
        if touch.grab_current is self:
            touch.ungrab(self)
            return True
        return super().on_touch_up(touch)

    def _update_cursor_from_touch(self, touch) -> bool:
        """Purpose: convert a touch position into the nearest plotted sample. Rationale: cursor selection should snap to real sample points."""
        if not self._x_values or not self._y_values or self._plot_bounds is None:
            return False

        left, _bottom, plot_width, _plot_height = self._plot_bounds
        if plot_width <= 0:
            return False

        relative_x = min(max(touch.x, left), left + plot_width) - left
        fraction = relative_x / plot_width
        nearest_index = int(round(fraction * max(len(self._x_values) - 1, 0)))
        nearest_index = min(max(nearest_index, 0), len(self._x_values) - 1)
        self._cursor_index = nearest_index
        touch.grab(self)
        self._redraw()

        if self._cursor_callback is not None:
            self._cursor_callback(
                int(self._x_values[nearest_index]),
                float(self._y_values[nearest_index]),
            )
        return True

    @staticmethod
    def _iter_line_chunks(points: list[float], *, max_vertices: int) -> list[list[float]]:
        """Purpose: split a long line into smaller pieces. Rationale: chunking large plots is more reliable for Kivy rendering."""
        """Purpose: split a long line into smaller pieces. Rationale: chunking large plots is more reliable for Kivy rendering."""
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
    """Purpose: own the desktop window and all UI behavior. Rationale: Kivy apps usually centralize event handling in one app object."""
    """Purpose: own the desktop window and all UI behavior. Rationale: Kivy apps usually centralize event handling in one app object."""
    def __init__(self, runtime: AppRuntime, **kwargs) -> None:
        """Purpose: store the runtime and widget references. Rationale: later refresh methods need access to both services and UI controls."""
        """Purpose: store the runtime and widget references. Rationale: later refresh methods need access to both services and UI controls."""
        super().__init__(**kwargs)
        self.runtime = runtime
        self.title = "VIS-NIR Spectrometer"
        # These fields are filled in during `build()` and then reused by button
        # handlers and refresh timers.
        # These fields are filled in during `build()` and then reused by button
        # handlers and refresh timers.
        self.port_spinner: Spinner | None = None
        self.command_input: TextInput | None = None
        self.wavelength_input: TextInput | None = None
        self.wavelength_fit_order_input: TextInput | None = None
        self.normalization_mode_spinner: Spinner | None = None
        self.pixel_mapping_input: TextInput | None = None
        self.laser_wavelengths_input: TextInput | None = None
        self.bias_capture_count_input: TextInput | None = None
        self.bias_vector_input: TextInput | None = None
        self.dark_vector_input: TextInput | None = None
        self.flat_field_input: TextInput | None = None
        self.qe_points_input: TextInput | None = None
        self.qe_normalization_input: TextInput | None = None
        self.dark_checkbox: CheckBox | None = None
        self.intensity_checkbox: CheckBox | None = None
        self.qe_checkbox: CheckBox | None = None
        self.status_label: Label | None = None
        self.banner_label: Label | None = None
        self.stream_label: Label | None = None
        self.frame_label: Label | None = None
        self.layout_label: Label | None = None
        self.edge_label: Label | None = None
        self.refresh_rate_label: Label | None = None
        self.session_label: Label | None = None
        self.cursor_label: Label | None = None
        self.cursor_label: Label | None = None
        self.notice_label: Label | None = None
        self.log_area: TextInput | None = None
        self.bias_summary_label: Label | None = None
        self.dark_summary_label: Label | None = None
        self.flat_field_summary_label: Label | None = None
        self.pixel_mapping_summary_label: Label | None = None
        self.qe_summary_label: Label | None = None
        self.guided_mapping_status_label: Label | None = None
        self.guided_mapping_selection_label: Label | None = None
        self.plot: SpectrumPlot | None = None
        self.calibration_plot: SpectrumPlot | None = None
        self.plot_y_max_label: Label | None = None
        self.plot_y_mid_label: Label | None = None
        self.plot_y_min_label: Label | None = None
        self.plot_x_start_label: Label | None = None
        self.plot_x_mid_label: Label | None = None
        self.plot_x_end_label: Label | None = None
        self.calibration_plot_x_start_label: Label | None = None
        self.calibration_plot_x_mid_label: Label | None = None
        self.calibration_plot_x_end_label: Label | None = None
        self._last_plot_signature: tuple[object, ...] | None = None
        self._last_calibration_plot_signature: tuple[object, ...] | None = None
        self._plot_update_times: deque[float] = deque(maxlen=48)
        self._cursor_sample_index: int | None = None
        self._cursor_sample_value: float | None = None
        self._guided_pixel_mapping_active = False
        self._guided_pixel_mapping_wavelengths: list[float] = []
        self._guided_pixel_mapping_step_index = 0
        self._body: BoxLayout | None = None
        self._left_column: BoxLayout | None = None
        self._right_column: BoxLayout | None = None
        self._main_content_container: BoxLayout | None = None
        self._plot_card: Card | None = None
        self._calibration_manager_card: Widget | None = None
        self._header_card: Card | None = None
        self._header_title_label: Label | None = None
        self._header_top_row: BoxLayout | None = None
        self._side_panel_button: Button | None = None
        self._left_scroll: ScrollView | None = None
        self._calibration_wavelength_plot_shell: BoxLayout | None = None
        self._connection_buttons: BoxLayout | None = None
        self._session_buttons: BoxLayout | None = None
        self._connection_card: Card | None = None
        self._calibration_card: Card | None = None
        self._command_card: Card | None = None
        self._metadata_card: Card | None = None
        self._diagnostics_card: Card | None = None
        self._side_panel_cards: list[Card] = []
        self._side_panel_visible = True
        self._main_content_mode = "spectrum"
        self._checkbox_rows: list[BoxLayout] = []
        self._labels_for_wrapping: list[Label] = []
        self._text_inputs: list[TextInput] = []
        self._multiline_editors: list[TextInput] = []
        self._buttons: list[Button] = []
        self._section_titles: list[Label] = []
        self._info_labels: list[Label] = []
        self._small_labels: list[Label] = []
        self._axis_labels: list[Label] = []

    def build(self) -> BoxLayout:
        """Purpose: construct the full desktop layout. Rationale: Kivy expects one method to create the root widget tree."""
        """Purpose: construct the full desktop layout. Rationale: Kivy expects one method to create the root widget tree."""
        user_config = self.runtime.state_manager.get_user_config()
        calibration_config = self.runtime.state_manager.get_calibration_config()

        # Root app shell: header on top, main content below.
        # Root app shell: header on top, main content below.
        root = BoxLayout(
            orientation="vertical",
            spacing=APP_GAP,
            padding=APP_GAP,
            spacing=APP_GAP,
            padding=APP_GAP,
        )

        # Header card holds the app title and a single high-visibility notice line.
        header = Card(size_hint_y=None, height=HEADER_CARD_HEIGHT)
        self._header_card = header
        header_top_row = BoxLayout(orientation="horizontal", spacing=CARD_GAP, size_hint_y=None, height=HEADER_TITLE_HEIGHT)
        self._header_top_row = header_top_row
        self._header_title_label = Label(
            text=HEADER_CARD_TITLE_TEXT,
            markup=True,
            font_size=f"{TITLE_FONT_SP}sp",
            color=TEXT_PRIMARY_RGBA,
            size_hint_y=1.0,
            halign="left",
            valign="middle",
        )
        self._configure_label_wrapping(self._header_title_label)
        header_top_row.add_widget(self._header_title_label)
        self._side_panel_button = self._button(
            HEADER_SIDE_PANEL_BUTTON_TEXT,
            self.toggle_side_panel,
            size_hint_x=None,
            width=HEADER_SIDE_PANEL_BUTTON_WIDTH,
            size_hint_y=1.0,
        )
        header_top_row.add_widget(self._side_panel_button)
        header.add_widget(header_top_row)
        # Header card holds the app title and a single high-visibility notice line.
        header = Card(size_hint_y=None, height=HEADER_CARD_HEIGHT)
        self._header_card = header
        header_top_row = BoxLayout(orientation="horizontal", spacing=CARD_GAP, size_hint_y=None, height=HEADER_TITLE_HEIGHT)
        self._header_top_row = header_top_row
        self._header_title_label = Label(
            text=HEADER_CARD_TITLE_TEXT,
            markup=True,
            font_size=f"{TITLE_FONT_SP}sp",
            color=TEXT_PRIMARY_RGBA,
            size_hint_y=1.0,
            halign="left",
            valign="middle",
        )
        self._configure_label_wrapping(self._header_title_label)
        header_top_row.add_widget(self._header_title_label)
        self._side_panel_button = self._button(
            HEADER_SIDE_PANEL_BUTTON_TEXT,
            self.toggle_side_panel,
            size_hint_x=None,
            width=HEADER_SIDE_PANEL_BUTTON_WIDTH,
            size_hint_y=1.0,
        )
        header_top_row.add_widget(self._side_panel_button)
        header.add_widget(header_top_row)
        self.notice_label = Label(
            text=HEADER_CARD_INITIAL_NOTICE_TEXT,
            color=NOTICE_RGBA,
            text=HEADER_CARD_INITIAL_NOTICE_TEXT,
            color=NOTICE_RGBA,
            halign="left",
            valign="middle",
            size_hint_y=None,
            height=HEADER_NOTICE_HEIGHT,
            height=HEADER_NOTICE_HEIGHT,
        )
        self._configure_label_wrapping(self.notice_label)
        self._configure_label_wrapping(self.notice_label)
        header.add_widget(self.notice_label)
        root.add_widget(header)

        # Body is the responsive region that flips between horizontal and vertical.
        body = BoxLayout(spacing=APP_GAP)
        # Body is the responsive region that flips between horizontal and vertical.
        body = BoxLayout(spacing=APP_GAP)
        root.add_widget(body)
        self._body = body

        left_scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(8),
            scroll_type=["bars", "content"],
            size_hint_x=SIDEBAR_RATIO_WIDE,
        )
        body.add_widget(left_scroll)
        self._left_scroll = left_scroll

        # Left column: controls and session management.
        self._body = body

        left_scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(8),
            scroll_type=["bars", "content"],
            size_hint_x=SIDEBAR_RATIO_WIDE,
        )
        body.add_widget(left_scroll)
        self._left_scroll = left_scroll

        # Left column: controls and session management.
        left_column = BoxLayout(
            orientation="vertical",
            spacing=APP_GAP,
            size_hint_y=None,
            spacing=APP_GAP,
            size_hint_y=None,
        )
        left_column.bind(minimum_height=left_column.setter("height"))
        left_scroll.add_widget(left_column)
        left_scroll.bind(width=lambda _instance, value: setattr(left_column, "width", value))
        self._left_column = left_column
        left_column.bind(minimum_height=left_column.setter("height"))
        left_scroll.add_widget(left_column)
        left_scroll.bind(width=lambda _instance, value: setattr(left_column, "width", value))
        self._left_column = left_column

        # Right column: graph and diagnostics.
        # Right column: graph and diagnostics.
        right_column = BoxLayout(
            orientation="vertical",
            spacing=APP_GAP,
            size_hint_x=DETAIL_RATIO_WIDE,
            spacing=APP_GAP,
            size_hint_x=DETAIL_RATIO_WIDE,
        )
        body.add_widget(right_column)
        self._right_column = right_column
        main_content_container = BoxLayout(orientation="vertical", size_hint_y=1.0)
        right_column.add_widget(main_content_container)
        self._main_content_container = main_content_container

        # Connection card keeps device discovery and connect/disconnect actions together.
        connection_card = Card(size_hint_y=None)
        connection_card.bind(minimum_height=connection_card.setter("height"))
        self._connection_card = connection_card
        self._side_panel_cards.append(connection_card)
        connection_card.add_widget(self._section_title(CONNECTION_CARD_TITLE_TEXT))
        self._right_column = right_column
        main_content_container = BoxLayout(orientation="vertical", size_hint_y=1.0)
        right_column.add_widget(main_content_container)
        self._main_content_container = main_content_container

        # Connection card keeps device discovery and connect/disconnect actions together.
        connection_card = Card(size_hint_y=None)
        connection_card.bind(minimum_height=connection_card.setter("height"))
        self._connection_card = connection_card
        self._side_panel_cards.append(connection_card)
        connection_card.add_widget(self._section_title(CONNECTION_CARD_TITLE_TEXT))
        self.port_spinner = Spinner(
            text=user_config.serial.port or CONNECTION_CARD_PORT_PLACEHOLDER,
            text=user_config.serial.port or CONNECTION_CARD_PORT_PLACEHOLDER,
            values=(),
            size_hint_y=None,
            height=CONTROL_HEIGHT,
            sync_height=True,
            height=CONTROL_HEIGHT,
            sync_height=True,
        )
        self.port_spinner.font_size = f"{BODY_FONT_SP}sp"
        self.port_spinner.font_size = f"{BODY_FONT_SP}sp"
        connection_card.add_widget(self.port_spinner)
        connection_buttons = BoxLayout(size_hint_y=None, height=BUTTON_HEIGHT, spacing=CARD_GAP)
        self._connection_buttons = connection_buttons
        connection_buttons.add_widget(self._button(CONNECTION_CARD_REFRESH_BUTTON_TEXT, self.refresh_ports))
        connection_buttons.add_widget(self._button(CONNECTION_CARD_CONNECT_BUTTON_TEXT, self.connect_device))
        connection_buttons.add_widget(self._button(CONNECTION_CARD_DISCONNECT_BUTTON_TEXT, self.disconnect_device))
        connection_buttons = BoxLayout(size_hint_y=None, height=BUTTON_HEIGHT, spacing=CARD_GAP)
        self._connection_buttons = connection_buttons
        connection_buttons.add_widget(self._button(CONNECTION_CARD_REFRESH_BUTTON_TEXT, self.refresh_ports))
        connection_buttons.add_widget(self._button(CONNECTION_CARD_CONNECT_BUTTON_TEXT, self.connect_device))
        connection_buttons.add_widget(self._button(CONNECTION_CARD_DISCONNECT_BUTTON_TEXT, self.disconnect_device))
        connection_card.add_widget(connection_buttons)
        connection_card.add_widget(self._button(CONNECTION_CARD_SAVE_BUTTON_TEXT, self.save_user_config, size_hint_y=None, height=BUTTON_HEIGHT))
        self.status_label = self._info_label(CONNECTION_CARD_STATUS_TEXT)
        self.banner_label = self._info_label(CONNECTION_CARD_FIRMWARE_TEXT)
        connection_card.add_widget(self._button(CONNECTION_CARD_SAVE_BUTTON_TEXT, self.save_user_config, size_hint_y=None, height=BUTTON_HEIGHT))
        self.status_label = self._info_label(CONNECTION_CARD_STATUS_TEXT)
        self.banner_label = self._info_label(CONNECTION_CARD_FIRMWARE_TEXT)
        connection_card.add_widget(self.status_label)
        connection_card.add_widget(self.banner_label)

        # Calibration card holds wavelength fit terms and correction toggles.
        calibration_card = Card(

        # Calibration card holds wavelength fit terms and correction toggles.
        calibration_card = Card(
            size_hint_y=None,
            background_rgba=CALIBRATION_CARD_BACKGROUND_RGBA,
            border_rgba=CALIBRATION_CARD_BORDER_RGBA,
            background_rgba=CALIBRATION_CARD_BACKGROUND_RGBA,
            border_rgba=CALIBRATION_CARD_BORDER_RGBA,
        )
        calibration_card.bind(minimum_height=calibration_card.setter("height"))
        self._calibration_card = calibration_card
        self._side_panel_cards.append(calibration_card)
        calibration_card.add_widget(self._section_title(CALIBRATION_CARD_TITLE_TEXT))
        calibration_card.add_widget(self._small_label(CALIBRATION_CARD_HELPER_TEXT))
        calibration_card.bind(minimum_height=calibration_card.setter("height"))
        self._calibration_card = calibration_card
        self._side_panel_cards.append(calibration_card)
        calibration_card.add_widget(self._section_title(CALIBRATION_CARD_TITLE_TEXT))
        calibration_card.add_widget(self._small_label(CALIBRATION_CARD_HELPER_TEXT))
        calibration_card.add_widget(
            self._button(
                CALIBRATION_CARD_OPEN_MANAGER_BUTTON_TEXT,
                self.open_calibration_manager,
                size_hint_y=None,
                height=BUTTON_HEIGHT,
            )
        )

        # Session/command card is for export/reset and raw command testing.
        command_card = Card(size_hint_y=None)
        command_card.bind(minimum_height=command_card.setter("height"))
        self._command_card = command_card
        self._side_panel_cards.append(command_card)
        command_card.add_widget(self._section_title(COMMAND_CARD_TITLE_TEXT))
            self._button(
                CALIBRATION_CARD_OPEN_MANAGER_BUTTON_TEXT,
                self.open_calibration_manager,
                size_hint_y=None,
                height=BUTTON_HEIGHT,
            )
        )

        # Session/command card is for export/reset and raw command testing.
        command_card = Card(size_hint_y=None)
        command_card.bind(minimum_height=command_card.setter("height"))
        self._command_card = command_card
        self._side_panel_cards.append(command_card)
        command_card.add_widget(self._section_title(COMMAND_CARD_TITLE_TEXT))
        self.command_input = TextInput(
            text="",
            multiline=False,
            hint_text=COMMAND_CARD_HINT_TEXT,
            hint_text=COMMAND_CARD_HINT_TEXT,
            size_hint_y=None,
            height=CONTROL_HEIGHT,
            height=CONTROL_HEIGHT,
        )
        self._configure_text_input(self.command_input)
        self._configure_text_input(self.command_input)
        command_card.add_widget(self.command_input)
        command_card.add_widget(self._button(COMMAND_CARD_SEND_BUTTON_TEXT, self.send_raw_command, size_hint_y=None, height=BUTTON_HEIGHT))
        session_buttons = BoxLayout(size_hint_y=None, height=BUTTON_HEIGHT, spacing=CARD_GAP)
        self._session_buttons = session_buttons
        session_buttons.add_widget(self._button(COMMAND_CARD_EXPORT_BUTTON_TEXT, self.export_session))
        session_buttons.add_widget(self._button(COMMAND_CARD_RESET_BUTTON_TEXT, self.reset_session))
        command_card.add_widget(self._button(COMMAND_CARD_SEND_BUTTON_TEXT, self.send_raw_command, size_hint_y=None, height=BUTTON_HEIGHT))
        session_buttons = BoxLayout(size_hint_y=None, height=BUTTON_HEIGHT, spacing=CARD_GAP)
        self._session_buttons = session_buttons
        session_buttons.add_widget(self._button(COMMAND_CARD_EXPORT_BUTTON_TEXT, self.export_session))
        session_buttons.add_widget(self._button(COMMAND_CARD_RESET_BUTTON_TEXT, self.reset_session))
        command_card.add_widget(session_buttons)

        # Plot card is the main live-view area for the CCD output.
        # Plot card is the main live-view area for the CCD output.
        plot_card = Card()
        self._plot_card = plot_card
        plot_card.add_widget(self._section_title(SPECTRUM_CARD_TITLE_TEXT))
        self._plot_card = plot_card
        plot_card.add_widget(self._section_title(SPECTRUM_CARD_TITLE_TEXT))
        self.stream_label = Label(
            text=SPECTRUM_CARD_WAITING_STREAM_MARKUP,
            text=SPECTRUM_CARD_WAITING_STREAM_MARKUP,
            markup=True,
            size_hint_y=None,
            height=HEADER_NOTICE_HEIGHT,
            height=HEADER_NOTICE_HEIGHT,
            halign="left",
            valign="middle",
        )
        self._configure_label_wrapping(self.stream_label)
        self._configure_label_wrapping(self.stream_label)
        plot_card.add_widget(self.stream_label)

        # Plot shell has a fixed-width y-axis column and a flexible plot column.
        plot_shell = BoxLayout(orientation="horizontal", spacing=CARD_GAP, size_hint_y=1.0)

        # Plot shell has a fixed-width y-axis column and a flexible plot column.
        plot_shell = BoxLayout(orientation="horizontal", spacing=CARD_GAP, size_hint_y=1.0)
        y_axis_column = BoxLayout(
            orientation="vertical",
            spacing=dp(0),
            size_hint_x=None,
            width=AXIS_COLUMN_WIDTH,
            width=AXIS_COLUMN_WIDTH,
        )
        self.plot_y_max_label = self._axis_label("1.0", valign="top")
        self.plot_y_mid_label = self._axis_label("0.5", valign="middle")
        self.plot_y_min_label = self._axis_label("0.0", valign="bottom")
        self.plot_y_max_label = self._axis_label("1.0", valign="top")
        self.plot_y_mid_label = self._axis_label("0.5", valign="middle")
        self.plot_y_min_label = self._axis_label("0.0", valign="bottom")
        y_axis_column.add_widget(self.plot_y_max_label)
        y_axis_column.add_widget(Widget())
        y_axis_column.add_widget(self.plot_y_mid_label)
        y_axis_column.add_widget(Widget())
        y_axis_column.add_widget(self.plot_y_min_label)
        plot_shell.add_widget(y_axis_column)

        # Plot column contains the graph canvas and the x-axis labels below it.
        # Plot column contains the graph canvas and the x-axis labels below it.
        plot_column = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=1.0)
        self.plot = SpectrumPlot(size_hint_y=1.0)
        self.plot.set_cursor_callback(self._handle_plot_cursor)
        self.plot.set_adc_range(0.0, 1.0)
        self.plot.set_cursor_callback(self._handle_plot_cursor)
        self.plot.set_adc_range(0.0, 1.0)
        plot_column.add_widget(self.plot)

        x_axis_row = BoxLayout(size_hint_y=None, height=X_AXIS_HEIGHT)
        x_axis_row = BoxLayout(size_hint_y=None, height=X_AXIS_HEIGHT)
        self.plot_x_start_label = self._axis_label("0", halign="left")
        self.plot_x_mid_label = self._axis_label("0", halign="center")
        self.plot_x_end_label = self._axis_label("0", halign="right")
        x_axis_row.add_widget(self.plot_x_start_label)
        x_axis_row.add_widget(self.plot_x_mid_label)
        x_axis_row.add_widget(self.plot_x_end_label)
        plot_column.add_widget(x_axis_row)

        plot_shell.add_widget(plot_column)
        plot_card.add_widget(plot_shell)
        self._plot_card = plot_card

        calibration_manager_scroll = ScrollView(
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(8),
            scroll_type=["bars", "content"],
        )
        calibration_manager_card = BoxLayout(
            orientation="vertical",
            spacing=APP_GAP,
            size_hint_y=None,
        )
        calibration_manager_card.bind(minimum_height=calibration_manager_card.setter("height"))
        calibration_manager_scroll.add_widget(calibration_manager_card)
        calibration_manager_scroll.bind(
            width=lambda _instance, value: setattr(calibration_manager_card, "width", value)
        )

        calibration_header_card = Card(size_hint_y=None)
        calibration_header_card.bind(minimum_height=calibration_header_card.setter("height"))
        calibration_header_card.add_widget(self._section_title(CALIBRATION_MANAGER_TITLE_TEXT))
        calibration_header_card.add_widget(self._small_label(CALIBRATION_MANAGER_SUBTITLE_TEXT))
        calibration_header_card.add_widget(
            self._button(
                CALIBRATION_MANAGER_BACK_BUTTON_TEXT,
                self.show_spectrum_view,
                size_hint_y=None,
                height=BUTTON_HEIGHT,
            )
        )
        calibration_manager_card.add_widget(calibration_header_card)

        calibration_settings_card = Card(size_hint_y=None)
        calibration_settings_card.bind(minimum_height=calibration_settings_card.setter("height"))
        calibration_settings_card.add_widget(self._section_title(CALIBRATION_SETTINGS_CARD_TITLE_TEXT))
        calibration_settings_card.add_widget(self._small_label(CALIBRATION_SETTINGS_CARD_HELPER_TEXT))
        self.wavelength_input = TextInput(
            text=", ".join(str(value) for value in calibration_config.wavelength_coefficients),
            multiline=False,
            hint_text=CALIBRATION_CARD_WAVELENGTH_HINT,
            size_hint_y=None,
            height=CONTROL_HEIGHT,
        )
        self._configure_text_input(self.wavelength_input)
        calibration_settings_card.add_widget(self.wavelength_input)
        self.wavelength_fit_order_input = TextInput(
            text=str(calibration_config.wavelength_fit_order),
            multiline=False,
            hint_text=CALIBRATION_SETTINGS_CARD_FIT_ORDER_HINT,
            size_hint_y=None,
            height=CONTROL_HEIGHT,
        )
        self._configure_text_input(self.wavelength_fit_order_input)
        calibration_settings_card.add_widget(self.wavelength_fit_order_input)
        calibration_settings_card.add_widget(
            self._small_label(CALIBRATION_SETTINGS_CARD_NORMALIZATION_LABEL_TEXT)
        )
        self.normalization_mode_spinner = Spinner(
            text=(
                CALIBRATION_SETTINGS_CARD_NORMALIZATION_ABSOLUTE_TEXT
                if calibration_config.display_normalization_mode == "absolute_saturation"
                else CALIBRATION_SETTINGS_CARD_NORMALIZATION_AUTO_TEXT
            ),
            values=(
                CALIBRATION_SETTINGS_CARD_NORMALIZATION_AUTO_TEXT,
                CALIBRATION_SETTINGS_CARD_NORMALIZATION_ABSOLUTE_TEXT,
            ),
            size_hint_y=None,
            height=CONTROL_HEIGHT,
            sync_height=True,
        )
        self.normalization_mode_spinner.font_size = f"{BODY_FONT_SP}sp"
        self.normalization_mode_spinner.bind(text=lambda *_args: self.preview_calibration())
        calibration_settings_card.add_widget(self.normalization_mode_spinner)
        self.dark_checkbox = CheckBox(active=calibration_config.apply_dark_subtraction)
        self.dark_checkbox.bind(active=lambda *_args: self.preview_calibration())
        calibration_settings_card.add_widget(self._checkbox_row(CALIBRATION_CARD_DARK_TEXT, self.dark_checkbox))
        self.intensity_checkbox = CheckBox(active=calibration_config.apply_intensity_correction)
        self.intensity_checkbox.bind(active=lambda *_args: self.preview_calibration())
        calibration_settings_card.add_widget(self._checkbox_row(CALIBRATION_CARD_INTENSITY_TEXT, self.intensity_checkbox))
        self.qe_checkbox = CheckBox(active=calibration_config.apply_quantum_efficiency_correction)
        self.qe_checkbox.bind(active=lambda *_args: self.preview_calibration())
        calibration_settings_card.add_widget(self._checkbox_row(CALIBRATION_SETTINGS_CARD_QE_TEXT, self.qe_checkbox))
        calibration_settings_card.add_widget(
            self._button(
                CALIBRATION_SETTINGS_CARD_APPLY_BUTTON_TEXT,
                self.preview_calibration,
                size_hint_y=None,
                height=BUTTON_HEIGHT,
            )
        )
        calibration_settings_card.add_widget(
            self._button(
                CALIBRATION_SETTINGS_CARD_SAVE_BUTTON_TEXT,
                self.save_calibration,
                size_hint_y=None,
                height=BUTTON_HEIGHT,
            )
        )
        calibration_manager_card.add_widget(calibration_settings_card)

        calibration_bias_card = Card(size_hint_y=None)
        calibration_bias_card.bind(minimum_height=calibration_bias_card.setter("height"))
        calibration_bias_card.add_widget(self._section_title(CALIBRATION_BIAS_CARD_TITLE_TEXT))
        calibration_bias_card.add_widget(self._small_label(CALIBRATION_BIAS_CARD_HELPER_TEXT))
        self.bias_capture_count_input = TextInput(
            text=str(calibration_config.bias_capture_frame_count),
            multiline=False,
            hint_text=CALIBRATION_BIAS_CAPTURE_COUNT_HINT,
            size_hint_y=None,
            height=CONTROL_HEIGHT,
        )
        self._configure_text_input(self.bias_capture_count_input)
        calibration_bias_card.add_widget(self.bias_capture_count_input)
        calibration_bias_card.add_widget(
            self._button(
                CALIBRATION_BIAS_CAPTURE_BUTTON_TEXT,
                self.capture_bias_reference,
                size_hint_y=None,
                height=BUTTON_HEIGHT,
            )
        )
        self.bias_summary_label = self._info_label(
            CALIBRATION_BIAS_SUMMARY_TEMPLATE.format(count=len(calibration_config.bias_counts))
        )
        calibration_bias_card.add_widget(self.bias_summary_label)
        self.bias_vector_input = TextInput(
            text=self._format_float_vector(calibration_config.bias_counts),
            multiline=True,
            hint_text=CALIBRATION_BIAS_VECTOR_HINT,
            size_hint_y=None,
            height=CALIBRATION_EDITOR_HEIGHT,
        )
        self._configure_text_input(self.bias_vector_input)
        self._register_multiline_editor(self.bias_vector_input)
        calibration_bias_card.add_widget(self.bias_vector_input)
        self.dark_summary_label = self._info_label(
            CALIBRATION_DARK_SUMMARY_TEMPLATE.format(count=len(calibration_config.dark_offset_counts))
        )
        calibration_bias_card.add_widget(self.dark_summary_label)
        self.dark_vector_input = TextInput(
            text=self._format_float_vector(calibration_config.dark_offset_counts),
            multiline=True,
            hint_text=CALIBRATION_DARK_VECTOR_HINT,
            size_hint_y=None,
            height=CALIBRATION_EDITOR_HEIGHT,
        )
        self._configure_text_input(self.dark_vector_input)
        self._register_multiline_editor(self.dark_vector_input)
        calibration_bias_card.add_widget(self.dark_vector_input)
        calibration_manager_card.add_widget(calibration_bias_card)

        calibration_wavelength_card = Card(size_hint_y=None)
        calibration_wavelength_card.bind(minimum_height=calibration_wavelength_card.setter("height"))
        calibration_wavelength_card.add_widget(self._section_title(CALIBRATION_WAVELENGTH_CARD_TITLE_TEXT))
        calibration_wavelength_card.add_widget(self._small_label(CALIBRATION_WAVELENGTH_CARD_HELPER_TEXT))
        calibration_wavelength_card.add_widget(self._small_label(CALIBRATION_WAVELENGTH_GUIDED_HELPER_TEXT))
        self.laser_wavelengths_input = TextInput(
            text="",
            multiline=False,
            hint_text=CALIBRATION_WAVELENGTH_GUIDED_LASERS_HINT,
            size_hint_y=None,
            height=CONTROL_HEIGHT,
        )
        self._configure_text_input(self.laser_wavelengths_input)
        calibration_wavelength_card.add_widget(self.laser_wavelengths_input)
        guided_button_row = BoxLayout(size_hint_y=None, height=BUTTON_HEIGHT, spacing=CARD_GAP)
        guided_button_row.add_widget(
            self._button(
                CALIBRATION_WAVELENGTH_GUIDED_START_BUTTON_TEXT,
                self.start_guided_pixel_mapping,
            )
        )
        guided_button_row.add_widget(
            self._button(
                CALIBRATION_WAVELENGTH_GUIDED_CAPTURE_BUTTON_TEXT,
                self.capture_guided_pixel_mapping_point,
            )
        )
        guided_button_row.add_widget(
            self._button(
                CALIBRATION_WAVELENGTH_GUIDED_RESET_BUTTON_TEXT,
                self.reset_guided_pixel_mapping,
            )
        )
        calibration_wavelength_card.add_widget(guided_button_row)
        self.guided_mapping_status_label = self._small_label(CALIBRATION_WAVELENGTH_GUIDED_STATUS_IDLE_TEXT)
        calibration_wavelength_card.add_widget(self.guided_mapping_status_label)
        self.guided_mapping_selection_label = self._info_label(CALIBRATION_WAVELENGTH_GUIDED_SELECTION_IDLE_TEXT)
        calibration_wavelength_card.add_widget(self.guided_mapping_selection_label)
        calibration_plot_shell = BoxLayout(
            orientation="vertical",
            spacing=dp(4),
            size_hint_y=None,
            height=CALIBRATION_WAVELENGTH_PLOT_HEIGHT,
        )
        self._calibration_wavelength_plot_shell = calibration_plot_shell
        self.calibration_plot = SpectrumPlot(size_hint_y=1.0)
        self.calibration_plot.set_cursor_callback(self._handle_plot_cursor)
        self.calibration_plot.set_adc_range(0.0, 1.0)
        calibration_plot_shell.add_widget(self.calibration_plot)
        calibration_plot_x_axis = BoxLayout(size_hint_y=None, height=X_AXIS_HEIGHT)
        self.calibration_plot_x_start_label = self._axis_label("0", halign="left")
        self.calibration_plot_x_mid_label = self._axis_label("0", halign="center")
        self.calibration_plot_x_end_label = self._axis_label("0", halign="right")
        calibration_plot_x_axis.add_widget(self.calibration_plot_x_start_label)
        calibration_plot_x_axis.add_widget(self.calibration_plot_x_mid_label)
        calibration_plot_x_axis.add_widget(self.calibration_plot_x_end_label)
        calibration_plot_shell.add_widget(calibration_plot_x_axis)
        calibration_wavelength_card.add_widget(calibration_plot_shell)
        self.pixel_mapping_summary_label = self._info_label(
            CALIBRATION_WAVELENGTH_SUMMARY_TEMPLATE.format(count=len(calibration_config.pixel_mapping_points))
        )
        calibration_wavelength_card.add_widget(self.pixel_mapping_summary_label)
        self.pixel_mapping_input = TextInput(
            text=self._format_mapping_points(calibration_config.pixel_mapping_points),
            multiline=True,
            hint_text=CALIBRATION_WAVELENGTH_POINTS_HINT,
            size_hint_y=None,
            height=CALIBRATION_EDITOR_HEIGHT,
        )
        self._configure_text_input(self.pixel_mapping_input)
        self._register_multiline_editor(self.pixel_mapping_input)
        calibration_wavelength_card.add_widget(self.pixel_mapping_input)
        calibration_wavelength_card.add_widget(
            self._button(
                CALIBRATION_WAVELENGTH_FIT_BUTTON_TEXT,
                self.fit_wavelength_coefficients_from_points,
                size_hint_y=None,
                height=BUTTON_HEIGHT,
            )
        )
        calibration_manager_card.add_widget(calibration_wavelength_card)

        calibration_flat_field_card = Card(size_hint_y=None)
        calibration_flat_field_card.bind(minimum_height=calibration_flat_field_card.setter("height"))
        calibration_flat_field_card.add_widget(self._section_title(CALIBRATION_FLAT_FIELD_CARD_TITLE_TEXT))
        calibration_flat_field_card.add_widget(self._small_label(CALIBRATION_FLAT_FIELD_CARD_HELPER_TEXT))
        self.flat_field_summary_label = self._info_label(
            CALIBRATION_FLAT_FIELD_SUMMARY_TEMPLATE.format(count=len(calibration_config.intensity_correction))
        )
        calibration_flat_field_card.add_widget(self.flat_field_summary_label)
        self.flat_field_input = TextInput(
            text=self._format_float_vector(calibration_config.intensity_correction),
            multiline=True,
            hint_text=CALIBRATION_FLAT_FIELD_VECTOR_HINT,
            size_hint_y=None,
            height=CALIBRATION_EDITOR_HEIGHT,
        )
        self._configure_text_input(self.flat_field_input)
        self._register_multiline_editor(self.flat_field_input)
        calibration_flat_field_card.add_widget(self.flat_field_input)
        calibration_manager_card.add_widget(calibration_flat_field_card)

        calibration_qe_card = Card(size_hint_y=None)
        calibration_qe_card.bind(minimum_height=calibration_qe_card.setter("height"))
        calibration_qe_card.add_widget(self._section_title(CALIBRATION_QE_CARD_TITLE_TEXT))
        calibration_qe_card.add_widget(self._small_label(CALIBRATION_QE_CARD_HELPER_TEXT))
        self.qe_summary_label = self._info_label(
            CALIBRATION_QE_SUMMARY_TEMPLATE.format(count=len(calibration_config.quantum_efficiency_points))
        )
        calibration_qe_card.add_widget(self.qe_summary_label)
        self.qe_normalization_input = TextInput(
            text=""
            if calibration_config.quantum_efficiency_normalization_wavelength_nm is None
            else str(calibration_config.quantum_efficiency_normalization_wavelength_nm),
            multiline=False,
            hint_text=CALIBRATION_QE_NORMALIZATION_HINT,
            size_hint_y=None,
            height=CONTROL_HEIGHT,
        )
        self._configure_text_input(self.qe_normalization_input)
        calibration_qe_card.add_widget(self.qe_normalization_input)
        self.qe_points_input = TextInput(
            text=self._format_response_points(calibration_config.quantum_efficiency_points),
            multiline=True,
            hint_text=CALIBRATION_QE_POINTS_HINT,
            size_hint_y=None,
            height=CALIBRATION_EDITOR_HEIGHT,
        )
        self._configure_text_input(self.qe_points_input)
        self._register_multiline_editor(self.qe_points_input)
        calibration_qe_card.add_widget(self.qe_points_input)
        calibration_manager_card.add_widget(calibration_qe_card)

        self._calibration_manager_card = calibration_manager_scroll
        self._refresh_main_content()

        metadata_card = Card(size_hint_y=None)
        metadata_card.bind(minimum_height=metadata_card.setter("height"))
        self._metadata_card = metadata_card
        self._side_panel_cards.append(metadata_card)
        metadata_card.add_widget(self._section_title("Frame Data"))
        self.frame_label = self._info_label(SPECTRUM_CARD_FRAME_LABEL_TEXT)
        self.layout_label = self._info_label(SPECTRUM_CARD_LAYOUT_LABEL_TEXT)
        self.edge_label = self._info_label(SPECTRUM_CARD_EDGE_LABEL_TEXT)
        self.refresh_rate_label = self._info_label(SPECTRUM_CARD_REFRESH_LABEL_TEXT)
        self.session_label = self._info_label(SPECTRUM_CARD_SESSION_LABEL_TEXT)
        self.cursor_label = self._info_label(SPECTRUM_CARD_CURSOR_LABEL_TEXT)
        metadata_card.add_widget(self.frame_label)
        metadata_card.add_widget(self.layout_label)
        metadata_card.add_widget(self.edge_label)
        metadata_card.add_widget(self.refresh_rate_label)
        metadata_card.add_widget(self.session_label)
        metadata_card.add_widget(self.cursor_label)

        diagnostics_card = Card(size_hint_y=None)
        diagnostics_card.bind(minimum_height=diagnostics_card.setter("height"))
        self._diagnostics_card = diagnostics_card
        self._side_panel_cards.append(diagnostics_card)
        diagnostics_card.add_widget(self._section_title(DIAGNOSTICS_CARD_TITLE_TEXT))
        self.log_area = TextInput(readonly=True, multiline=True, size_hint_y=None, height=DIAGNOSTICS_CARD_TEXT_HEIGHT)
        self._configure_text_input(self.log_area)
        diagnostics_card.add_widget(self.log_area)

        self._refresh_side_panel_cards()
        self._update_guided_pixel_mapping_status()

        Window.bind(size=self._apply_responsive_layout)
        self._apply_responsive_layout()

        return root

    def on_start(self) -> None:
        """Purpose: start periodic refresh tasks after the UI loads. Rationale: timers should only begin once the window exists."""
        """Purpose: start periodic refresh tasks after the UI loads. Rationale: timers should only begin once the window exists."""
        self.refresh_ports()
        # Plot refresh is allowed to run fast; status/log refresh runs slower to
        # keep the UI responsive.
        # Plot refresh is allowed to run fast; status/log refresh runs slower to
        # keep the UI responsive.
        plot_refresh_s = min(
            max(self.runtime.state_manager.get_user_config().ui.refresh_interval_ms / 1000.0, 0.001),
            1.0 / MAX_PLOT_REFRESH_HZ,
            1.0 / MAX_PLOT_REFRESH_HZ,
        )
        status_refresh_s = max(MIN_WIDE_STATUS_REFRESH_S, plot_refresh_s * 12.0)
        status_refresh_s = max(MIN_WIDE_STATUS_REFRESH_S, plot_refresh_s * 12.0)
        Clock.schedule_interval(self.refresh_plot, plot_refresh_s)
        Clock.schedule_interval(self.refresh_status, status_refresh_s)
        self.refresh_view()
        if self.runtime.state_manager.get_user_config().serial.reconnect_on_start:
            Clock.schedule_once(lambda *_args: self.connect_device(), 0.1)
        try:
            Window.maximize()
        except Exception:
            pass

    def on_stop(self) -> None:
        """Purpose: clean up the device connection on app exit. Rationale: the serial port should not be left open after closing the window."""
        Window.unbind(size=self._apply_responsive_layout)
        """Purpose: clean up the device connection on app exit. Rationale: the serial port should not be left open after closing the window."""
        Window.unbind(size=self._apply_responsive_layout)
        if self.runtime.transport.is_connected():
            self.runtime.command_service.disconnect()

    def refresh_ports(self, *_args) -> None:
        """Purpose: refresh the COM-port choices shown in the UI. Rationale: devices may be plugged in or removed while the app is open."""
        """Purpose: refresh the COM-port choices shown in the UI. Rationale: devices may be plugged in or removed while the app is open."""
        ports = self.runtime.command_service.list_serial_ports()
        devices = [item["device"] for item in ports]
        if self.port_spinner is None:
            return

        # Prefer the saved port, then the current selection, then the first device found.
        # Prefer the saved port, then the current selection, then the first device found.
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
            self.port_spinner.text = CONNECTION_CARD_NO_PORTS_TEXT
            self.port_spinner.text = CONNECTION_CARD_NO_PORTS_TEXT

        self.set_notice(f"Detected {len(devices)} serial port(s).")

    def connect_device(self, *_args) -> None:
        """Purpose: connect using the current UI settings. Rationale: button clicks should flow through one method that validates input first."""
        """Purpose: connect using the current UI settings. Rationale: button clicks should flow through one method that validates input first."""
        port = None if self.port_spinner is None else self.port_spinner.text
        if port == CONNECTION_CARD_NO_PORTS_TEXT:
        if port == CONNECTION_CARD_NO_PORTS_TEXT:
            port = None

        result = self.runtime.command_service.connect(port=port)
        result = self.runtime.command_service.connect(port=port)
        self.set_notice(result.message)
        self.refresh_view()

    def disconnect_device(self, *_args) -> None:
        """Purpose: disconnect from the current device. Rationale: the UI should expose a direct way to end the session cleanly."""
        """Purpose: disconnect from the current device. Rationale: the UI should expose a direct way to end the session cleanly."""
        result = self.runtime.command_service.disconnect()
        self.set_notice(result.message)
        self.refresh_view()

    def save_user_config(self, *_args) -> None:
        """Purpose: save current connection and UI settings. Rationale: user preferences should persist across restarts."""
        if self.port_spinner is None:
        """Purpose: save current connection and UI settings. Rationale: user preferences should persist across restarts."""
        if self.port_spinner is None:
            return

        config = self.runtime.state_manager.get_user_config()
        config.serial.port = None if self.port_spinner.text == CONNECTION_CARD_NO_PORTS_TEXT else self.port_spinner.text
        config.serial.port = None if self.port_spinner.text == CONNECTION_CARD_NO_PORTS_TEXT else self.port_spinner.text
        path = self.runtime.config_store.save(config)
        self.runtime.command_service.apply_user_config(config)
        self.set_notice(f"Saved user config to {path}.")

    def save_calibration(self, *_args) -> None:
        """Purpose: save the current calibration settings. Rationale: calibration changes should be editable from the desktop UI."""
        config = self._read_calibration_form()
        if config is None:
            return

        path = self.runtime.calibration_store.save(config)
        self.runtime.command_service.apply_calibration_config(config)
        self._refresh_calibration_summaries(config)
        self.set_notice(f"Saved calibration config to {path}.")

    def preview_calibration(self, *_args) -> None:
        """Purpose: apply current calibration form settings to the live display. Rationale: toggles should visibly affect the plot immediately, even before saving."""
        config = self._read_calibration_form()
        if config is None:
            return

        self.runtime.command_service.apply_calibration_config(config)
        self._refresh_calibration_summaries(config)
        self.refresh_view()
        self.set_notice("Applied calibration changes to the live display.")

    def capture_bias_reference(self, *_args) -> None:
        """Purpose: capture a master bias vector B_p from recent covered frames. Rationale: the calibration document's bias term should be acquired directly from blackout data inside the app."""
        config = self._read_calibration_form()
        if config is None:
            return

        buffered_frames = self.runtime.session_manager.frames()
        frame_count = max(int(config.bias_capture_frame_count), 1)
        selected_frames = [
            frame.adc_counts
            for frame in buffered_frames[-frame_count:]
            if frame.adc_counts
        ]
        if not selected_frames:
            self.set_notice("No buffered frames are available for B_p capture. Stream covered CCD frames first.")
            return

        bias_counts = self.runtime.calibration_manager.capture_bias_from_frames(selected_frames)
        if self.bias_vector_input is not None:
            self.bias_vector_input.text = self._format_float_vector(bias_counts)

        updated = self._read_calibration_form()
        if updated is None:
            return

        self.runtime.command_service.apply_calibration_config(updated)
        self._refresh_calibration_summaries(updated)
        self.refresh_view()
        self.set_notice(f"Captured B_p from {len(selected_frames)} buffered frame(s).")

    def start_guided_pixel_mapping(self, *_args) -> None:
        """Purpose: begin the diode-by-diode pixel mapping workflow. Rationale: wavelength calibration is easier when the app guides the user through one laser reference at a time."""
        if self.laser_wavelengths_input is None:
            return

        try:
            wavelengths = self._parse_float_vector(self.laser_wavelengths_input.text)
        except ValueError:
            self.set_notice("Laser wavelengths must be numbers separated by commas or spaces.")
            return

        if not wavelengths:
            self.set_notice("Enter one or more laser diode wavelengths before starting guided mapping.")
            return

        self._guided_pixel_mapping_wavelengths = wavelengths
        self._guided_pixel_mapping_step_index = 0
        self._guided_pixel_mapping_active = True
        self._cursor_sample_index = None
        self._cursor_sample_value = None
        self._update_guided_pixel_mapping_status()
        self.set_notice(f"Guided mapping started with {len(wavelengths)} diode wavelength(s).")

    def capture_guided_pixel_mapping_point(self, *_args) -> None:
        """Purpose: store the selected peak for the current guided laser step. Rationale: the user should be able to click a peak and commit it to the wavelength map without typing pixel numbers manually."""
        if not self._guided_pixel_mapping_active or not self._guided_pixel_mapping_wavelengths:
            self.set_notice("Start guided mapping before capturing a laser peak.")
            return
        if self._cursor_sample_index is None or self._cursor_sample_value is None:
            self.set_notice("Click the peak on the plot before capturing the current laser wavelength.")
            return
        if self.pixel_mapping_input is None:
            return

        try:
            current_points = self._parse_mapping_points(self.pixel_mapping_input.text)
        except ValueError:
            self.set_notice("The existing pixel mapping points could not be parsed. Fix them before adding guided points.")
            return

        target_wavelength = self._guided_pixel_mapping_wavelengths[self._guided_pixel_mapping_step_index]
        filtered_points = [
            point
            for point in current_points
            if abs(point.wavelength_nm - target_wavelength) > 1e-9
        ]
        filtered_points.append(
            PixelMappingPoint(
                pixel_index=float(self._cursor_sample_index),
                wavelength_nm=float(target_wavelength),
            )
        )
        self.pixel_mapping_input.text = self._format_mapping_points(filtered_points)

        self._guided_pixel_mapping_step_index += 1
        completed = self._guided_pixel_mapping_step_index >= len(self._guided_pixel_mapping_wavelengths)
        self._guided_pixel_mapping_active = not completed
        if completed:
            self._update_guided_pixel_mapping_status()
            self.fit_wavelength_coefficients_from_points()
            return

        self._cursor_sample_index = None
        self._cursor_sample_value = None
        updated = self._read_calibration_form()
        if updated is not None:
            self.runtime.command_service.apply_calibration_config(updated)
            self._refresh_calibration_summaries(updated)
        self._update_guided_pixel_mapping_status()
        self.refresh_view()
        self.set_notice(
            CALIBRATION_WAVELENGTH_GUIDED_CAPTURED_TEMPLATE.format(
                captured=self._guided_pixel_mapping_step_index,
                total=len(self._guided_pixel_mapping_wavelengths),
            )
        )

    def reset_guided_pixel_mapping(self, *_args) -> None:
        """Purpose: clear the guided wavelength-mapping calibration state. Rationale: resetting the guided workflow should also remove the captured mapping table and restore the graph x-axis to raw pixel indices."""
        self._guided_pixel_mapping_active = False
        self._guided_pixel_mapping_wavelengths = []
        self._guided_pixel_mapping_step_index = 0
        self._cursor_sample_index = None
        self._cursor_sample_value = None
        if self.laser_wavelengths_input is not None:
            self.laser_wavelengths_input.text = ""
        if self.pixel_mapping_input is not None:
            self.pixel_mapping_input.text = ""
        if self.wavelength_input is not None:
            self.wavelength_input.text = self._format_inline_coefficients(DEFAULT_WAVELENGTH_COEFFICIENTS)
        self._update_guided_pixel_mapping_status()
        updated = self._read_calibration_form()
        if updated is not None:
            self.runtime.command_service.apply_calibration_config(updated)
            self._refresh_calibration_summaries(updated)
        self.refresh_view()
        self.set_notice("Guided pixel mapping reset and wavelength axis returned to pixels.")

    def fit_wavelength_coefficients_from_points(self, *_args) -> None:
        """Purpose: fit wavelength coefficients from the entered pixel map. Rationale: the user should be able to move from line references to the polynomial map without leaving the calibration manager."""
        config = self._read_calibration_form()
        if config is None:
            return
        if not config.pixel_mapping_points:
            self.set_notice("Enter at least one pixel mapping point before fitting coefficients.")
            return

        coefficients = self.runtime.calibration_manager.fit_wavelength_coefficients(
            config.pixel_mapping_points,
            fit_order=config.wavelength_fit_order,
        )
        if self.wavelength_input is not None:
            self.wavelength_input.text = self._format_inline_coefficients(coefficients)

        updated = self._read_calibration_form()
        if updated is None:
            return

        self.runtime.command_service.apply_calibration_config(updated)
        self._refresh_calibration_summaries(updated)
        self.refresh_view()
        self._update_guided_pixel_mapping_status()
        self.set_notice(
            f"Fitted {len(updated.wavelength_coefficients)} wavelength coefficient(s) from {len(updated.pixel_mapping_points)} mapping point(s)."
        )

    def _read_calibration_form(self) -> CalibrationConfig | None:
        """Purpose: read the calibration controls into a config object. Rationale: preview and save should share one form-reading path."""
        if (
            self.wavelength_input is None
            or self.wavelength_fit_order_input is None
            or self.normalization_mode_spinner is None
            or self.pixel_mapping_input is None
            or self.bias_capture_count_input is None
            or self.bias_vector_input is None
            or self.dark_vector_input is None
            or self.flat_field_input is None
            or self.qe_points_input is None
            or self.qe_normalization_input is None
            or self.dark_checkbox is None
            or self.intensity_checkbox is None
            or self.qe_checkbox is None
        ):
            return None
            return None

        try:
            coefficients = self._parse_float_vector(self.wavelength_input.text)
            if not coefficients:
                raise ValueError("missing coefficients")
            fit_order = int(self.wavelength_fit_order_input.text.strip() or "0")
            bias_capture_frame_count = int(self.bias_capture_count_input.text.strip() or "1")
            bias_counts = self._parse_float_vector(self.bias_vector_input.text)
            dark_counts = self._parse_float_vector(self.dark_vector_input.text)
            flat_field = self._parse_float_vector(self.flat_field_input.text)
            mapping_points = self._parse_mapping_points(self.pixel_mapping_input.text)
            qe_points = self._parse_response_points(self.qe_points_input.text)
            qe_normalization = (
                float(self.qe_normalization_input.text.strip())
                if self.qe_normalization_input.text.strip()
                else None
            )
        except ValueError:
            self.set_notice("One or more calibration entries could not be parsed. Check the coefficients, vectors, and point tables.")
            return None

        return CalibrationConfig(
            apply_dark_subtraction=bool(self.dark_checkbox.active),
            apply_intensity_correction=bool(self.intensity_checkbox.active),
            apply_quantum_efficiency_correction=bool(self.qe_checkbox.active),
            display_normalization_mode=(
                "absolute_saturation"
                if self.normalization_mode_spinner.text == CALIBRATION_SETTINGS_CARD_NORMALIZATION_ABSOLUTE_TEXT
                else "auto_peak"
            ),
            wavelength_coefficients=coefficients,
            wavelength_fit_order=max(fit_order, 0),
            pixel_mapping_points=mapping_points,
            bias_capture_frame_count=max(bias_capture_frame_count, 1),
            bias_counts=bias_counts,
            dark_offset_counts=dark_counts,
            intensity_correction=flat_field,
            quantum_efficiency_points=qe_points,
            quantum_efficiency_normalization_wavelength_nm=qe_normalization,
        )

    def export_session(self, *_args) -> None:
        """Purpose: export buffered frames to CSV. Rationale: captured data should be easy to save without leaving the app."""
        """Purpose: export buffered frames to CSV. Rationale: captured data should be easy to save without leaving the app."""
        path = self.runtime.session_manager.export_csv()
        self.runtime.command_service.refresh_session_status()
        self.set_notice(f"Exported session to {path}.")
        self.refresh_view()

    def reset_session(self, *_args) -> None:
        """Purpose: clear the current session buffer. Rationale: users often want a fresh capture run without restarting the app."""
        """Purpose: clear the current session buffer. Rationale: users often want a fresh capture run without restarting the app."""
        self.runtime.session_manager.reset()
        self.runtime.command_service.refresh_session_status()
        self.set_notice("Session buffer cleared.")
        self.refresh_view()

    def send_raw_command(self, *_args) -> None:
        """Purpose: send a raw command string to the device. Rationale: advanced control and debugging should be available from the UI."""
        """Purpose: send a raw command string to the device. Rationale: advanced control and debugging should be available from the UI."""
        if self.command_input is None:
            return
        result = self.runtime.command_service.send_raw_command(self.command_input.text)
        self.set_notice(result.message)
        self.refresh_view()

    def refresh_status(self, *_args) -> None:
        """Purpose: refresh slower-changing text fields. Rationale: status labels and logs do not need the same rate as the plot."""
        """Purpose: refresh slower-changing text fields. Rationale: status labels and logs do not need the same rate as the plot."""
        snapshot = self.runtime.state_manager.snapshot(include_spectrum=False)

        # Connection and firmware banner fields summarize the device state.
        # Connection and firmware banner fields summarize the device state.
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
        """Purpose: refresh the live spectrum graph and its labels. Rationale: the plot is the fastest-changing part of the UI."""
        """Purpose: refresh the live spectrum graph and its labels. Rationale: the plot is the fastest-changing part of the UI."""
        spectrum = self.runtime.state_manager.latest_spectrum()
        device_config = self.runtime.state_manager.get_user_config().device
        calibration_config = self.runtime.state_manager.get_calibration_config()
        expected_samples = device_config.sample_count
        normalized_max = 1.0
        normalized_max = 1.0
        effective_start_default = device_config.effective_start_index
        effective_end_default = max(
            effective_start_default + device_config.effective_sample_count - 1,
            effective_start_default,
        )

        display_indices: list[int] = []
        display_values: list[float] = []
        layout_text = SPECTRUM_CARD_STREAM_WAITING_TEXT
        stream_markup = SPECTRUM_CARD_WAITING_STREAM_MARKUP

        if spectrum is not None:
            plot_source = spectrum.live_display_counts or spectrum.adc_counts
            total_samples = len(plot_source)
            plot_source = spectrum.live_display_counts or spectrum.adc_counts
            total_samples = len(plot_source)
            full_frame_ready = total_samples >= expected_samples

            if full_frame_ready:
                # Only the effective CCD pixels are plotted for full frames, so
                # dummy leading/trailing clocks do not dominate the display.
                # Only the effective CCD pixels are plotted for full frames, so
                # dummy leading/trailing clocks do not dominate the display.
                start = spectrum.effective_start_index
                end = min(
                    start + spectrum.effective_sample_count,
                    total_samples,
                )
                display_indices = range(start, end)
                display_values = plot_source[start:end]
                stream_markup = SPECTRUM_CARD_FULL_FRAME_MARKUP_TEMPLATE.format(
                    start=start,
                    end=max(end - 1, start),
                display_values = plot_source[start:end]
                stream_markup = SPECTRUM_CARD_FULL_FRAME_MARKUP_TEMPLATE.format(
                    start=start,
                    end=max(end - 1, start),
                )
                layout_text = SPECTRUM_CARD_LAYOUT_FULL_TEMPLATE.format(
                    total=total_samples,
                    effective=len(display_values),
                    leading=start,
                    trailing=max(total_samples - end, 0),
                layout_text = SPECTRUM_CARD_LAYOUT_FULL_TEMPLATE.format(
                    total=total_samples,
                    effective=len(display_values),
                    leading=start,
                    trailing=max(total_samples - end, 0),
                )
            else:
                # Preview-only mode intentionally plots the exact short stream the
                # device sent so the UI does not invent missing data.
                # Preview-only mode intentionally plots the exact short stream the
                # device sent so the UI does not invent missing data.
                display_indices = range(total_samples)
                display_values = plot_source
                stream_markup = SPECTRUM_CARD_PREVIEW_MARKUP_TEMPLATE.format(
                    actual=total_samples,
                    expected=expected_samples,
                display_values = plot_source
                stream_markup = SPECTRUM_CARD_PREVIEW_MARKUP_TEMPLATE.format(
                    actual=total_samples,
                    expected=expected_samples,
                )
                layout_text = SPECTRUM_CARD_LAYOUT_PREVIEW_TEMPLATE.format(total=total_samples)

        if self.stream_label is not None:
            self.stream_label.text = stream_markup
        if self.layout_label is not None:
            self.layout_label.text = layout_text
        if self.plot_y_max_label is not None:
            self.plot_y_max_label.text = "1.0"
            self.plot_y_max_label.text = "1.0"
        if self.plot_y_mid_label is not None:
            self.plot_y_mid_label.text = "0.5"
            self.plot_y_mid_label.text = "0.5"
        if self.plot_y_min_label is not None:
            self.plot_y_min_label.text = "0.0"
            self.plot_y_min_label.text = "0.0"
        if display_indices:
            x_start = display_indices[0]
            x_mid = display_indices[len(display_indices) // 2]
            x_end = display_indices[-1]
        else:
            x_start = effective_start_default
            x_mid = (effective_start_default + effective_end_default) // 2
            x_end = effective_end_default
        axis_start_text = self._format_plot_axis_label(x_start, calibration_config)
        axis_mid_text = self._format_plot_axis_label(x_mid, calibration_config)
        axis_end_text = self._format_plot_axis_label(x_end, calibration_config)
        if self.plot_x_start_label is not None:
            self.plot_x_start_label.text = axis_start_text
        if self.plot_x_mid_label is not None:
            self.plot_x_mid_label.text = axis_mid_text
        if self.plot_x_end_label is not None:
            self.plot_x_end_label.text = axis_end_text
        if self.plot is not None:
            self.plot.set_adc_range(0.0, normalized_max)
            # This signature prevents redrawing the same spectrum repeatedly when
            # the timer fires faster than new frames arrive.
            self.plot.set_adc_range(0.0, normalized_max)
            # This signature prevents redrawing the same spectrum repeatedly when
            # the timer fires faster than new frames arrive.
            plot_signature = (
                spectrum.frame_id if spectrum is not None else None,
                len(display_values),
                display_indices[0] if display_indices else None,
                display_indices[-1] if display_indices else None,
                round(float(display_values[0]), 6) if display_values else None,
                round(float(display_values[len(display_values) // 2]), 6) if display_values else None,
                round(float(display_values[-1]), 6) if display_values else None,
            )
            if plot_signature != self._last_plot_signature:
                self.plot.set_series(display_indices, display_values)
                self._last_plot_signature = plot_signature
                self._record_plot_update()
        if self.calibration_plot_x_start_label is not None:
            self.calibration_plot_x_start_label.text = axis_start_text
        if self.calibration_plot_x_mid_label is not None:
            self.calibration_plot_x_mid_label.text = axis_mid_text
        if self.calibration_plot_x_end_label is not None:
            self.calibration_plot_x_end_label.text = axis_end_text
        if self.calibration_plot is not None:
            self.calibration_plot.set_adc_range(0.0, normalized_max)
            calibration_plot_signature = (
                spectrum.frame_id if spectrum is not None else None,
                len(display_values),
                display_indices[0] if display_indices else None,
                display_indices[-1] if display_indices else None,
                round(float(display_values[0]), 6) if display_values else None,
                round(float(display_values[len(display_values) // 2]), 6) if display_values else None,
                round(float(display_values[-1]), 6) if display_values else None,
            )
            if calibration_plot_signature != self._last_calibration_plot_signature:
                self.calibration_plot.set_series(display_indices, display_values)
                self._last_calibration_plot_signature = calibration_plot_signature
        active_cursor_value: tuple[int, float] | None = None
        if self._main_content_mode == "calibration":
            if self.calibration_plot is not None:
                active_cursor_value = self.calibration_plot.current_cursor_value()
        elif self.plot is not None:
            active_cursor_value = self.plot.current_cursor_value()
        if active_cursor_value is not None:
            self._handle_plot_cursor(*active_cursor_value)
        if self.refresh_rate_label is not None:
            refresh_hz = self._current_plot_refresh_hz()
            self.refresh_rate_label.text = (
                f"Graph Refresh: {refresh_hz:.1f} Hz"
                if refresh_hz > 0.0
                else SPECTRUM_CARD_REFRESH_LABEL_TEXT
                else SPECTRUM_CARD_REFRESH_LABEL_TEXT
            )

    def refresh_view(self, *_args) -> None:
        """Purpose: refresh both status and plot sections together. Rationale: some UI actions need an immediate full refresh."""
        """Purpose: refresh both status and plot sections together. Rationale: some UI actions need an immediate full refresh."""
        self.refresh_status()
        self.refresh_plot()

    def _handle_plot_cursor(self, sample_index: int, sample_value: float) -> None:
        """Purpose: show the currently selected plot point. Rationale: cursor readout should be visible outside the graph canvas."""
        self._cursor_sample_index = sample_index
        self._cursor_sample_value = sample_value
        if self.cursor_label is not None:
            calibration_config = self.runtime.state_manager.get_calibration_config()
            if self._show_wavelength_axis(calibration_config):
                wavelength = float(indices_to_wavelengths([sample_index], calibration_config.wavelength_coefficients)[0])
                self.cursor_label.text = (
                    f"Cursor: pixel={sample_index} wavelength={wavelength:.2f} nm value={sample_value:.4f}"
                )
            else:
                self.cursor_label.text = f"Cursor: pixel={sample_index} value={sample_value:.4f}"
        self._update_guided_pixel_mapping_status()

    def _refresh_main_content(self) -> None:
        """Purpose: swap the main content view. Rationale: the app should show either the live spectrum or the calibration manager, not both."""
        if self._main_content_container is None:
            return

        self._main_content_container.clear_widgets()
        if self._main_content_mode == "calibration" and self._calibration_manager_card is not None:
            self._main_content_container.add_widget(self._calibration_manager_card)
        elif self._plot_card is not None:
            self._main_content_container.add_widget(self._plot_card)

    def open_calibration_manager(self, *_args) -> None:
        """Purpose: toggle the calibration manager in the main content area. Rationale: the side-panel entry button should also work as a quick return to the live plot."""
        if self._main_content_mode == "calibration":
            self.show_spectrum_view()
            return
        self._main_content_mode = "calibration"
        self._refresh_main_content()
        self.set_notice("Calibration manager opened.")

    def show_spectrum_view(self, *_args) -> None:
        """Purpose: return to the live spectrum view. Rationale: users need a quick way back to the main measurement screen."""
        self._main_content_mode = "spectrum"
        self._refresh_main_content()
        self.set_notice("Returned to live spectrum view.")

    def _refresh_side_panel_cards(self) -> None:
        """Purpose: rebuild the scrollable side panel. Rationale: the side panel should always contain the full card set when visible."""
        if self._left_column is None:
            return

        self._left_column.clear_widgets()
        for card in self._side_panel_cards:
            self._left_column.add_widget(card)

    def toggle_side_panel(self, *_args) -> None:
        """Purpose: show or hide the side panel. Rationale: one header control should let the graph expand to full width on demand."""
        self._side_panel_visible = not self._side_panel_visible
        self._apply_responsive_layout()

    def _record_plot_update(self) -> None:
        """Purpose: record when the plot changed. Rationale: measured refresh speed should reflect real redraw activity."""
        """Purpose: record when the plot changed. Rationale: measured refresh speed should reflect real redraw activity."""
        self._plot_update_times.append(perf_counter())

    def _current_plot_refresh_hz(self) -> float:
        """Purpose: estimate the plot refresh rate. Rationale: users need feedback on how quickly new frames are reaching the graph."""
        """Purpose: estimate the plot refresh rate. Rationale: users need feedback on how quickly new frames are reaching the graph."""
        if len(self._plot_update_times) < 2:
            return 0.0

        newest = self._plot_update_times[-1]
        oldest = self._plot_update_times[0]
        if perf_counter() - newest > PLOT_REFRESH_STALE_S:
        if perf_counter() - newest > PLOT_REFRESH_STALE_S:
            return 0.0

        elapsed_s = newest - oldest
        if elapsed_s <= 0.0:
            return 0.0

        return (len(self._plot_update_times) - 1) / elapsed_s

    def set_notice(self, message: str) -> None:
        """Purpose: update the header notice text. Rationale: one central status message keeps user feedback easy to find."""
        """Purpose: update the header notice text. Rationale: one central status message keeps user feedback easy to find."""
        if self.notice_label is not None:
            self.notice_label.text = message

    def _update_guided_pixel_mapping_status(self) -> None:
        """Purpose: refresh the diode-mapping instructions and selection summary. Rationale: the wavelength workflow should clearly tell the user which laser comes next and what peak is currently selected."""
        if self.guided_mapping_status_label is None or self.guided_mapping_selection_label is None:
            return

        if not self._guided_pixel_mapping_wavelengths:
            self.guided_mapping_status_label.text = CALIBRATION_WAVELENGTH_GUIDED_STATUS_IDLE_TEXT
            self.guided_mapping_selection_label.text = CALIBRATION_WAVELENGTH_GUIDED_SELECTION_IDLE_TEXT
            return

        total = len(self._guided_pixel_mapping_wavelengths)
        if self._guided_pixel_mapping_active and self._guided_pixel_mapping_step_index < total:
            active_wavelength = self._guided_pixel_mapping_wavelengths[self._guided_pixel_mapping_step_index]
            self.guided_mapping_status_label.text = CALIBRATION_WAVELENGTH_GUIDED_STATUS_TEMPLATE.format(
                step=self._guided_pixel_mapping_step_index + 1,
                total=total,
                wavelength=active_wavelength,
            )
            if self._cursor_sample_index is None or self._cursor_sample_value is None:
                self.guided_mapping_selection_label.text = CALIBRATION_WAVELENGTH_GUIDED_SELECTION_IDLE_TEXT
            else:
                self.guided_mapping_selection_label.text = CALIBRATION_WAVELENGTH_GUIDED_SELECTION_TEMPLATE.format(
                    wavelength=active_wavelength,
                    pixel=self._cursor_sample_index,
                    value=self._cursor_sample_value,
                )
            return

        self.guided_mapping_status_label.text = CALIBRATION_WAVELENGTH_GUIDED_COMPLETE_TEMPLATE.format(
            captured=total,
        )
        self.guided_mapping_selection_label.text = CALIBRATION_WAVELENGTH_GUIDED_SELECTION_IDLE_TEXT

    def _format_plot_axis_label(self, sample_index: int, calibration_config: CalibrationConfig) -> str:
        """Purpose: choose pixel or wavelength labels for the plot x-axis. Rationale: once wavelength calibration exists, the graph should read in physical units instead of raw CCD indices."""
        if not self._show_wavelength_axis(calibration_config):
            return str(sample_index)

        wavelength = float(indices_to_wavelengths([sample_index], calibration_config.wavelength_coefficients)[0])
        return f"{wavelength:.1f}"

    def _show_wavelength_axis(self, calibration_config: CalibrationConfig) -> bool:
        """Purpose: decide when the x-axis should display wavelength values. Rationale: uncalibrated plots are easier to interpret in pixels, while calibrated plots should show wavelength."""
        return calibration_config.wavelength_coefficients != [0.0, 1.0]

    def _apply_responsive_layout(self, *_args) -> None:
        """Purpose: switch between wide and narrow layouts. Rationale: the UI should remain usable on both large and smaller windows."""
        if (
            self._body is None
            or self._left_column is None
            or self._right_column is None
            or self._left_scroll is None
        ):
            return

        # Wide mode uses side-by-side columns; narrow mode stacks everything and
        # keeps the side panel optional so the plot can use the full width.
        narrow_layout = Window.width < RESPONSIVE_BREAKPOINT
        short_layout = Window.height < SHORT_HEIGHT_BREAKPOINT
        compact_layout = Window.width < COMPACT_BREAKPOINT or short_layout
        stack_connection_buttons = Window.width < BUTTON_STACK_BREAKPOINT
        stack_session_buttons = Window.width < BUTTON_STACK_BREAKPOINT
        self._body.orientation = "vertical" if narrow_layout else "horizontal"
        side_panel_active = self._side_panel_visible
        self._left_scroll.size_hint_x = (1.0 if narrow_layout else SIDEBAR_RATIO_WIDE) if side_panel_active else None
        self._left_scroll.width = 0 if side_panel_active else 0
        self._left_scroll.size_hint_y = None if (narrow_layout and side_panel_active) else 1.0
        self._left_scroll.height = dp(320) if (narrow_layout and side_panel_active) else 0
        self._left_scroll.opacity = 1.0 if side_panel_active else 0.0
        self._left_scroll.disabled = not side_panel_active
        self._right_column.size_hint_x = 1.0 if (narrow_layout or not side_panel_active) else DETAIL_RATIO_WIDE
        self._right_column.size_hint_y = 1.0
        if self._connection_buttons is not None:
            self._connection_buttons.orientation = "vertical" if stack_connection_buttons else "horizontal"
            self._connection_buttons.height = (
                (NARROW_BUTTON_HEIGHT * len(self._connection_buttons.children)) + (CARD_GAP * (len(self._connection_buttons.children) - 1))
                if stack_connection_buttons
                else BUTTON_HEIGHT
            )
        if self._session_buttons is not None:
            self._session_buttons.orientation = "vertical" if stack_session_buttons else "horizontal"
            self._session_buttons.height = (
                (NARROW_BUTTON_HEIGHT * len(self._session_buttons.children)) + (CARD_GAP * (len(self._session_buttons.children) - 1))
                if stack_session_buttons
                else BUTTON_HEIGHT
            )

        title_font_sp = COMPACT_TITLE_FONT_SP if compact_layout else TITLE_FONT_SP
        section_font_sp = COMPACT_SECTION_TITLE_FONT_SP if compact_layout else SECTION_TITLE_FONT_SP
        body_font_sp = COMPACT_BODY_FONT_SP if compact_layout else BODY_FONT_SP
        small_font_sp = COMPACT_SMALL_FONT_SP if compact_layout else SMALL_FONT_SP
        axis_font_sp = COMPACT_AXIS_FONT_SP if compact_layout else AXIS_FONT_SP
        control_height = NARROW_CONTROL_HEIGHT if compact_layout else CONTROL_HEIGHT
        button_height = NARROW_BUTTON_HEIGHT if compact_layout else BUTTON_HEIGHT
        info_height = NARROW_INFO_LABEL_HEIGHT if compact_layout else INFO_LABEL_HEIGHT
        small_height = NARROW_SMALL_LABEL_HEIGHT if compact_layout else SMALL_LABEL_HEIGHT
        checkbox_height = NARROW_CHECKBOX_ROW_HEIGHT if compact_layout else CHECKBOX_ROW_HEIGHT
        header_height = HEADER_CARD_HEIGHT_COMPACT if compact_layout else HEADER_CARD_HEIGHT
        notice_height = HEADER_NOTICE_HEIGHT_COMPACT if compact_layout else HEADER_NOTICE_HEIGHT
        for card in self._side_panel_cards:
            card.spacing = dp(6) if compact_layout else CARD_GAP
            card.padding = dp(10) if compact_layout else CARD_PAD
        if self._header_card is not None:
            self._header_card.height = header_height
        if self._header_top_row is not None:
            self._header_top_row.height = HEADER_TITLE_HEIGHT
        if self._header_title_label is not None:
            self._header_title_label.font_size = f"{title_font_sp}sp"
            self._header_title_label.height = max(HEADER_TITLE_HEIGHT, notice_height)
        if self.notice_label is not None:
            self.notice_label.height = notice_height
            self.notice_label.font_size = f"{body_font_sp}sp"
            self.notice_label.text_size = (max(Window.width - (APP_GAP * 4), HEADER_NOTICE_MIN_TEXT_WIDTH), None)
        if self._side_panel_button is not None:
            self._side_panel_button.text = (
                HEADER_SIDE_PANEL_BUTTON_TEXT if side_panel_active else HEADER_SIDE_PANEL_BUTTON_TEXT_HIDDEN
            )
            self._side_panel_button.height = button_height
            self._side_panel_button.font_size = f"{body_font_sp}sp"
        if self._calibration_wavelength_plot_shell is not None:
            self._calibration_wavelength_plot_shell.height = (
                CALIBRATION_WAVELENGTH_PLOT_HEIGHT_COMPACT if compact_layout else CALIBRATION_WAVELENGTH_PLOT_HEIGHT
            )
        if self.log_area is not None:
            self.log_area.height = DIAGNOSTICS_CARD_TEXT_HEIGHT_COMPACT if compact_layout else DIAGNOSTICS_CARD_TEXT_HEIGHT

        if self.port_spinner is not None:
            self.port_spinner.height = control_height
            self.port_spinner.font_size = f"{body_font_sp}sp"
        if self.normalization_mode_spinner is not None:
            self.normalization_mode_spinner.height = control_height
            self.normalization_mode_spinner.font_size = f"{body_font_sp}sp"
        for text_input in self._text_inputs:
            if text_input.readonly and text_input.multiline:
                text_input.font_size = f"{small_font_sp}sp"
                continue
            if text_input.multiline:
                text_input.font_size = f"{small_font_sp}sp"
                continue
            text_input.height = control_height
            text_input.font_size = f"{body_font_sp}sp"
        for editor in self._multiline_editors:
            editor.height = CALIBRATION_EDITOR_HEIGHT_COMPACT if compact_layout else CALIBRATION_EDITOR_HEIGHT
        for button in self._buttons:
            button.height = button_height
            button.font_size = f"{body_font_sp}sp"
            button.text_size = (
                max(button.width - BUTTON_TEXT_PAD_X, dp(40)),
                max(button.height - BUTTON_TEXT_PAD_Y, dp(20)),
            )
            button.halign = "center"
            button.valign = "middle"
        for label in self._section_titles:
            label.font_size = f"{section_font_sp}sp"
            label.height = notice_height
        for label in self._info_labels:
            label.font_size = f"{body_font_sp}sp"
            label.height = info_height
        for label in self._small_labels:
            label.font_size = f"{small_font_sp}sp"
            label.height = small_height
        for label in self._axis_labels:
            label.font_size = f"{axis_font_sp}sp"
        for row in self._checkbox_rows:
            row.height = checkbox_height
        for label in self._labels_for_wrapping:
            label.text_size = (max(label.width - dp(8), dp(40)), None)

    def _section_title(self, text: str) -> Label:
        """Purpose: create a styled section heading. Rationale: shared formatting avoids repeating label style settings everywhere."""
        label = Label(
            text=f"[b]{text}[/b]",
            markup=True,
            font_size=f"{SECTION_TITLE_FONT_SP}sp",
            color=TEXT_PRIMARY_RGBA,
            font_size=f"{SECTION_TITLE_FONT_SP}sp",
            color=TEXT_PRIMARY_RGBA,
            size_hint_y=None,
            height=HEADER_NOTICE_HEIGHT,
            height=HEADER_NOTICE_HEIGHT,
            halign="left",
            valign="middle",
        )
        return self._register_section_title(label)

    def _info_label(self, text: str) -> Label:
        """Purpose: create a standard info label. Rationale: repeated UI label styling should come from one helper."""
        label = Label(
        return self._register_section_title(label)

    def _info_label(self, text: str) -> Label:
        """Purpose: create a standard info label. Rationale: repeated UI label styling should come from one helper."""
        label = Label(
            text=text,
            color=TEXT_SECONDARY_RGBA,
            color=TEXT_SECONDARY_RGBA,
            size_hint_y=None,
            height=INFO_LABEL_HEIGHT,
            height=INFO_LABEL_HEIGHT,
            halign="left",
            valign="middle",
            font_size=f"{BODY_FONT_SP}sp",
            font_size=f"{BODY_FONT_SP}sp",
        )
        return self._register_info_label(label)

    def _small_label(self, text: str) -> Label:
        """Purpose: create smaller explanatory text. Rationale: helper text should be visually distinct from live status labels."""
        label = Label(
        return self._register_info_label(label)

    def _small_label(self, text: str) -> Label:
        """Purpose: create smaller explanatory text. Rationale: helper text should be visually distinct from live status labels."""
        label = Label(
            text=text,
            color=TEXT_TERTIARY_RGBA,
            font_size=f"{SMALL_FONT_SP}sp",
            color=TEXT_TERTIARY_RGBA,
            font_size=f"{SMALL_FONT_SP}sp",
            size_hint_y=None,
            height=SMALL_LABEL_HEIGHT,
            height=SMALL_LABEL_HEIGHT,
            halign="left",
            valign="top",
        )
        return self._register_small_label(label)
        return self._register_small_label(label)

    def _axis_label(
        self,
        self,
        text: str,
        *,
        halign: str = "right",
        valign: str = "middle",
    ) -> Label:
        """Purpose: create a plot axis label. Rationale: axis labels share a compact style that is easier to manage in one helper."""
        label = Label(
        """Purpose: create a plot axis label. Rationale: axis labels share a compact style that is easier to manage in one helper."""
        label = Label(
            text=text,
            color=TEXT_TERTIARY_RGBA,
            font_size=f"{AXIS_FONT_SP}sp",
            color=TEXT_TERTIARY_RGBA,
            font_size=f"{AXIS_FONT_SP}sp",
            halign=halign,
            valign=valign,
        )
        self._configure_label_wrapping(label)
        return self._register_axis_label(label)
        self._configure_label_wrapping(label)
        return self._register_axis_label(label)

    def _button(self, text: str, handler, **kwargs) -> Button:
        """Purpose: create a styled button bound to a handler. Rationale: button look-and-feel should stay consistent across the UI."""
    def _button(self, text: str, handler, **kwargs) -> Button:
        """Purpose: create a styled button bound to a handler. Rationale: button look-and-feel should stay consistent across the UI."""
        button = Button(
            text=text,
            background_normal="",
            background_color=BUTTON_BACKGROUND_RGBA,
            color=BUTTON_TEXT_RGBA,
            font_size=f"{BODY_FONT_SP}sp",
            halign="center",
            valign="middle",
            background_color=BUTTON_BACKGROUND_RGBA,
            color=BUTTON_TEXT_RGBA,
            font_size=f"{BODY_FONT_SP}sp",
            halign="center",
            valign="middle",
            **kwargs,
        )
        button.bind(
            size=lambda instance, _value: setattr(
                instance,
                "text_size",
                (
                    max(instance.width - BUTTON_TEXT_PAD_X, dp(40)),
                    max(instance.height - BUTTON_TEXT_PAD_Y, dp(20)),
                ),
            )
        )
        button.bind(
            size=lambda instance, _value: setattr(
                instance,
                "text_size",
                (
                    max(instance.width - BUTTON_TEXT_PAD_X, dp(40)),
                    max(instance.height - BUTTON_TEXT_PAD_Y, dp(20)),
                ),
            )
        )
        button.bind(on_release=handler)
        self._buttons.append(button)
        self._buttons.append(button)
        return button

    def _checkbox_row(self, text: str, checkbox: CheckBox) -> BoxLayout:
        """Purpose: lay out a checkbox with its label. Rationale: calibration toggles should use one compact reusable row pattern."""
        row = BoxLayout(size_hint_y=None, height=CHECKBOX_ROW_HEIGHT, spacing=CARD_GAP)
        checkbox.size_hint = (None, None)
        checkbox.size = (CALIBRATION_CHECKBOX_SIZE, CALIBRATION_CHECKBOX_SIZE)
        checkbox_box = BoxLayout(
            size_hint_x=None,
            width=CALIBRATION_CHECKBOX_BOX_WIDTH,
            size_hint_y=None,
            height=CALIBRATION_CHECKBOX_BOX_HEIGHT,
            padding=dp(4),
        )
        with checkbox_box.canvas.before:
            Color(*CALIBRATION_CHECKBOX_BACKGROUND_RGBA)
            checkbox_box._background = RoundedRectangle(radius=[8])  # type: ignore[attr-defined]
            Color(*CALIBRATION_CHECKBOX_BORDER_RGBA)
            checkbox_box._border = Line(rounded_rectangle=[0, 0, 0, 0, 8], width=1.0)  # type: ignore[attr-defined]
        checkbox_box.bind(
            pos=lambda instance, _value: self._update_checkbox_box_canvas(instance),
            size=lambda instance, _value: self._update_checkbox_box_canvas(instance),
        )
        checkbox_box.add_widget(checkbox)
        row.add_widget(checkbox_box)
        state_label = Label(
            text=CALIBRATION_CHECKBOX_STATE_ON_TEXT if checkbox.active else CALIBRATION_CHECKBOX_STATE_OFF_TEXT,
            color=CALIBRATION_CHECKBOX_STATE_ON_RGBA if checkbox.active else CALIBRATION_CHECKBOX_STATE_OFF_RGBA,
            size_hint_x=None,
            width=dp(36),
            halign="center",
            valign="middle",
            font_size=f"{BODY_FONT_SP}sp",
        )
        self._configure_label_wrapping(state_label)
        checkbox.bind(active=lambda _instance, value: self._update_checkbox_state_label(state_label, value))
        row.add_widget(state_label)
        label = Label(
            text=text,
            color=TEXT_SECONDARY_RGBA,
            halign="left",
            valign="middle",
            font_size=f"{BODY_FONT_SP}sp",
        )
        self._configure_label_wrapping(label)
        row.add_widget(label)
        self._checkbox_rows.append(row)
    def _checkbox_row(self, text: str, checkbox: CheckBox) -> BoxLayout:
        """Purpose: lay out a checkbox with its label. Rationale: calibration toggles should use one compact reusable row pattern."""
        row = BoxLayout(size_hint_y=None, height=CHECKBOX_ROW_HEIGHT, spacing=CARD_GAP)
        checkbox.size_hint = (None, None)
        checkbox.size = (CALIBRATION_CHECKBOX_SIZE, CALIBRATION_CHECKBOX_SIZE)
        checkbox_box = BoxLayout(
            size_hint_x=None,
            width=CALIBRATION_CHECKBOX_BOX_WIDTH,
            size_hint_y=None,
            height=CALIBRATION_CHECKBOX_BOX_HEIGHT,
            padding=dp(4),
        )
        with checkbox_box.canvas.before:
            Color(*CALIBRATION_CHECKBOX_BACKGROUND_RGBA)
            checkbox_box._background = RoundedRectangle(radius=[8])  # type: ignore[attr-defined]
            Color(*CALIBRATION_CHECKBOX_BORDER_RGBA)
            checkbox_box._border = Line(rounded_rectangle=[0, 0, 0, 0, 8], width=1.0)  # type: ignore[attr-defined]
        checkbox_box.bind(
            pos=lambda instance, _value: self._update_checkbox_box_canvas(instance),
            size=lambda instance, _value: self._update_checkbox_box_canvas(instance),
        )
        checkbox_box.add_widget(checkbox)
        row.add_widget(checkbox_box)
        state_label = Label(
            text=CALIBRATION_CHECKBOX_STATE_ON_TEXT if checkbox.active else CALIBRATION_CHECKBOX_STATE_OFF_TEXT,
            color=CALIBRATION_CHECKBOX_STATE_ON_RGBA if checkbox.active else CALIBRATION_CHECKBOX_STATE_OFF_RGBA,
            size_hint_x=None,
            width=dp(36),
            halign="center",
            valign="middle",
            font_size=f"{BODY_FONT_SP}sp",
        )
        self._configure_label_wrapping(state_label)
        checkbox.bind(active=lambda _instance, value: self._update_checkbox_state_label(state_label, value))
        row.add_widget(state_label)
        label = Label(
            text=text,
            color=TEXT_SECONDARY_RGBA,
            halign="left",
            valign="middle",
            font_size=f"{BODY_FONT_SP}sp",
        )
        self._configure_label_wrapping(label)
        row.add_widget(label)
        self._checkbox_rows.append(row)
        return row

    def _update_checkbox_box_canvas(self, widget: BoxLayout) -> None:
        """Purpose: keep the checkbox highlight box aligned to its widget. Rationale: custom checkbox framing must follow layout changes."""
        widget._background.pos = widget.pos  # type: ignore[attr-defined]
        widget._background.size = widget.size  # type: ignore[attr-defined]
        widget._border.rounded_rectangle = [widget.x, widget.y, widget.width, widget.height, 8]  # type: ignore[attr-defined]

    def _update_checkbox_state_label(self, label: Label, is_active: bool) -> None:
        """Purpose: update the visible checkbox state tag. Rationale: the calibration toggles should be readable even on low-contrast displays."""
        label.text = CALIBRATION_CHECKBOX_STATE_ON_TEXT if is_active else CALIBRATION_CHECKBOX_STATE_OFF_TEXT
        label.color = CALIBRATION_CHECKBOX_STATE_ON_RGBA if is_active else CALIBRATION_CHECKBOX_STATE_OFF_RGBA

    def _calibration_action_row(self, title: str, description: str, action_key: str) -> Card:
        """Purpose: create one calibration routine entry. Rationale: the manager should present guided calibrations as a readable action list."""
        row_card = Card(size_hint_y=None)
        row_card.bind(minimum_height=row_card.setter("height"))
        row_card.add_widget(self._section_title(title))
        row_card.add_widget(self._small_label(description))
        row_card.add_widget(
            self._button(
                f"Start {title}",
                lambda *_args, key=action_key, display=title: self.run_calibration_task(key, display),
                size_hint_y=None,
                height=BUTTON_HEIGHT,
            )
        )
        return row_card

    def run_calibration_task(self, action_key: str, display_name: str) -> None:
        """Purpose: acknowledge a requested calibration routine. Rationale: the manager should expose task slots even before each routine is fully automated."""
        notices = {
            "pixel_mapping": (
                "Pixel mapping selected. Next step: capture several known light sources and match their peaks to CCD pixels."
            ),
            "dark_reference": "Dark reference capture selected. Cover the sensor and acquire a baseline frame set.",
            "intensity_reference": "Intensity reference selected. Use an even illumination source and record a correction frame.",
            "wavelength_review": "Wavelength review selected. Inspect the current coefficients and compare them to known peaks.",
        }
        self.set_notice(notices.get(action_key, f"{display_name} selected."))

    def _refresh_calibration_summaries(self, config: CalibrationConfig) -> None:
        """Purpose: refresh the summary labels for the editable calibration data blocks. Rationale: the manager should show what is currently loaded without forcing the user to inspect each large text field."""
        if self.bias_summary_label is not None:
            self.bias_summary_label.text = CALIBRATION_BIAS_SUMMARY_TEMPLATE.format(count=len(config.bias_counts))
        if self.dark_summary_label is not None:
            self.dark_summary_label.text = CALIBRATION_DARK_SUMMARY_TEMPLATE.format(count=len(config.dark_offset_counts))
        if self.flat_field_summary_label is not None:
            self.flat_field_summary_label.text = CALIBRATION_FLAT_FIELD_SUMMARY_TEMPLATE.format(
                count=len(config.intensity_correction)
            )
        if self.pixel_mapping_summary_label is not None:
            self.pixel_mapping_summary_label.text = CALIBRATION_WAVELENGTH_SUMMARY_TEMPLATE.format(
                count=len(config.pixel_mapping_points)
            )
        if self.qe_summary_label is not None:
            self.qe_summary_label.text = CALIBRATION_QE_SUMMARY_TEMPLATE.format(
                count=len(config.quantum_efficiency_points)
            )

    def _format_inline_coefficients(self, values: Sequence[float]) -> str:
        """Purpose: format polynomial coefficients for the single-line coefficient field. Rationale: fitted wavelength terms should be easy to review and edit manually afterward."""
        return ", ".join(f"{float(value):.9g}" for value in values)

    def _format_float_vector(self, values: Sequence[float], *, per_line: int = 8) -> str:
        """Purpose: format vector-style calibration data into a readable multiline string. Rationale: long correction arrays are easier to inspect when wrapped across lines."""
        if not values:
            return ""

        lines: list[str] = []
        for start in range(0, len(values), per_line):
            chunk = values[start : start + per_line]
            lines.append(", ".join(f"{float(value):.9g}" for value in chunk))
        return "\n".join(lines)

    def _format_mapping_points(self, points: Sequence[PixelMappingPoint]) -> str:
        """Purpose: format pixel mapping references for the editor. Rationale: saved wavelength references should round-trip cleanly through the text form."""
        return "\n".join(
            f"{float(point.pixel_index):.9g}, {float(point.wavelength_nm):.9g}"
            for point in points
        )

    def _format_response_points(self, points: Sequence[SpectralResponsePoint]) -> str:
        """Purpose: format QE/response points for the editor. Rationale: wavelength/value pairs should be easy to paste in and edit line-by-line."""
        return "\n".join(
            f"{float(point.wavelength_nm):.9g}, {float(point.relative_value):.9g}"
            for point in points
        )

    def _parse_float_vector(self, text: str) -> list[float]:
        """Purpose: parse a vector from comma-, newline-, or whitespace-separated text. Rationale: calibration arrays are often pasted from spreadsheets in different plain-text layouts."""
        cleaned = text.replace(",", " ").replace("\n", " ").replace("\t", " ")
        return [float(part) for part in cleaned.split() if part.strip()]

    def _parse_mapping_points(self, text: str) -> list[PixelMappingPoint]:
        """Purpose: parse pixel-to-wavelength reference pairs from the text editor. Rationale: wavelength calibration should accept simple copied tables from external notes or spreadsheets."""
        points: list[PixelMappingPoint] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = self._split_pair_line(line)
            if len(parts) != 2:
                raise ValueError("invalid mapping row")
            points.append(
                PixelMappingPoint(
                    pixel_index=float(parts[0].strip()),
                    wavelength_nm=float(parts[1].strip()),
                )
            )
        return points

    def _parse_response_points(self, text: str) -> list[SpectralResponsePoint]:
        """Purpose: parse QE / response reference pairs from the text editor. Rationale: response-curve calibration data is naturally stored as wavelength/value rows."""
        points: list[SpectralResponsePoint] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            parts = self._split_pair_line(line)
            if len(parts) != 2:
                raise ValueError("invalid response row")
            points.append(
                SpectralResponsePoint(
                    wavelength_nm=float(parts[0].strip()),
                    relative_value=float(parts[1].strip()),
                )
            )
        return points

    def _split_pair_line(self, line: str) -> list[str]:
        """Purpose: split a two-column calibration line from comma-, tab-, or whitespace-separated text. Rationale: copied calibration tables come from a mix of spreadsheet and plain-text formats."""
        if "," in line:
            return [part for part in line.split(",") if part.strip()]
        return [part for part in line.replace("\t", " ").split() if part.strip()]

    def _configure_label_wrapping(self, label: Label) -> None:
        """Purpose: make labels wrap within their current width. Rationale: narrow layouts need labels to resize instead of clipping."""
        label.bind(
            size=lambda instance, _value: setattr(
                instance,
                "text_size",
                (max(instance.width - dp(8), dp(40)), None),
            )
        )
        self._labels_for_wrapping.append(label)

    def _configure_text_input(self, widget: TextInput) -> None:
        """Purpose: register text inputs for responsive scaling. Rationale: controls should share one resize path instead of per-widget tweaks."""
        widget.font_size = f"{BODY_FONT_SP}sp"
        self._text_inputs.append(widget)

    def _register_multiline_editor(self, widget: TextInput) -> None:
        """Purpose: remember editable multiline calibration boxes. Rationale: large calibration tables need their own responsive height handling instead of being squeezed to single-line control size."""
        self._multiline_editors.append(widget)

    def _register_section_title(self, label: Label) -> Label:
        """Purpose: remember section headers for responsive scaling. Rationale: title sizing should stay synchronized across cards."""
        self._configure_label_wrapping(label)
        self._section_titles.append(label)
        return label

    def _register_info_label(self, label: Label) -> Label:
        """Purpose: remember standard labels for responsive scaling. Rationale: status lines need shared height and font adjustments."""
        self._configure_label_wrapping(label)
        self._info_labels.append(label)
        return label

    def _register_small_label(self, label: Label) -> Label:
        """Purpose: remember helper text labels for responsive scaling. Rationale: explanatory copy needs more height when wrapping."""
        self._configure_label_wrapping(label)
        self._small_labels.append(label)
        return label

    def _register_axis_label(self, label: Label) -> Label:
        """Purpose: remember axis labels for responsive scaling. Rationale: axis text should stay legible but compact on small windows."""
        self._axis_labels.append(label)
        return label


def run_desktop_app(runtime: AppRuntime) -> None:
    """Purpose: launch the Kivy desktop app. Rationale: the entrypoint should only need one simple call to start the UI."""
    """Purpose: launch the Kivy desktop app. Rationale: the entrypoint should only need one simple call to start the UI."""
    DesktopSpectrometerApp(runtime).run()
