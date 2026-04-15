# PythonGUI

Python/NiceGUI control app for the VIS-NIR spectrometer.

The current STM32 firmware sends USB CDC text lines like:

```text
USB CDC online
TIM2_TRGO (500kHz) -> ADC1 -> DMA, TIM4 ICG (8ms/7.388ms on)
frame=42 samples=123,456,789,321 half=42 full=42
```

This app is scaffolded around that real transport today, while leaving clear extension points for:

- full binary spectrum packets
- MCU command handling
- wavelength and intensity calibration
- CSV export and session history

Run with:

```bash
uvicorn app:app --reload
```
