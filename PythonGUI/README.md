# PythonGUI

`PythonGUI` is the desktop control program for the VIS-NIR spectrometer.
It is written in Python 3.12+ and runs as a native Kivy desktop window.

Last aligned with the source tree on 2026-04-29.

This folder contains the desktop-side pipeline:

- opening the USB serial connection to the STM32 board
- rebuilding incoming text lines and `CCD1` binary frame packets
- tracking connection state, recent logs, and the latest frame
- applying the live calibration pipeline for display values
- maintaining rolling session and spectrogram-history buffers
- exporting captured frames to CSV
- drawing either a live line spectrum or a rolling spectrogram
- providing calibration, display/layout, diagnostics, and performance tools

The current STM32 firmware is expected to stream:

- a full `3694`-sample binary frame
- `32` leading dummy samples
- `3648` effective light-sensitive samples
- `14` trailing dummy samples
- frame timing tied to the CCD ICG edges

## Start Here

Install dependencies with:

```bat
install_dependencies.bat
```

Run the desktop app with:

```bat
run_app.bat
```

The launcher expects a `.venv` in this folder. `install_dependencies.bat` creates it when needed and installs this package in editable mode with the dependencies from `pyproject.toml`.

The PyInstaller packaging recipe lives in:

```text
vis_nir_spec.spec
```

## If You Are New To Python

If you have never worked with Python before, these words show up everywhere in this code:

- A `file` is a single `.py` module.
- A `function` is a named block of code that does one job.
- A `class` is a blueprint for building objects that hold data and behavior together.
- An `object` is one live instance of a class.
- A `method` is a function that belongs to a class.
- A `thread` is a separate stream of execution that can run alongside the main program.
- A `config` file is saved settings, usually JSON in this project.

Python reads very literally from top to bottom.
Imports pull in code from other files.
Functions and classes are defined first, then the program starts running from an entry point such as `main()`.

## Project Layout

Here is the big picture of the folder:

- `desktop_app.py`: the real program entry point for the desktop app
- `pyproject.toml`: Python package metadata and dependencies
- `run_app.bat`: Windows launcher for the app
- `install_dependencies.bat`: Windows setup script for `.venv`
- `vis_nir_spec.spec`: PyInstaller packaging recipe
- `frontend/`: the Kivy user interface
- `backend/models/`: shared data structures
- `backend/core/`: application services, runtime wiring, state, sessions, commands, and performance metrics
- `backend/device/`: serial transport and packet parsing
- `backend/processing/`: ADC conversion, calibration, wavelength, and spectrogram helpers
- `backend/storage/`: config loading/saving and CSV export
- `configs/`: default settings files
- `logs/`: runtime logs written while the app is running
- `exports/`: CSV exports created at runtime

For the detailed file-by-file walkthrough, read:

```text
CODE_TOUR.md
```

## How The Program Starts

When you run `run_app.bat`, the startup path is:

1. `run_app.bat` switches into `PythonGUI`, checks for `.venv`, and launches `desktop_app.py`.
2. `desktop_app.py` sets Kivy environment options before importing Kivy UI code.
3. `desktop_app.py` resolves runtime paths and configures logging.
4. `desktop_app.py` builds the shared runtime by calling `build_runtime(...)` in `backend/core/runtime.py`.
5. `build_runtime(...)` loads user and calibration configs, normalizes the calibration map, creates service objects, and wires them together.
6. `desktop_app.py` hides the extra Windows console when possible and starts the Kivy app with `run_desktop_app(runtime)`.
7. `frontend/kivy_app.py` builds the window and schedules timed refresh callbacks for plot, status, logs, and optional performance reporting.

## Live Data Flow

Once the user presses `Connect`, data moves through the program like this:

1. `SerialTransport.connect(...)` opens the selected COM port.
2. `SerialTransport` starts a serial reader thread.
3. The reader thread continuously reads raw bytes from the STM32 board.
4. The bytes are handed to `CommandService._handle_bytes(...)`.
5. `CommandService` places those bytes into a queue so the reader thread stays light.
6. A separate processor thread inside `CommandService` takes queued byte chunks.
7. `DeviceStreamReader.feed(...)` rebuilds complete text packets and binary frame packets from the incoming byte stream.
8. `protocol.py` validates the `CCD1` frame header and decodes the little-endian 16-bit ADC payload.
9. `CommandService._process_packet(...)` updates frame counters, missed-frame counters, logs, and state.
10. `SpectrumBuilder.build_from_frame(...)` builds a `SpectrumFrame` with raw samples, processed live display values, and a compressed spectrogram row.
11. `StateManager` stores the latest status and newest spectrum frame.
12. `SessionManager` appends the full frame to the export buffer and the compact row to the spectrogram-history buffer.
13. The Kivy UI polls the latest state on timers and redraws the selected graph mode.

## What Runs Separately

Several parts run independently so the graph stays responsive while data keeps arriving:

- The main Kivy UI thread owns the window, buttons, labels, graph widgets, and refresh timers.
- The serial reader thread inside `SerialTransport` only reads USB CDC bytes and emits callbacks.
- The packet processor thread inside `CommandService` parses chunks and updates backend state.
- The session manager keeps bounded rolling buffers for full-frame export data and compact spectrogram rows.
- CSV export runs only when the user asks to save the buffered session.

This split keeps USB reads, binary packet rebuilding, calibration processing, UI painting, and file output from blocking each other unnecessarily.

## Main UI Areas

The current app opens as a measurement workspace with a side panel and a main display area.

The side panel includes:

- `Connection`: COM-port refresh, connect/disconnect, and live-display pause/resume
- `Tools`: buttons for the calibration manager and display/layout manager
- `Session And Commands`: raw USB CDC command entry, CSV export, and session reset
- `Frame Data`: frame, layout, edge-sample, refresh-rate, session, and cursor readouts
- `Performance`: optional timing and throughput report
- `Diagnostics`: recent log messages

The main display can show:

- `Live Spectrum`: a processed line plot of the current effective pixels
- `Rolling Spectrogram`: a heatmap built from recent compact frame rows
- `Calibration Manager`: the full calibration workflow
- `Display & Layout`: graph-mode, spectrogram-window, side-panel, and frame-data visibility settings

## Calibration Pipeline

The live graph is no longer a raw-only ADC plot.
`SpectrumBuilder` stores raw ADC counts for export and debugging, but the visible line spectrum uses the current processed display signal when available.

The processing path is:

1. Convert raw ADC counts to floating point.
2. Remove stored master bias `B_p` if bias counts are configured.
3. Estimate a frame-wise dark reference from shielded pixels `16` through `28` when dark subtraction is enabled.
4. Convert the inverted CCD readout into light-tracking counts.
5. Apply stored master-dark offsets if configured.
6. Apply flat-field / PRNU multiplicative correction if enabled.
7. Apply QE / response correction if enabled.
8. Build wavelengths from the current polynomial coefficients.
9. Normalize the display either by absolute saturation reference or per-frame auto peak.
10. Compress a stable 0-to-1 row for the rolling spectrogram.

CSV export writes both raw and derived columns:

- `raw_adc_count`
- `processed_adc_count`
- `frame_dark_reference_count`
- `wavelength_nm`
- `volts`
- `processed_intensity`

## Calibration Manager

The calibration manager is opened from `Tools` and gives the calibration workflow more space than the side panel.

It currently supports:

- processing toggles for dark subtraction, intensity correction, and QE/response correction
- display normalization mode: `Absolute Saturation` or `Auto Range`
- direct wavelength polynomial editing
- wavelength fit order control
- master bias `B_p` capture from recent covered-sensor frames
- master bias and master-dark vector editing
- manual pixel-to-wavelength mapping point entry
- guided laser-diode mapping by clicking a peak on the plot and capturing that pixel
- coefficient fitting from saved mapping points
- flat-field / PRNU correction factor entry
- QE / response point entry and normalization wavelength selection
- previewing calibration without saving
- saving calibration and syncing user config

