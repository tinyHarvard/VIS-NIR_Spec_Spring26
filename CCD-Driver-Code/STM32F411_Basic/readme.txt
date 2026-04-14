CCD Timer Plan
===============

This document describes how the STM32F411 timers will be used to drive the CCD control signals.

PHI/M Clock
-----------

- PHI/M will remain fixed at 2 MHz.
- This is the master CCD clock and will run continuously.

ICG Timing
----------

- ICG will define the total frame period.
- The full ICG frame will be extended to 8.000 ms.
- Required CCD readout time is 7.388 ms.
- This leaves 0.612 ms of spare timing margin inside each frame.

SH Timing
---------

- SH will be synchronized to the ICG frame so that the full SH pulse occurs during the ICG low time.
- The SH sequence must start low, transition high, and return low before the next ICG active edge.
- The SH high pulse width will be fixed at 4 us.
- The SH low time will be adjustable to control integration time.
- The adjustable SH timing should align with fractional divisions of the ICG period.

Examples of SH timing points include:

- 8.0 ms
- 4.0 ms
- other fractional divisions of the ICG frame
- down to 12.5 us resolution

Integration Time Strategy
-------------------------

- SH acts as the adjustable integration timing signal.
- By keeping the SH high pulse fixed at 4 us and changing the off time between pulses, the integration time can be tuned.
- The timer arrangement should place the complete SH off-on-off pulse inside the ICG off interval, using fractional timing steps as needed.

Implementation Notes
--------------------

- Use one timer as the fixed 2 MHz source for PHI/M.
- Use another timer to generate the 8.000 ms ICG frame period.
- Use a synchronized timer channel for SH so the full 4 us pulse is locked inside the ICG low interval.
- SH delay/off time should be programmable so integration time can be adjusted without changing the PHI/M frequency.

Pin Configuration Summary
--------------------------

Processor: STM32F411CEU6

ADC Inputs:
-----------
- PA0   : ADC1_CH0 (CCD Analog Output)

Timer Outputs:
--------------
- PA8   : TIM1_CH1 (PHI/M Clock - 2 MHz master clock)
- PA5   : TIM2_CH1 (ADC DMA Trigger - 500kHz)
- PA6   : TIM3_CH1 (SH Timing - variable integration time)
- PB6   : TIM4_CH1 (ICG Frame Period - 8.000 ms)

Timer Configuration Details:
----------------------------

TIM1 (PHI/M Clock):
  - Frequency: 2 MHz
  - Prescaler: 0
  - Period: 47
  - Duty Cycle: 50% (Pulse: 24)
  - Output: PA8

TIM2 (ADC DMA Trigger):
  - Frequency: 500kHz
  - Prescaler: 0
  - Period: 191
  - Duty Cycle: 50% (Pulse: 96)
  - TRGO: UPDATE triggers ADC
  - Output: PA5

TIM3 (SH Timing):
  - Synchronized with ICG for integration time control
  - Output: PA6
  - Adjustable timing aligned to fractional ICG divisions

TIM4 (ICG Frame):
  - Frame Period: 8.000 ms
  - Prescaler: 95
  - Period: 7999
  - Pulse: 7388
  - Output: PB6
  - MCU pin waveform: 7.388 ms low, 0.612 ms high
  - CCD waveform after external inverter: 7.388 ms high, 0.612 ms low
