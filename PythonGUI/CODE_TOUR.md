# PythonGUI Code Tour

This document explains the current `PythonGUI` project file by file.
It is written for someone who may be new to both this codebase and Python itself.

The goal is not just to say what each file contains.
The goal is to explain why each file exists, what each class or function does, and what role it plays in the full spectrometer app.

## Scope Of This Tour

This tour covers the current source and project files inside `PythonGUI`.
It focuses on code and project structure, not generated folders such as `.venv`, `build`, `dist`, or `__pycache__`.

## Top-Level Project Files

### `pyproject.toml`

Purpose:
This is the project definition file for Python packaging and dependency installation.

Rationale:
Instead of manually installing packages one by one, this file gives Python tools one central place to read the app name, Python version, and required libraries.

Sections:

- `[build-system]`: tells Python how this package should be built.
- `[project]`: stores the package name, version, summary, README, Python version requirement, and runtime dependencies.
- `[project.optional-dependencies]`: defines extra packages that are only needed for special tasks such as building a standalone executable.
- `[tool.setuptools.packages.find]`: tells setuptools which folders should be treated as Python packages.

### `desktop_app.py`

Purpose:
This is the real entry point for the desktop application.

Rationale:
Keeping the entry point small makes startup easier to understand.
This file prepares Kivy, builds the shared runtime, hides the extra console window on Windows, and launches the UI.

Definitions:

- `hide_console_window()`: hides the Windows console window after startup so the user only sees the desktop app.
- `main()`: builds runtime paths, sets up logging, constructs all app services, hides the console, and launches the Kivy app.

### `run_app.bat`

Purpose:
This is the simplest launcher for Windows users.

Rationale:
It saves the user from having to remember the Python command.

Behavior:

- switches into the `PythonGUI` folder
- checks that `.venv` exists
- runs `desktop_app.py` with the virtual environment's Python interpreter

### `install_dependencies.bat`

Purpose:
This installs the Python environment for the project.

Rationale:
The batch file makes setup easier for users who are not comfortable running `pip` commands manually.

Behavior:

- finds a usable Python 3.12+ interpreter
- creates `.venv` if needed
- upgrades `pip`, `setuptools`, and `wheel`
- installs the project in editable mode with `pip install -e .`

### `vis_nir_spec.spec`

Purpose:
This is the PyInstaller recipe for turning the Python app into a standalone Windows executable.

Rationale:
A spec file gives fine control over which files and hidden imports must be bundled.

Important pieces:

- `datas`: bundles default JSON config files into the packaged app.
- `binaries`: collects binary dependencies from packages.
- `hiddenimports`: collects imports PyInstaller might miss automatically.
- `collect_all(...)` loops: gather Kivy, NumPy, and serial package data.
- `Analysis(...)`: tells PyInstaller what script is the entry point and what assets to include.
- `PYZ(...)`: builds the compressed Python archive.
- `EXE(...)`: defines the executable itself.
- `COLLECT(...)`: gathers the final bundle contents into the output folder.

### `README.md`

Purpose:
This is the first-stop project guide.

Rationale:
It explains the project at a high level and gives new readers a mental map before they dive into the code.

### `configs/default_user.json`

Purpose:
This file stores the default user-facing settings for connection, device geometry, and UI timing.

Rationale:
Keeping defaults in JSON makes the app behavior editable without changing Python code.

Fields:

- `serial.port`: default COM port name.
- `serial.timeout_s`: serial read timeout.
- `serial.reconnect_on_start`: whether the app should auto-connect on launch.
- `device.sample_count`: expected total samples in one frame.
- `device.effective_start_index`: where the useful pixels begin.
- `device.effective_sample_count`: number of useful pixels.
- `device.trailing_dummy_count`: number of dummy pixels after the useful region.
- `device.adc_resolution_bits`: ADC resolution.
- `device.adc_reference_volts`: ADC full-scale voltage.
- `ui.refresh_interval_ms`: requested plot refresh period.
- `ui.max_session_frames`: session buffer size in frames.

### `configs/default_calibration.json`

Purpose:
This file stores default calibration settings.

Rationale:
It separates raw app behavior from scientific correction settings.

Fields:

- `apply_dark_subtraction`: whether dark offsets should be removed.
- `apply_intensity_correction`: whether multiplicative correction should be applied.
- `wavelength_coefficients`: polynomial coefficients for mapping pixel index to wavelength.
- `dark_offset_counts`: optional per-pixel dark offsets.
- `intensity_correction`: optional per-pixel scale factors.

