# PythonGUI Code Tour

This document explains the current `PythonGUI` project file by file.
It is written for someone who may be new to both this codebase and Python itself.

Last aligned with the source tree on 2026-04-29.

The goal is not just to say what each file contains.
The goal is to explain why each file exists, what each class or function does, and what role it plays in the full spectrometer app.

## Scope Of This Tour

This tour covers source and project files inside `PythonGUI`.
It does not cover generated folders such as `.venv`, `build`, `dist`, or `__pycache__`.

The current app is a Kivy desktop program that:

- opens a serial USB CDC connection to the STM32 firmware
- parses mixed firmware text lines and binary `CCD1` frame packets
- turns raw CCD frames into app-level spectrum frames
- applies the current calibration pipeline for live display and export
- keeps rolling buffers for full session export and compact spectrogram history
- renders a line spectrum or rolling spectrogram
- provides calibration, display/layout, diagnostics, and performance tools

## Top-Level Project Files

### `pyproject.toml`

Purpose:
Defines the Python package, Python version, dependencies, and optional build dependencies.

Important sections:

- `[build-system]`: tells Python tooling to build with setuptools.
- `[project]`: stores the app name, version, README, Python version, and runtime dependencies.
- `[project.optional-dependencies]`: adds `pyinstaller` for standalone executable builds.
- `[tool.setuptools.packages.find]`: makes `backend*` and `frontend*` installable packages.

Runtime dependencies are Kivy, NumPy, Pydantic, and pyserial.

### `desktop_app.py`

Purpose:
This is the entry point for the desktop application.

Definitions:

- `hide_console_window()`: hides the extra Windows console after startup when possible.
- `main()`: resolves paths, configures logging, builds the runtime, hides the console, and launches Kivy.

Why this file matters:
It stays small so startup is easy to follow.
Most real application wiring happens in `backend/core/runtime.py`.

### `run_app.bat`

Purpose:
Launches the desktop app on Windows.

Behavior:

- switches into the `PythonGUI` folder
- checks that `.venv` exists
- runs `desktop_app.py` with `.venv\Scripts\python.exe`

### `install_dependencies.bat`

Purpose:
Creates and updates the local Python environment.

Behavior:

- finds a usable Python 3.12+ interpreter
- creates `.venv` if needed
- upgrades `pip`, `setuptools`, and `wheel`
- installs the project in editable mode with `pip install -e .`

### `vis_nir_spec.spec`

Purpose:
PyInstaller recipe for making a standalone Windows app bundle.

Important pieces:

- `datas`: bundles the default config files.
- `binaries`: gathers binary dependencies from installed packages.
- `hiddenimports`: includes imports PyInstaller may miss.
- `collect_all(...)`: pulls Kivy, NumPy, and serial package assets into the bundle.
- `Analysis`, `PYZ`, `EXE`, and `COLLECT`: describe the normal PyInstaller build stages.

### `README.md`

Purpose:
First-stop guide for running and understanding `PythonGUI`.

## Config Files

### `configs/default_user.json`

Purpose:
Default user-facing settings for connection, device geometry, and UI timing.

Important fields:

- `serial.port`: default COM port.
- `serial.timeout_s`: serial read timeout.
- `serial.reconnect_on_start`: whether startup should reconnect automatically.
- `device.sample_count`: expected total samples in one frame.
- `device.effective_start_index`: first useful pixel.
- `device.effective_sample_count`: number of useful pixels.
- `device.trailing_dummy_count`: dummy pixels after the useful region.
- `device.adc_resolution_bits`: ADC resolution.
- `device.adc_reference_volts`: ADC full-scale voltage.
- `ui.refresh_interval_ms`: requested plot refresh period.
- `ui.max_session_frames`: full-frame export buffer size.

The `UIConfig` model also has display defaults that may not be written in this default JSON file until the user saves active config:

- `live_graph_mode`
- `spectrogram_time_window_s`
- `show_command_card`
- `show_diagnostics_card`
- `show_performance_card`
- `show_frame_data_frame`
- `show_frame_data_layout`
- `show_frame_data_edge`
- `show_frame_data_refresh`
- `show_frame_data_session`
- `show_frame_data_cursor`

### `configs/default_calibration.json`

