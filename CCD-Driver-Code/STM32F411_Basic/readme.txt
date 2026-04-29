STM32F411 CCD Driver Notes
==========================

This document describes the current STM32F411_Basic firmware used by the
VIS-NIR spectrometer project.

Last aligned with the source tree on 2026-04-29.

Current Role
------------

The firmware clocks the CCD, samples the analog output with ADC1 + DMA, and
streams each captured line to the desktop app over USB CDC as a binary `CCD1`
frame packet.

The matching desktop parser is in:

  PythonGUI/backend/device/protocol.py

Current Frame Layout
--------------------

- Total samples per frame: 3694
- Leading dummy samples: 32
- Effective light-sensitive samples: 3648
- Trailing dummy samples: 14
- ADC sample format: unsigned 16-bit little-endian values carrying 12-bit ADC
  results
- Effective-pixel range reported in the packet header:
  - `effective_start = 32`
  - `effective_count = 3648`

USB CDC Stream
--------------

On startup the firmware sends short text banner lines, then streams binary
frames. The current banner lines include:

- `USB CDC online`
- `ICG-synchronous binary frame stream enabled`
- `TIM4 update=ICG rising edge start, TIM4 compare=ICG falling edge stop`

Each binary frame contains a packed header followed by the raw ADC payload.

Header fields:

- `magic`: `CCD1` on the wire
- `version`: `1`
- `packet_type`: `1` for a frame packet
- `reserved`: currently `0`
- `frame_id`: monotonically increasing ICG-cycle frame number
- `sample_count`: `3694`
- `effective_start`: `32`
- `effective_count`: `3648`
- `flags`: bit field described below
- `payload_bytes`: `sample_count * 2`

The C header is `CcdUsbFrameHeader` in `Core/Src/main.c`.
The Python parser uses the little-endian layout `<4sBBHIHHHHI`.

Frame Flags
-----------

The current flags are:

- bit 0: `CCD_FRAME_FLAG_ICG_SYNC`
- bit 1: `CCD_FRAME_FLAG_TIMING_FAULT`
- bit 2: `CCD_FRAME_FLAG_USB_TIMEOUT`

Normal frames should have the ICG-sync bit set.
These flag values are included in the frame header for packets that are
successfully sent. A USB timeout may prevent that specific frame from reaching
the desktop app, but the firmware still records the timeout counter internally.

Timer Plan
----------

The firmware uses the following timer roles:

- TIM1 CH1: PHI/M master CCD clock
- TIM2 TRGO / CH1: ADC DMA trigger clock
- TIM3 CH1: SH timing PWM
- TIM4 CH1 + interrupts: ICG frame timing and capture gate
- TIM5: initialized as another 500 kHz base timer with TRGO update, currently
  reserved/not part of the active capture path

PHI/M Clock
-----------

- Timer: TIM1 CH1
- Pin: PA8
- Frequency: 2 MHz
- Prescaler: 0
- Period: 47
- Pulse: 24
- Duty cycle: approximately 50%
- Output polarity: high

This is the master CCD clock and runs continuously.

ADC Trigger
-----------

- Timer: TIM2
- Pin: PA5 for TIM2 CH1 output
- TRGO: update event
- Frequency: 500 kHz
- Prescaler: 0
- Period: 191
- Pulse: 96

TIM2 is started for each ICG-synchronized capture and disabled again when the
DMA transfer completes or when the TIM4 compare callback marks the ICG end.

ADC and DMA
-----------

- ADC: ADC1
- Input pin: PA0 / ADC1_IN0
- Resolution: 12-bit
- External trigger: TIM2 TRGO rising edge
- DMA: DMA2 Stream0
- Samples per DMA transfer: 3694

When ADC DMA completes, the active frame slot is marked ready for USB
transmission and TIM2 is disabled.

SH Timing
---------

- Timer: TIM3 CH1
- Pin: PA6
- Prescaler: 0
- Period: 959
- Pulse: 576
- Output polarity: high

TIM3 PWM is started during firmware initialization. The current code keeps SH
as a fixed PWM waveform rather than a runtime-adjustable integration control.

ICG Timing
----------

- Timer: TIM4 CH1
- Pin: PB6
- Frame period: 8.000 ms
- Prescaler: 95
- Period: 7999
- Pulse: 7388
- Output polarity: low
- TIM4 IRQ priority: 0

The firmware uses TIM4 callbacks as the capture boundaries:

- `HAL_TIM_PeriodElapsedCallback(...)` on TIM4 starts a new capture from the
  ICG edge.
- `HAL_TIM_PWM_PulseFinishedCallback(...)` on TIM4 disables TIM2 at the ICG
  end edge.

The startup banner describes this as:

- TIM4 update = ICG rising edge start
- TIM4 compare = ICG falling edge stop

Frame Buffering
---------------

The firmware keeps three frame slots:

- one slot can be actively filled by ADC DMA
- one slot can be ready for USB transmission
- one slot can provide breathing room if USB transmission overlaps capture

If no slot is available, the firmware increments the dropped-frame counter.
If a new capture starts while another is still active, the active capture is
aborted with the timing-fault flag.

USB Transmission
----------------

The main loop searches for the next ready frame slot and sends:

1. the packed binary header
2. the raw ADC sample payload

Transmission is chunked into 512-byte USB CDC writes through
`CDC_Transmit_All(...)`. Each chunk uses `CDC_Transmit_Blocking(...)` with a
timeout. If a send fails, the firmware records a USB timeout and marks the slot
with `CCD_FRAME_FLAG_USB_TIMEOUT`.

Pin Configuration Summary
-------------------------

Processor: STM32F411CEU6

ADC input:

- PA0: ADC1_CH0, CCD analog output

Timer/PWM outputs:

- PA8: TIM1_CH1, PHI/M 2 MHz master clock
- PA5: TIM2_CH1, ADC trigger monitor output / 500 kHz timing
- PA6: TIM3_CH1, SH timing PWM
- PB6: TIM4_CH1, ICG frame timing PWM

Additional GPIO defines currently generated in `Core/Inc/main.h`:

- PB12: `SH_Pin`
- PB13: `ICG_Pin`

Those GPIO defines are initialized as push-pull outputs, but the active timer
waveforms described above are on PA6 and PB6.

Desktop Compatibility Notes
---------------------------

The desktop app expects `CCD1` binary packets with the same sample count and
effective-pixel geometry listed above. If the firmware changes any of these
values, update the desktop config defaults in:

  PythonGUI/configs/default_user.json

and confirm that the parser constants in:

  PythonGUI/backend/device/protocol.py

still match the firmware packet format.