The x-axis stays in pixel mode until saved wavelength mapping points and non-default coefficients exist.
This prevents stale coefficient text from making an uncalibrated graph look wavelength-calibrated.

## Display And Layout Manager

The display/layout manager is opened from `Tools`.

It currently controls:

- line spectrum vs rolling spectrogram graph mode
- spectrogram time window: `2 s`, `5 s`, `10 s`, or `20 s`
- visibility of the Session And Commands card
- visibility of the Diagnostics card
- visibility of the Performance card
- visibility of individual Frame Data rows

Some display settings are stored in memory immediately and are written to `configs/user.json` when user settings are saved.
If a field is absent from `configs/default_user.json`, the Pydantic model default in `backend/models/config.py` is used.

## Performance Diagnostics

`backend/core/performance_monitor.py` collects rolling timing, value, and counter metrics from both backend and UI paths.

The Performance card is disabled by default.
When hidden, the monitor is paused so performance sampling does not keep perturbing the hot path.
When enabled, the report highlights:

- likely 125 Hz limiting stage
- observed frame and byte throughput
- serial chunk timing and size
- queue wait and depth
- display age
- UI refresh and paint cadence
- missed frames, skipped redraws, and buffer overwrites
- timing-budget checkpoints for backend and UI stages

## Frame Layout Validation

The app expects full CCD binary frames from the STM32, but it does not invent missing samples.

If the device sends a frame whose sample count does not match the configured layout, the app logs a frame-size warning and plots exactly what was received.
For full frames, only the effective pixels are plotted so leading and trailing dummy samples do not dominate the display.

## Configuration Files

The most important JSON files are:

- `configs/default_user.json`: default connection, device, and UI settings
- `configs/default_calibration.json`: default calibration settings
- `configs/user.json`: active user settings if present
- `configs/calibration.json`: active calibration settings if present

The code loads the active file first when it exists.
If it does not exist yet, it falls back to the default file.

User config is structured as:

- `serial.port`
- `serial.timeout_s`
- `serial.reconnect_on_start`
- `device.sample_count`
- `device.effective_start_index`
- `device.effective_sample_count`
- `device.trailing_dummy_count`
- `device.adc_resolution_bits`
- `device.adc_reference_volts`
- `ui.refresh_interval_ms`
- `ui.max_session_frames`
- `ui.live_graph_mode`
- `ui.spectrogram_time_window_s`
- `ui.show_command_card`
- `ui.show_diagnostics_card`
- `ui.show_performance_card`
- `ui.show_frame_data_frame`
- `ui.show_frame_data_layout`
- `ui.show_frame_data_edge`
- `ui.show_frame_data_refresh`
- `ui.show_frame_data_session`
- `ui.show_frame_data_cursor`

Calibration config is structured as:

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

## Logs And Exports

The app writes logs to:

```text
logs/vis_nir_spec.log
```

CSV exports are written under:

```text
exports/
```

The log file is useful when:

- the app fails during startup
- the serial connection fails
- frames are missed
- the firmware sends unexpected data
- a calibration or export action fails

## Recommended Reading Order

If you want to understand the project from top to bottom, this is a good reading order:

1. `desktop_app.py`
2. `backend/core/runtime.py`
3. `backend/models/config.py`
4. `backend/models/frames.py`
5. `backend/models/status.py`
6. `backend/core/command_service.py`
7. `backend/core/session_manager.py`
8. `backend/core/performance_monitor.py`
9. `backend/device/`
10. `backend/processing/spectrum_builder.py`
11. `backend/processing/calibration_manager.py`
12. `backend/storage/`
13. `frontend/kivy_app.py`
14. `CODE_TOUR.md`

## Detailed Documentation

For the file-by-file walkthrough that explains every module and the main runtime paths, read:

```text
CODE_TOUR.md
```