Purpose:
Default calibration settings for signal correction, wavelength mapping, and response correction.

Important fields:

- `apply_dark_subtraction`
- `apply_intensity_correction`
- `apply_quantum_efficiency_correction`
- `display_normalization_mode`
- `wavelength_coefficients`
- `wavelength_fit_order`
- `pixel_mapping_points`
- `bias_capture_frame_count`
- `bias_counts`
- `dark_offset_counts`
- `intensity_correction`
- `quantum_efficiency_points`
- `quantum_efficiency_normalization_wavelength_nm`

Active user edits are saved to `configs/user.json` and `configs/calibration.json`.

## Package Marker Files

These files mostly mark folders as Python packages and may hold short package descriptions:

- `backend/__init__.py`
- `backend/core/__init__.py`
- `backend/device/__init__.py`
- `backend/models/__init__.py`
- `backend/processing/__init__.py`
- `backend/storage/__init__.py`
- `frontend/__init__.py`

## Model Files

The model files define the structured objects passed between services.
Most are Pydantic models, which means the app gets validation and safe copying behavior.

### `backend/models/config.py`

Purpose:
Defines structured configuration objects for serial settings, device geometry, UI settings, and calibration.

Definitions:

- Constants such as `DEFAULT_TOTAL_SAMPLE_COUNT`, `DEFAULT_EFFECTIVE_START_INDEX`, `DEFAULT_DISPLAY_NORMALIZATION_MODE`, and `DEFAULT_LIVE_GRAPH_MODE`.
- `SerialConfig`: serial-port settings.
- `DeviceConfig`: expected CCD frame layout and ADC characteristics.
- `UIConfig`: refresh timing, session size, graph mode, spectrogram window, and visibility toggles.
- `UserConfig`: groups `serial`, `device`, and `ui`.
- `PixelMappingPoint`: one pixel-to-wavelength reference pair.
- `SpectralResponsePoint`: one wavelength/relative-response pair.
- `CalibrationConfig`: calibration toggles and stored calibration arrays.
- `has_saved_wavelength_mapping(...)`: reports whether the calibration contains real wavelength mapping points and non-default coefficients.
- `ensure_pixel_mode_without_mapping(...)`: resets empty wavelength mappings to pixel mode.

Why this file matters:
It is the source of truth for what settings the app understands.
When JSON files omit newer fields, these models supply defaults.

### `backend/models/frames.py`

Purpose:
Defines packet and frame objects used while receiving, displaying, storing, and exporting spectrometer data.

Definitions:

- `utc_now()`: shared UTC timestamp helper.
- `BannerPacket`: firmware banner or startup line.
- `TextLinePacket`: generic device text line.
- `FramePacket`: one decoded binary frame packet from the STM32.
- `DevicePacket`: type alias for all packet variants.
- `SpectrumFrame`: app-level frame containing raw samples, processed live-display values, spectrogram row data, dark reference, and optional export columns.
- `SpectrogramHistoryFrame`: compact frame row used by the rolling spectrogram.

Notes:

- `SpectrumFrame.adc_counts` preserves the raw samples.
- `SpectrumFrame.live_display_counts` stores the processed 0-to-1 display signal used by the line plot.
- `SpectrumFrame.spectrogram_row` stores a compressed 0-to-1 row for the rolling spectrogram.
- `SpectrumFrame.wavelengths_nm`, `volts`, and `processed_intensity` can be filled lazily during export.

### `backend/models/status.py`

Purpose:
Defines live app status objects.

Definitions:

- `ConnectionState`: disconnected, connecting, connected, or error.
- `DeviceStatus`: current device state, frame counters, sample preview, firmware lines, and errors.
- `SessionStatus`: session ID, start time, buffered frame count, dropped frame count, and last export path.
- `CommandResult`: success/failure result for UI actions.
- `AppSnapshot`: one read-only snapshot used by the UI.

## Core Service Files

The core layer coordinates state, sessions, commands, runtime wiring, and performance metrics.

### `backend/core/state_manager.py`

Purpose:
Owns the app's current live state.

Definitions:

- `StateManager`: thread-safe holder for user config, calibration config, device status, session status, latest spectrum frame, firmware messages, and recent logs.

Important methods:

- `get_user_config()` and `set_user_config(...)`
- `get_calibration_config()` and `set_calibration_config(...)`
- `set_connection_state(...)`
- `add_firmware_message(...)`
- `append_log(...)`
- `reset_frame_tracking()`
- `update_from_frame(...)`
- `set_last_spectrum(...)`
- `latest_spectrum()`
- `set_session_status(...)`
- `snapshot(...)`

Why this file matters:
Multiple threads touch application state.
This class keeps reads and writes guarded by a lock and gives the UI one snapshot to render.

### `backend/core/session_manager.py`

Purpose:
Owns rolling capture buffers and CSV export.

Definitions:

- `DEFAULT_MAX_SPECTROGRAM_HISTORY_FRAMES`: compact spectrogram-history depth.
- `SessionManager`: stores full `SpectrumFrame` objects for export and compact `SpectrogramHistoryFrame` rows for heatmap display.

Important methods:

- `set_max_frames(...)`: resize the full-frame export buffer.
- `set_max_spectrogram_frames(...)`: resize the compact spectrogram buffer.
- `append_frame(...)`: add one full frame and one compact spectrogram row when available.
- `set_spectrum_builder(...)`: provide the export-time processing helper.
- `reset()`: start a fresh session.
- `export_csv()`: write the full-frame buffer to `exports/spectrometer_session_*.csv`.
- `frames()`: return buffered full frames.
- `spectrogram_frames()`: return compact history rows.
- `status()`: return the current `SessionStatus`.

Why this file matters:
The line plot and CSV export need full data, while the rolling spectrogram needs many rows without keeping an unbounded raw-frame history.

### `backend/core/runtime.py`

Purpose:
Creates and wires together the application's main objects.

Definitions:

- `RuntimePaths`: bundle root, project root, log directory, log file, and frozen-app flag.
- `AppRuntime`: immutable bundle of all services used by the UI.
- `resolve_runtime_paths(...)`: handles source-tree vs PyInstaller path layout.
- `configure_logging(...)`: configures file and console logging.
- `build_runtime(...)`: loads configs, normalizes calibration, creates stores/services, and returns `AppRuntime`.

Why this file matters:
It is the composition root.
If you want to know what objects exist and how they are connected, start here.

### `backend/core/command_service.py`

Purpose:
Acts as the control layer between transport, parsing, state updates, session buffering, calibration updates, and UI commands.

Definitions:

- `CommandService`: main coordinator for connection management, incoming bytes, config application, raw commands, frame processing, missed-frame detection, and packet queue handling.

Important methods:

- `list_serial_ports()`
- `connect(...)`
- `disconnect()`
- `send_raw_command(...)`
- `apply_user_config(...)`
- `apply_calibration_config(...)`
- `refresh_session_status()`
- `_handle_transport_state(...)`
- `_handle_bytes(...)`
- `_processing_loop()`
- `_process_packet(...)`
- `_clear_pending_bytes()`

Why this file matters:
It keeps the serial reader thread light by pushing packet parsing and frame processing to a worker queue.
It is also where frame-size mismatch warnings, missed-frame logging, and performance counters are recorded.

### `backend/core/performance_monitor.py`

Purpose:
Collects rolling timing, value, and counter metrics from backend and UI paths.

Definitions:

- `PerformanceMetricSnapshot`: timing metric summary.
- `PerformanceValueSnapshot`: rolling numeric signal summary.
- `PerformanceCounterSnapshot`: event-counter summary.
- `PerformanceMonitor`: records durations, values, counters, snapshots, and a formatted report.

Important methods:

- `measure(...)`: context manager for timing a block.
- `set_enabled(...)`: pause or resume metric collection.
- `reset()`: clear all rolling metrics.
- `record_duration(...)`
- `record_value(...)`
- `increment(...)`
- `snapshot()`
- `snapshot_values()`
- `snapshot_counters()`
- `format_report(...)`

Why this file matters:
The Performance card uses this report to explain stream rate, UI cadence, queue pressure, missed frames, and likely 125 Hz bottlenecks.

## Device Files

The device layer talks to external hardware and rebuilds structured packets from raw USB CDC bytes.

### `backend/device/base_transport.py`

Purpose:
Defines the abstract interface every transport must follow.