### `logs/vis_nir_spec.log`

Purpose:
This is the runtime log output file.

Rationale:
It gives a persistent record of what the app did, which helps with debugging without needing the console window.

## Package Marker Files

These files exist mostly to mark folders as Python packages and to hold short package descriptions.
They contain no active logic.

### `backend/__init__.py`

Purpose:
Marks `backend` as a package.

Rationale:
This lets Python import code from the folder using package paths like `backend.core.runtime`.

### `backend/core/__init__.py`

Purpose:
Marks `backend/core` as a package and labels it as the home of the main services.

### `backend/device/__init__.py`

Purpose:
Marks `backend/device` as a package and labels it as the transport and protocol layer.

### `backend/models/__init__.py`

Purpose:
Marks `backend/models` as a package and labels it as the shared data-model layer.

### `backend/processing/__init__.py`

Purpose:
Marks `backend/processing` as a package and labels it as the math helper layer.

### `backend/storage/__init__.py`

Purpose:
Marks `backend/storage` as a package and labels it as the persistence layer.

### `frontend/__init__.py`

Purpose:
Marks `frontend` as a package and labels it as the UI layer.

## Model Files

The model files define the shapes of the data moving through the app.
These are mostly Pydantic models, which means they are structured Python objects with validation support.

### `backend/models/config.py`

Purpose:
Defines structured configuration objects for the app.

Rationale:
Using classes for config makes the rest of the code easier to read than passing around loose dictionaries.

Definitions:

- `SerialConfig`: stores serial-port settings.
- `DeviceConfig`: stores expected CCD geometry and ADC characteristics.
- `UIConfig`: stores user-interface timing and session-buffer settings.
- `UserConfig`: groups `serial`, `device`, and `ui` into one object.
- `CalibrationConfig`: stores calibration choices and correction arrays.

### `backend/models/frames.py`

Purpose:
Defines the packet and frame objects used while receiving and storing spectrometer data.

Rationale:
Separating raw incoming packet types from stored spectrum frames makes the data flow easier to reason about.

Definitions:

- `utc_now()`: helper that returns the current UTC timestamp.
- `BannerPacket`: a structured wrapper for firmware banner lines or startup messages.
- `TextLinePacket`: a structured wrapper for any plain text line that is not treated as a banner.
- `FramePacket`: the direct parsed representation of one incoming device frame packet.
- `DevicePacket`: a type alias meaning "one of the supported incoming packet types."
- `SpectrumFrame`: the app's stored representation of a frame after the backend has accepted it.

Notes:

- `SpectrumFrame.adc_counts` is the most important live-data field for the plot.
- `SpectrumFrame.wavelengths_nm`, `volts`, and `processed_intensity` may be empty during live operation and then filled on export.

### `backend/models/status.py`

Purpose:
Defines application status objects.

Rationale:
This separates live state from configuration and raw frame data.

Definitions:

- `utc_now()`: helper that returns the current UTC timestamp.
- `ConnectionState`: enum describing whether the device is disconnected, connecting, connected, or in error.
- `DeviceStatus`: everything the UI needs to know about the device right now.
- `SessionStatus`: session buffer state, such as how many frames are stored.
- `CommandResult`: a small success-or-failure result object for UI commands.
- `AppSnapshot`: one combined view of device status, session status, latest spectrum, and recent logs.

## Core Service Files

The core layer coordinates the whole application.

### `backend/core/state_manager.py`

Purpose:
Owns the app's current live state.

Rationale:
The UI and services need one central place to read and update state safely.

Definitions:

- `utc_now()`: helper that returns the current UTC timestamp.
- `StateManager`: thread-safe holder for configs, device status, session status, last spectrum, and logs.

Important `StateManager` methods:

