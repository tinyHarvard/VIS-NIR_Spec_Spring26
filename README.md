# VIS-NIR_Spec_Spring26

Working repository for the Spring 2026 VIS-NIR spectrometer senior design project.

The repo has two active software areas:

- `PythonGUI/`: the Python/Kivy desktop app for connecting to the spectrometer, plotting live CCD data, calibrating the signal, and exporting sessions to CSV.
- `CCD-Driver-Code/STM32F411_Basic/`: the STM32F411 CubeIDE firmware project that clocks the CCD, captures ADC samples with DMA, and streams binary frames over USB CDC.

Other top-level files include the STM32Cube project metadata, a PuTTY helper batch file, and project measurement/reference material.

## Quick Start

For the desktop app:

```bat
cd PythonGUI
install_dependencies.bat
run_app.bat
```

For the current Python app guide, read:

```text
PythonGUI/README.md
PythonGUI/CODE_TOUR.md
```

For the current firmware timing and stream notes, read:

```text
CCD-Driver-Code/STM32F411_Basic/readme.txt
```

## Current System Shape

The STM32 firmware emits `CCD1` binary frame packets over USB CDC. Each normal frame contains `3694` 12-bit ADC samples: `32` leading dummy samples, `3648` effective pixels, and `14` trailing dummy samples.

The desktop app reads that stream from a COM port, reconstructs mixed text and binary packets, applies the current calibration pipeline for the live display, stores recent frames in a rolling session buffer, and exports CSV rows with raw and derived columns.

The main app now includes:

- line-spectrum and rolling-spectrogram live views
- a full-screen calibration manager
- guided pixel-to-wavelength mapping from selected plot peaks
- bias, dark, flat-field, and QE/response calibration inputs
- display/layout controls for side-panel cards and frame-data rows
- optional performance diagnostics for backend and UI timing