Definitions:

- `BytesCallback`: callback type for raw bytes.
- `StateCallback`: callback type for connection-state changes.
- `BaseTransport`: abstract base class with callback registration and required transport methods.

Required methods:

- `connect(...)`
- `disconnect()`
- `write(...)`
- `is_connected()`
- `list_ports()`

### `backend/device/serial_transport.py`

Purpose:
Implements the real COM-port transport with `pyserial`.

Definitions:

- `SerialTransport`: opens the serial port, starts a reader thread, writes bytes with a lock, and lists visible COM ports.

Why this file matters:
Everything outside this module can talk to a transport abstraction instead of directly calling `serial.Serial(...)`.

### `backend/device/wifi_transport.py`

Purpose:
Placeholder for a future WiFi transport.

Current behavior:
All required transport operations raise `NotImplementedError` or report disconnected/no ports.

### `backend/device/packet_reader.py`

Purpose:
Turns arbitrary byte chunks into complete packet objects.

Definitions:

- `DeviceStreamReader`: buffered parser for mixed text and binary device streams.
- `FRAME_HEADER_LIMIT`: safety limit for trimming invalid buffer data.

Important methods:

- `feed(...)`: appends bytes, parses complete `CCD1` frames or newline text, handles text before a binary frame, and returns packet objects.
- `reset()`: clears the parse buffer during reconnect/disconnect.

### `backend/device/protocol.py`

Purpose:
Defines the wire-level protocol for firmware text and binary frame packets.

Definitions:

- `PACKET_MAGIC`: `b"CCD1"`.
- `PACKET_VERSION`: current binary protocol version.
- `PACKET_TYPE_FRAME`: frame packet type code.
- `MAX_BINARY_SAMPLE_COUNT`: parser safety cap.
- `FRAME_HEADER_STRUCT`: little-endian binary header layout.
- `parse_device_line(...)`: classifies banner/status lines vs generic text.
- `encode_raw_command(...)`: converts raw UI command text into an ASCII line ending.
- `try_parse_binary_frame(...)`: validates and decodes one binary frame packet.

Packet shape:
The firmware sends a packed header matching `<4sBBHIHHHHI` followed by `sample_count * 2` bytes of little-endian unsigned 16-bit ADC samples.

## Processing Files

The processing layer turns raw ADC counts into display, export, and calibration outputs.

### `backend/processing/adc_converter.py`

Purpose:
Converts ADC counts into volts.

Definitions:

- `counts_to_volts(...)`: scales counts by ADC resolution and reference voltage.

### `backend/processing/dark_subtraction.py`

Purpose:
Provides additive dark/bias helpers.

Definitions:

- `estimate_dark_level(...)`: median dark reference from an index range.
- `subtract_dark_level(...)`: subtract one scalar baseline from all samples.
- `apply_dark_subtraction(...)`: subtract a direct or index-mapped dark vector.

### `backend/processing/intensity_correction.py`

Purpose:
Applies multiplicative correction factors.

Definitions:

- `apply_intensity_correction(...)`: multiplies values by direct or index-mapped correction factors.

### `backend/processing/wavelength_map.py`

Purpose:
Maps sample indices to wavelengths.

Definitions:

- `indices_to_wavelengths(...)`: evaluates polynomial coefficients with sample index as the input.

### `backend/processing/calibration_manager.py`

Purpose:
Owns calibration settings and higher-level calibration operations.

Definitions:

- `MIN_RESPONSE_VALUE`: lower bound for QE/response correction factors.
- `CalibrationManager`: stores current calibration config and applies calibration math.

Important methods:

- `config`: returns the current config.
- `update_config(...)`: replaces the current config.
- `capture_bias_from_frames(...)`: averages covered-sensor frames into a master bias vector `B_p`.
- `fit_wavelength_coefficients(...)`: fits wavelength polynomial coefficients from pixel mapping points.
- `build_quantum_efficiency_curve(...)`: interpolates and normalizes a wavelength-dependent response curve.
- `apply(...)`: runs a general calibration path returning wavelengths, volts, and intensity.

### `backend/processing/spectrum_builder.py`

Purpose:
Builds `SpectrumFrame` objects and derived export columns from raw frame packets.

Definitions:

- `FRAME_DARK_START_INDEX` and `FRAME_DARK_END_INDEX`: shielded pixel range used for frame-wise dark reference.
- `SPECTROGRAM_ROW_TARGET_WIDTH`: compact heatmap row width.
- `SpectrumBuilder`: main frame conversion and live/export processing helper.

Important methods:

- `update_device_config(...)`: stores updated ADC/device settings.
- `build_from_frame(...)`: builds one `SpectrumFrame` with raw counts, processed live-display counts, dark reference, and compact spectrogram row.
- `rebuild_live_frame(...)`: rebuilds the latest frame when calibration changes.
- `build_export_columns(...)`: computes processed counts, wavelengths, volts, normalized intensity, and dark reference during CSV export.
- `_build_processed_columns(...)`: central calibration pipeline shared by live display and export.
- `_build_spectrogram_row(...)`: compresses effective pixels into a fixed-width heatmap row.
- `_normalize_processed_signal(...)`: supports absolute-saturation and auto-peak display normalization.
- `_normalize_spectrogram_signal(...)`: keeps rolling spectrogram color scale comparable across frames.

Why this file matters:
It is the bridge between raw hardware packets and what the user sees.
The app preserves raw ADC samples while plotting processed display values.

## Storage Files

The storage layer reads/writes JSON config and CSV exports.

### `backend/storage/config_store.py`

Purpose:
Loads and saves user config files.

Definitions:

- `ConfigStore`: reads the active user config if present, otherwise the default config, and saves active config.

### `backend/storage/calibration_store.py`

Purpose:
Loads and saves calibration config files.

Definitions:

- `CalibrationStore`: mirrors `ConfigStore` for calibration settings.

### `backend/storage/export_csv.py`

Purpose:
Exports stored frames to a CSV file.

Definitions:

- `export_spectra_csv(...)`: writes one row per sample and asks `SpectrumBuilder` for derived columns when needed.

CSV columns:

- `frame_id`
- `timestamp`
- `source`
- `expected_sample_count`
- `effective_start_index`
- `effective_sample_count`
- `frame_flags`
- `sample_index`
- `wavelength_nm`
- `raw_adc_count`
- `processed_adc_count`
- `frame_dark_reference_count`
- `volts`
- `processed_intensity`

## Frontend File

### `frontend/kivy_app.py`

Purpose:
Defines the entire desktop user interface.

Major classes:

- `Card`: reusable styled panel container.
- `SpectrumPlot`: custom line-plot widget with cursor support.
- `SpectrogramPlot`: custom heatmap widget backed by a Kivy texture.
- `XAxisLabels`: custom x-axis label widget.
- `YAxisLabels`: custom y-axis label widget.
- `DesktopSpectrometerApp`: Kivy application class that builds the UI and handles user actions.
- `run_desktop_app(...)`: starts the prepared Kivy app.

#### `Card`

Purpose:
Shared rounded panel used for header, side-panel cards, and manager cards.

#### `SpectrumPlot`

Purpose:
Draws the processed line spectrum with guide lines and an optional cursor.

Important methods:

- `set_series(...)`
- `set_cursor_callback(...)`
- `current_cursor_value()`
- `set_adc_range(...)`
- `set_grid_counts(...)`
- touch handlers for click/drag cursor updates
- `_iter_line_chunks(...)`

#### `SpectrogramPlot`

Purpose:
Draws recent compact frame rows as a rolling heatmap.

Important methods:

- `set_frame_history(...)`
- `_try_incremental_texture_update(...)`
- `_build_texture(...)`
- `_fit_row_width(...)`
- `_encode_row_rgba(...)`
- `_heatmap_rgb(...)`

Why this class matters:
The spectrogram uses compact normalized rows so the UI can show a recent time window without redrawing thousands of raw pixels per frame.

#### `XAxisLabels` and `YAxisLabels`

Purpose:
Draw axis labels in custom widgets so labels align with the plot area and can switch between modes.

The x-axis shows pixel indices until saved wavelength mapping exists, then shows wavelength labels.
The spectrogram y-axis shows recent elapsed time labels ending at `Now`.

#### `DesktopSpectrometerApp`

Purpose:
Owns the window, widget references, user actions, timed refresh, responsive layout, calibration workflows, and display/layout settings.