- `__init__(...)`: builds the initial in-memory state objects.
- `new_session_id()`: creates a short random session ID.
- `get_user_config()`: returns a safe copy of the user config.
- `set_user_config(...)`: stores new user config and updates matching device-status defaults.
- `get_calibration_config()`: returns a safe copy of the calibration config.
- `set_calibration_config(...)`: stores new calibration config.
- `set_connection_state(...)`: updates connection-related fields.
- `add_firmware_message(...)`: stores recent firmware banner text.
- `append_log(...)`: adds a timestamped message to the rolling log list.
- `reset_frame_tracking()`: clears frame counters and removes the last spectrum after disconnect or reconnect.
- `update_from_frame(...)`: copies frame metadata from the newest incoming frame into `DeviceStatus`.
- `set_last_spectrum(...)`: stores the newest full `SpectrumFrame`.
- `latest_spectrum()`: returns the newest stored spectrum object.
- `set_session_status(...)`: updates the current session status object.
- `snapshot(...)`: builds a combined `AppSnapshot` for UI reads.

Why this file matters:

- it is the shared memory of the app
- it uses a lock so multiple threads do not trample each other
- it lets the UI stay simple because the UI can ask for one snapshot instead of rebuilding state itself

### `backend/core/session_manager.py`

Purpose:
Owns the rolling frame buffer and session exports.

Rationale:
Keeping session history separate from current live state prevents the state object from growing into too many responsibilities.

Definitions:

- `utc_now()`: helper that returns the current UTC timestamp.
- `SessionManager`: stores recent frames, tracks dropped frames, resets sessions, and exports CSV files.

Important `SessionManager` methods:

- `__init__(...)`: creates the frame deque, sets the export directory, and starts a new session.
- `_new_session_id()`: creates a short random session ID.
- `set_max_frames(...)`: changes the rolling buffer size while keeping the newest data.
- `append_frame(...)`: adds one frame and counts it as dropped if the deque was already full.
- `set_spectrum_builder(...)`: stores the helper used for export-time derived columns.
- `reset()`: clears the session and starts a fresh session ID.
- `export_csv()`: writes the current session buffer to disk.
- `frames()`: returns a copy of the buffered frame list.
- `status()`: returns a `SessionStatus` summary.

### `backend/core/runtime.py`

Purpose:
Creates and wires together the application's main objects.

Rationale:
This keeps startup logic in one place so the entry point stays small.

Definitions:

- `RuntimePaths`: immutable bundle of important filesystem paths.
- `AppRuntime`: immutable bundle of the service objects the app needs.
- `resolve_runtime_paths(...)`: decides where configs, logs, and project files live, including packaged-app cases.
- `configure_logging(...)`: sets up file and console logging.
- `build_runtime(...)`: loads configs, creates stores and services, wires dependencies together, and returns `AppRuntime`.

Why this file matters:

- it is the composition root of the app
- if you want to know how everything is connected, this is the place to read

### `backend/core/command_service.py`

Purpose:
Acts as the central control layer between transport, parsing, state updates, session buffering, and UI-triggered commands.

Rationale:
Without this service, command logic would be scattered between the UI, transport, and state layers.

Definitions:

- `CommandService`: the main coordinator for connection management, incoming bytes, config application, and user commands.

Important `CommandService` methods:

- `__init__(...)`: stores dependencies, creates a `DeviceStreamReader`, starts the packet-processing thread, and registers transport callbacks.
- `list_serial_ports()`: asks the transport for visible COM ports.
- `connect(...)`: resets packet state, opens the port, updates config and device status, and logs the result.
- `disconnect()`: closes the transport, clears pending input, resets frame tracking, and logs the result.
- `send_raw_command(...)`: sends a text command to the device over USB CDC.
- `apply_user_config(...)`: applies user config to state and updates dependent services.
- `apply_calibration_config(...)`: applies calibration config to the calibration manager and state.
- `refresh_session_status()`: refreshes the session summary stored in `StateManager`.
- `_handle_transport_state(...)`: receives state changes from the transport layer and mirrors them into `StateManager`.
- `_handle_bytes(...)`: receives raw incoming bytes and queues them for background processing.
- `_processing_loop()`: runs in a background thread and continuously turns queued bytes into packets.
- `_process_packet(...)`: handles each parsed packet and decides how it changes app state.
- `_clear_pending_bytes()`: empties the byte queue during reconnect or disconnect.

Why this file matters:

- it is the traffic controller of the app
- it keeps the serial reader thread light by moving packet work to a separate queue and processor thread
- it is where preview-mode detection and missed-frame detection live

## Device Files

The device layer is responsible for talking to external hardware and for rebuilding structured packets from raw bytes.

### `backend/device/base_transport.py`

Purpose:
Defines the abstract interface that all transport types must follow.

