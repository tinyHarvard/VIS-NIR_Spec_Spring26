# PythonGUI

Python desktop control app for the VIS-NIR spectrometer.

The current STM32 firmware is set up to stream:

- full 3694-sample binary USB CDC frames
- frame start on the CCD ICG low-to-high edge
- frame end on the CCD ICG high-to-low edge
- 32 leading dummy outputs, 3648 effective outputs, and 14 trailing dummy outputs

Run with:

```bash
run_app.bat
```

The app runs as a native Kivy desktop window.
The old NiceGUI/browser frontend has been removed, so the desktop path is now the only UI.
If the app detects the old four-sample preview stream from the STM32, it will say so
explicitly in the UI and logs instead of pretending that those packets are full CCD frames.

Build a standalone executable with:

```bash
build_standalone.bat
```