Important user-facing actions:

- `refresh_ports(...)`
- `connect_device(...)`
- `disconnect_device(...)`
- `toggle_live_display(...)`
- `save_user_config(...)`
- `save_calibration(...)`
- `preview_calibration(...)`
- `capture_bias_reference(...)`
- `start_guided_pixel_mapping(...)`
- `capture_guided_pixel_mapping_point(...)`
- `reset_guided_pixel_mapping(...)`
- `fit_wavelength_coefficients_from_points(...)`
- `export_session(...)`
- `reset_session(...)`
- `send_raw_command(...)`
- `open_calibration_manager(...)`
- `open_display_manager(...)`
- `show_spectrum_view(...)`
- `toggle_side_panel(...)`

Important refresh/layout helpers:

- `refresh_status(...)`: slower status/log/performance refresh.
- `refresh_plot(...)`: fast graph refresh for line spectrum, spectrogram, cursor, and frame labels.
- `refresh_view(...)`: immediate status and plot refresh.
- `_apply_live_graph_mode(...)`: swaps between line plot and spectrogram.
- `_spectrogram_source_frames(...)`: selects rows inside the configured time window.
- `_build_spectrogram_rows(...)`: gathers compact rows for the heatmap.
- `_apply_frame_data_label_visibility(...)`: hides selected Frame Data rows.
- `_apply_performance_monitor_state(...)`: pauses/resumes metrics when the Performance card is hidden/shown.
- `_apply_responsive_layout(...)`: adapts side-by-side vs stacked layout and plot sizing.

## Typical End-To-End Capture

Here is what happens during a normal frame capture:

1. The user opens the app with `run_app.bat`.
2. `desktop_app.py` builds the runtime and starts Kivy.
3. The user clicks `Connect`.
4. `CommandService.connect(...)` opens the COM port through `SerialTransport`.
5. `SerialTransport` starts reading USB CDC bytes from the STM32.
6. `CommandService` queues the raw chunks.
7. `DeviceStreamReader` rebuilds packets.
8. `protocol.py` recognizes a binary `CCD1` frame.
9. `CommandService._process_packet(...)` updates state and session tracking.
10. `SpectrumBuilder.build_from_frame(...)` builds processed live-display values and a compact spectrogram row.
11. `DesktopSpectrometerApp.refresh_plot(...)` redraws the selected graph mode.
12. If the user clicks `Export Session CSV`, `SessionManager.export_csv()` and `export_spectra_csv(...)` write buffered data to disk.

## Typical Calibration Update

Here is what happens when calibration changes:

1. The user opens `Calibration Manager`.
2. The user edits toggles, vectors, mapping points, QE points, or normalization mode.
3. `Preview Calibration` reads the form into a `CalibrationConfig`.
4. `CommandService.apply_calibration_config(...)` normalizes pixel/wavelength mode and updates `CalibrationManager`.
5. If a latest frame exists, `SpectrumBuilder.rebuild_live_frame(...)` rebuilds its processed display values.
6. `StateManager` stores the updated frame and calibration config.
7. `refresh_view()` updates the graph and summaries.
8. `Save Calibration` writes the calibration JSON and also syncs user config.

## Best Files To Read First

If you want to understand the code in the most natural order, start here:

1. `desktop_app.py`
2. `backend/core/runtime.py`
3. `backend/models/config.py`
4. `backend/models/frames.py`
5. `backend/models/status.py`
6. `backend/core/command_service.py`
7. `backend/core/session_manager.py`
8. `backend/device/protocol.py`
9. `backend/device/packet_reader.py`
10. `backend/device/serial_transport.py`
11. `backend/processing/spectrum_builder.py`
12. `backend/processing/calibration_manager.py`
13. `backend/core/performance_monitor.py`
14. `backend/storage/export_csv.py`
15. `frontend/kivy_app.py`

## Final Mental Model

The simplest way to think about this project is:

- `device` gets and decodes the bytes
- `protocol` defines what the bytes mean
- `core` coordinates state, sessions, commands, and metrics
- `processing` turns raw samples into display and export values
- `storage` saves configs and CSV files
- `frontend` shows the live instrument and tools

That is the full desktop system in one pass.