Rationale:
Using a base transport means the rest of the app can talk to "a transport" without caring whether it is serial, WiFi, or something else later.

Definitions:

- `BytesCallback`: callback type for raw byte delivery.
- `StateCallback`: callback type for connection state delivery.
- `BaseTransport`: abstract base class for all transport implementations.

Important `BaseTransport` methods:

- `__init__()`: initializes empty callback slots.
- `set_callbacks(...)`: registers functions to receive bytes and connection-state changes.
- `_emit_bytes(...)`: helper that calls the registered byte callback.
- `_emit_state(...)`: helper that calls the registered state callback.
- `connect(...)`: abstract method subclasses must implement.
- `disconnect()`: abstract method subclasses must implement.
- `write(...)`: abstract method subclasses must implement.
- `is_connected()`: abstract method subclasses must implement.
- `list_ports()`: abstract method subclasses must implement.

### `backend/device/packet_reader.py`

Purpose:
Turns an arbitrary stream of incoming bytes into complete packet objects.

Rationale:
Serial data does not arrive in nice, neat packet-sized chunks.
This file holds a buffer and rebuilds complete packets out of messy partial arrivals.

Definitions:

- `DeviceStreamReader`: buffered parser for mixed text and binary device data.
- `FRAME_HEADER_LIMIT`: safety limit used when trimming invalid garbage from the buffer.

Important `DeviceStreamReader` methods:

- `__init__()`: creates the internal byte buffer.
- `feed(...)`: appends new bytes, searches for binary frames or newline-terminated text, parses anything complete, and returns packet objects.
- `reset()`: clears the internal buffer.

### `backend/device/protocol.py`

Purpose:
Defines the wire-level protocol rules for text and binary frame packets.

Rationale:
Keeping packet details in one file prevents protocol constants from being scattered throughout the app.

Definitions:

- `PACKET_MAGIC`: the binary frame signature used to recognize frame packets.
- `PACKET_VERSION`: current binary protocol version.
- `PACKET_TYPE_FRAME`: the type code for a frame packet.
- `FRAME_HEADER_STRUCT`: the binary struct layout used for parsing frame headers.
- `parse_device_line(...)`: interprets one decoded text line as a firmware banner or generic text packet.
- `encode_raw_command(...)`: turns a user command string into an ASCII line ending with `\n`.
- `try_parse_binary_frame(...)`: tries to parse one binary frame packet from a byte buffer and returns both the packet and how many bytes were consumed.

### `backend/device/serial_transport.py`

Purpose:
Implements the real COM-port transport with `pyserial`.

Rationale:
This file isolates serial-port details so the rest of the app never has to call `serial.Serial(...)` directly.

Definitions:

- `SerialTransport`: concrete serial implementation of `BaseTransport`.

Important `SerialTransport` methods:

- `__init__()`: creates storage for the serial handle, reader thread, stop event, and write lock.
- `connect(...)`: opens the port and starts the serial reader thread.
- `disconnect()`: stops the reader thread, closes the port, and emits a disconnected state.
- `write(...)`: writes bytes to the port in a thread-safe way.
- `is_connected()`: reports whether the serial port is open.
- `list_ports()`: returns a simple list of visible serial ports.
- `_reader_loop()`: background loop that continuously reads incoming bytes and emits them to the registered callback.

### `backend/device/wifi_transport.py`

Purpose:
Reserves a place for a future WiFi transport.

Rationale:
The project structure already allows for more than one transport type, even though WiFi is not implemented yet.

Definitions:

- `WifiTransport`: placeholder transport that raises `NotImplementedError` for unsupported operations.

## Processing Files

The processing layer performs the math used to turn raw ADC counts into more meaningful values.

### `backend/processing/adc_converter.py`

Purpose:
Converts ADC counts into volts.

Rationale:
This keeps a very common math operation in one reusable helper instead of repeating the same formula in many places.

Definitions:

- `counts_to_volts(...)`: scales raw counts into volt values based on ADC resolution and reference voltage.

### `backend/processing/calibration_manager.py`

Purpose:
Owns the calibration settings and applies the full correction pipeline.

Rationale:
Putting calibration policy in one object makes it easier to update behavior when the user changes calibration settings.

Definitions:

- `CalibrationManager`: stores calibration config and applies dark subtraction, ADC conversion, intensity correction, and wavelength mapping.

Important `CalibrationManager` methods:

- `__init__(...)`: stores the calibration config.
- `config`: property that returns the current calibration config.
- `update_config(...)`: replaces the stored calibration config.
- `apply(...)`: runs the complete calibration pipeline on one set of sample indices and ADC counts.

### `backend/processing/dark_subtraction.py`

Purpose:
Subtracts dark offsets from signal values.

Rationale:
This logic is isolated so it can be reused from both live and export paths.

Definitions:

- `apply_dark_subtraction(...)`: subtracts either a direct same-length dark array or an index-mapped dark array.

### `backend/processing/intensity_correction.py`

Purpose:
Applies multiplicative correction factors to signal values.

Rationale:
This is the inverse of the dark-subtraction helper in spirit: one helper for one job.

Definitions:

- `apply_intensity_correction(...)`: multiplies values by either a direct same-length array or an index-mapped correction array.

### `backend/processing/wavelength_map.py`

Purpose:
Turns pixel indices into wavelengths.

Rationale:
This keeps the wavelength polynomial separate from the rest of the processing pipeline.

Definitions:

- `indices_to_wavelengths(...)`: evaluates a polynomial using sample index as the input variable.

### `backend/processing/spectrum_builder.py`

Purpose:
Builds `SpectrumFrame` objects and creates export-time derived columns.

Rationale:
This file bridges the gap between raw incoming frame packets and the app's higher-level spectrum representation.

Definitions:

- `SpectrumBuilder`: helper for creating `SpectrumFrame` objects and export columns.

Important `SpectrumBuilder` methods:

- `__init__(...)`: stores dependencies and prepares a wavelength cache.
- `update_device_config(...)`: updates the ADC/device settings used during export calculations.
- `build_from_frame(...)`: creates a `SpectrumFrame` from one parsed `FramePacket`.
- `build_export_columns(...)`: computes wavelengths, volts, and processed intensity for export when those fields are not already stored.

Why this file matters:

- it keeps the live path lighter by storing raw ADC data quickly
- it keeps export-time scientific columns available without forcing that cost on every live update

## Storage Files

The storage layer is responsible for reading and writing files.

### `backend/storage/config_store.py`

Purpose:
Loads and saves user config files.

Rationale:
This keeps JSON file handling out of the UI and out of the service layer.

Definitions:

- `ConfigStore`: reads and writes `UserConfig` JSON files.

Important `ConfigStore` methods:

- `__init__(...)`: stores the default and active config paths.
- `load()`: reads the active config if it exists, otherwise the default config.
- `save(...)`: writes a config object to the active config path.

### `backend/storage/calibration_store.py`

Purpose:
Loads and saves calibration config files.

Rationale:
This mirrors `ConfigStore` but for calibration settings.

Definitions:

- `CalibrationStore`: reads and writes `CalibrationConfig` JSON files.

Important `CalibrationStore` methods:

- `__init__(...)`: stores the default and active calibration paths.
- `load()`: reads the active calibration file if present, otherwise the default one.
- `save(...)`: writes a calibration object to the active calibration path.

### `backend/storage/export_csv.py`

Purpose:
Exports stored frames to a CSV file.

Rationale:
CSV output is a separate concern from live display, so it belongs in the storage layer.

Definitions:

- `export_spectra_csv(...)`: writes one row per sample, optionally asking `SpectrumBuilder` to compute wavelength, volt, and intensity columns during export.

Why this file matters:

- it turns frame-oriented memory into sample-oriented tabular data
- it is the last step in the capture pipeline when the user wants a file

## Frontend File

### `frontend/kivy_app.py`

Purpose:
Defines the entire desktop user interface.

Rationale:
The UI is kept in one file because it is tightly connected to one window and one graphing experience.

Definitions:

- `Card`: a reusable rounded panel widget for grouping related controls.
- `SpectrumPlot`: a custom widget that draws the spectrum graph.
- `DesktopSpectrometerApp`: the main Kivy application class.
- `run_desktop_app(...)`: starts the desktop app with a prepared runtime object.

#### `Card`

Purpose:
A styled `BoxLayout` with a rounded background.

Rationale:
This avoids repeating the same panel styling everywhere in `build()`.

Methods:

- `__init__(...)`: sets the layout style and creates the rounded background.
- `_update_background(...)`: resizes the background shape when the widget moves or changes size.

#### `SpectrumPlot`

Purpose:
Draws the live spectrum line manually using Kivy graphics primitives.

