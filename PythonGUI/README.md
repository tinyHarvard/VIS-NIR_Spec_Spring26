# PythonGUI

`PythonGUI` is the desktop control program for the VIS-NIR spectrometer.
It is written in Python and runs as a native Kivy window instead of a browser app.

This folder contains the complete desktop-side pipeline:

- opening the USB serial connection to the STM32 board
- rebuilding incoming packets from raw bytes
- keeping track of the latest frame and connection state
- buffering frames in a session
- exporting captured frames to CSV
- drawing the live graph in the desktop window

The current STM32 firmware is expected to stream:

- a full `3694`-sample binary frame
- `32` leading dummy samples
- `3648` effective light-sensitive samples
- `14` trailing dummy samples
- frame timing based on the CCD ICG edges

## Start Here

Run the desktop app with:

```bat
run_app.bat
```

Install dependencies with:

```bat
install_dependencies.bat
```

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
- A `config` file is just saved settings, usually JSON in this project.

Python reads very literally from top to bottom.
Imports pull in code from other files.
Functions and classes are defined first, then the program starts running from an entry point such as `main()`.

## Project Layout

Here is the big picture of the folders:

- `desktop_app.py`: the real program entry point for the desktop app
- `frontend/`: the Kivy user interface
- `backend/models/`: shared data structures
- `backend/core/`: the main application services and state holders
- `backend/device/`: serial transport and packet parsing
- `backend/processing/`: math and calibration helpers
- `backend/storage/`: config loading and CSV export
- `configs/`: default settings files
- `logs/`: runtime logs written while the app is running

If you want the detailed file-by-file explanation, read:

```text
CODE_TOUR.md
```

## How The Program Starts

When you run `run_app.bat`, the startup path is:

1. `run_app.bat` checks that the virtual environment exists and launches `desktop_app.py`.
2. `desktop_app.py` sets a few Kivy environment settings before Kivy is imported.
3. `desktop_app.py` builds the shared runtime by calling `build_runtime(...)` in `backend/core/runtime.py`.
4. `build_runtime(...)` loads the configs, creates the service objects, and wires them together.
5. `desktop_app.py` starts the Kivy app by calling `run_desktop_app(runtime)`.
6. `frontend/kivy_app.py` builds the window and starts timed refresh tasks for the plot and status text.

## Live Data Flow

Once the user presses `Connect`, the live data moves through the program like this:

1. `SerialTransport.connect(...)` opens the COM port.
2. `SerialTransport` starts a serial reader thread.
3. That reader thread continuously reads raw bytes from the STM32 board.
4. The bytes are handed to `CommandService._handle_bytes(...)`.
5. `CommandService` places those bytes into a queue instead of doing heavy work on the reader thread.
6. A separate processor thread inside `CommandService` takes bytes out of the queue.
7. `DeviceStreamReader.feed(...)` rebuilds complete text lines and binary frame packets from the incoming byte stream.
8. `protocol.py` interprets what those bytes mean.
9. `CommandService._process_packet(...)` updates application state and builds a `SpectrumFrame`.
10. `StateManager` stores the latest device status and the most recent frame.
11. `SessionManager` keeps a rolling buffer of frames for export.
12. The Kivy UI polls the latest state on a timer and redraws the graph.

## What Runs Separately

One of the most important ideas in this app is that not everything runs in one place.
Several parts run independently so the graph stays responsive while data keeps arriving.

- The main Kivy UI thread owns the window, buttons, labels, and graph drawing.
- The serial reader thread inside `SerialTransport` only worries about reading bytes from the COM port.
- The packet processor thread inside `CommandService` rebuilds frames and updates the state.
- Kivy timer callbacks call `refresh_plot(...)` and `refresh_status(...)` on a schedule.
- File save operations happen only when needed, such as exporting a CSV or saving config files.

This split exists for a reason:

- if the serial reader did everything itself, incoming USB data could back up while the app was busy
- if the UI did all packet rebuilding, the window could freeze or feel laggy
- if the app recalculated every derived value on every redraw, the graph would waste time doing work it does not need

## Why The Code Is Split Into Layers

The project is organized into layers so each part has a clear responsibility:

- `models` define the shapes of the data
- `device` talks to outside hardware
- `processing` performs math on raw data
- `core` coordinates the app
- `storage` saves and loads files
- `frontend` shows information to the user

This makes the code easier to debug because each layer has a narrower job.
For example, if the serial stream is wrong, you look in `device`.
If the graph is wrong but the captured data is correct, you look in `frontend`.
If a saved CSV is wrong, you look in `storage` and `processing`.

## Important Runtime Objects

These are the most important objects in the app:

- `StateManager`: the current truth of the app right now
- `SessionManager`: the rolling memory of captured frames
- `CommandService`: the traffic controller between transport, parsing, state, and sessions
- `SerialTransport`: the actual COM-port implementation
- `SpectrumBuilder`: turns an incoming frame packet into the app's internal spectrum object
- `CalibrationManager`: owns the calibration settings and math choices
- `DesktopSpectrometerApp`: the Kivy window and all UI behavior

## Why The Plot Uses Raw ADC Counts Live

The live graph is intentionally based on raw ADC counts.
That choice keeps the graph fast and predictable.

The app still supports calibration data, but the heavier wavelength and intensity calculations are mainly used when exporting data to CSV.
That design reduces work on the hot path that runs frame after frame at high speed.

## Preview Mode Versus Full Frame Mode

The app can detect two kinds of incoming device behavior:

- a true full-frame stream, where the STM32 sends the entire CCD line
- a legacy preview stream, where the STM32 only sends a tiny sample preview

If only the old preview data arrives, the app tells you directly instead of pretending it has a full 3694-pixel spectrum.

## Configuration Files

The most important JSON files are:

- `configs/default_user.json`: default connection, device, and UI settings
- `configs/default_calibration.json`: default calibration settings
- `configs/user.json`: active user settings if present
- `configs/calibration.json`: active calibration settings if present

The code loads the active file first when it exists.
If it does not exist yet, it falls back to the default file.

## Logs

The app writes logs to:

```text
logs/vis_nir_spec.log
```

This file is useful when:

- the app fails during startup
- the serial connection fails
- frames are missed
- the firmware sends unexpected data

## Recommended Reading Order

If you want to understand the project from top to bottom, this is a good reading order:

1. `desktop_app.py`
2. `backend/core/runtime.py`
3. `backend/models/`
4. `backend/core/command_service.py`
5. `backend/device/`
6. `backend/processing/`
7. `backend/storage/`
8. `frontend/kivy_app.py`
9. `CODE_TOUR.md`

## Detailed Documentation

For the file-by-file walkthrough that explains every class, function, and helper, read:

```text
CODE_TOUR.md
```