Rationale:
Using a custom widget makes it easier to control axis scaling, colors, and chunked drawing for large line sets.

Methods:

- `__init__(...)`: initializes the stored series and ADC range and binds redraws to resize events.
- `set_series(...)`: stores the current x and y data and triggers a redraw.
- `set_adc_range(...)`: stores the y-axis range and triggers a redraw.
- `_redraw(...)`: clears the canvas and redraws the background, guide lines, and spectrum line.
- `_iter_line_chunks(...)`: splits a long line into smaller chunks so Kivy can draw it more safely.

#### `DesktopSpectrometerApp`

Purpose:
Owns the whole window, all user interactions, and the timed UI refresh behavior.

Rationale:
Kivy apps are usually organized around one main application class that builds widgets and reacts to events.

Methods:

- `__init__(...)`: stores the shared runtime and creates placeholders for the widgets that need later updates.
- `build()`: creates the complete window layout and returns the root widget.
- `on_start()`: runs after the window is created, schedules refresh timers, and optionally reconnects to the device.
- `on_stop()`: disconnects the transport when the app closes.
- `refresh_ports(...)`: updates the COM-port list in the UI.
- `connect_device(...)`: reads UI input and asks `CommandService` to connect.
- `disconnect_device(...)`: asks `CommandService` to disconnect.
- `save_user_config(...)`: reads current UI values, saves them to disk, and applies them to the running app.
- `save_calibration(...)`: reads calibration inputs, saves them, and applies them to the running app.
- `export_session(...)`: exports the buffered frames to CSV.
- `reset_session(...)`: clears the session buffer.
- `send_raw_command(...)`: sends a raw command to the STM32.
- `refresh_status(...)`: updates slower-changing text fields such as connection state and logs.
- `refresh_plot(...)`: updates the graph, stream message, axis labels, layout text, and measured refresh speed.
- `refresh_view(...)`: runs both refresh helpers together.
- `_record_plot_update()`: records the time of a plot update for refresh-rate measurement.
- `_current_plot_refresh_hz()`: estimates the current graph refresh rate from recent timestamps.
- `set_notice(...)`: changes the message shown in the top header area.
- `_section_title(...)`: helper for styled section headers.
- `_info_label(...)`: helper for standard info labels.
- `_small_label(...)`: helper for compact explanatory text.
- `_axis_label(...)`: helper for axis labels.
- `_button(...)`: helper for consistently styled buttons.
- `_checkbox_row(...)`: helper that lays out a checkbox next to its text label.

#### `run_desktop_app(runtime)`

Purpose:
Creates `DesktopSpectrometerApp` and starts Kivy's event loop.

Rationale:
This gives the entry point a simple one-line way to launch the UI.

## Typical End-To-End Example

Here is what happens during a normal frame capture:

1. The user opens the app with `run_app.bat`.
2. `desktop_app.py` builds the runtime and starts Kivy.
3. The user clicks `Connect`.
4. `CommandService.connect(...)` opens the COM port through `SerialTransport`.
5. `SerialTransport` starts reading bytes from the STM32.
6. `CommandService` queues the raw bytes.
7. `DeviceStreamReader` rebuilds packets.
8. `protocol.py` recognizes a binary `CCD1` frame.
9. `CommandService._process_packet(...)` updates `StateManager` and `SessionManager`.
10. `DesktopSpectrometerApp.refresh_plot(...)` reads the latest frame and redraws the graph.
11. If the user clicks `Export Session CSV`, `SessionManager.export_csv()` and `export_spectra_csv(...)` write the buffered data to disk.

## Best Files To Read First

If you want to understand the code in the most natural order, start here:

1. `desktop_app.py`
2. `backend/core/runtime.py`
3. `backend/models/config.py`
4. `backend/models/frames.py`
5. `backend/core/command_service.py`
6. `backend/device/serial_transport.py`
7. `backend/device/packet_reader.py`
8. `backend/processing/spectrum_builder.py`
9. `frontend/kivy_app.py`

## Final Mental Model

The simplest way to think about this project is:

- `device` gets the bytes
- `protocol` explains the bytes
- `core` decides what to do with them
- `state` remembers the latest truth
- `session` remembers recent history
- `processing` adds meaning to raw numbers
- `storage` saves things to disk
- `frontend` shows the result to the user

That is the full system in one sentence.
