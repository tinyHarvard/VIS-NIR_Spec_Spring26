# Timer Configuration Outline — CCD Driver Plan

Target MCU: **STM32F411CEU6** (UFQFPN48)
CubeMX/CubeIDE: **MxCube 6.15.0 / CubeIDE 1.19.0** (matches current `.ioc`)
Goal: Bring `STM32F411_Basic.ioc` in line with the timer plan in [readme.txt](readme.txt) so SH and ICG are hardware-timer driven, ADC is triggered by TIM2, and integration time is adjustable.

---

## 1. State Audit — Source of Truth and What's Stale

Authority order for this project (per project lead):

1. **`readme.txt` — source of truth.** All other artifacts get reconciled to it.
2. **`STM32F411_Basic/`** is the active firmware tree. `main.c` and the `.ioc` here are working files that must be brought into agreement with readme.txt.
3. The root-level `VIS-NIR_SPEC_2026.ioc` is **not** the active project file — ignore it for timer planning.

How the active artifacts compare against readme.txt today:

| Source | TIM1 | TIM2 | TIM3 | TIM4 | TIM5 | SH pin | ICG pin |
|---|---|---|---|---|---|---|---|
| **readme.txt (truth)** | 2 MHz / PA8 | 500 kHz / PA5 (TRGO→ADC) | SH variable / PA6 | 8 ms / **PB6** | — | **PA6** (TIM3) | **PB6** (TIM4) |
| `.ioc` (stale) | 2 MHz / PA8 ✓ | 135 Hz / PA5 (Pulse=96) ✗ | 100 kHz / PA6 (Pulse=384) ✗ | not present ✗ | not present ✓ | PB12 GPIO ✗ | PB13 GPIO ✗ |
| `main.c` (partially matches) | 2 MHz / PA8 ✓ | 500 kHz / PA5 (Pulse=96, TRGO→ADC) ✓ | Period=959, Pulse=576 ≈ | 8 ms / Pulse=7388 / LOW ✓ | Period=191 (unused) ✗ | PB12 init only ✗ | PB13 init only ✗ |

Net: `main.c` is closer to readme.txt than `.ioc` is — somebody hand-edited the firmware ahead of CubeMX. The job is to make CubeMX (`.ioc`) catch up to that work and to readme.txt's pin map, then regenerate cleanly.

### Critical pre-work warning

`main.c` contains hand-written TIM4 / TIM5 / DMA / ADC-trigger setup that is **not in `.ioc`**. The instant you regenerate code from CubeMX, every line outside `/* USER CODE BEGIN */ ... /* USER CODE END */` blocks gets rewritten. The peripheral init functions (`MX_TIM4_Init`, `MX_TIM5_Init`, `MX_DMA_Init`, the ADC trigger settings inside `MX_ADC1_Init`) are **outside** those blocks today, so they will be **deleted** on regeneration.

The plan therefore reconciles `.ioc` to `readme.txt` *and* to the existing hand-written firmware logic at the same time, so regenerating produces init functions that match what `main.c` already expects. The application logic that lives inside `/* USER CODE BEGIN */` blocks (frame capture state machine, USB CDC transmit loop, ISR callbacks) is preserved automatically.

Before clicking "Generate Code", commit the current `main.c` to git so any accidental loss is recoverable.

---

## 2. Target State (from readme.txt)

| Timer | Role | Pin | Frequency / Period | Notes |
|---|---|---|---|---|
| **TIM1_CH1** | φM (master CCD clock) | PA8 | 2 MHz, 50% duty | Free-running |
| **TIM2_CH1** | ADC sample trigger | PA5 | 500 kHz | TRGO=Update, drives ADC1 ext-trig |
| **TIM3_CH1** | SH (transfer / shutter) | PA6 | Variable, fixed 4 µs HIGH pulse | Slaved/synced to TIM4 |
| **TIM4_CH1** | ICG (frame / clear) | **PB6** | 8.000 ms (125 Hz) | Inverted externally → CCD ICG = 7.388 ms HIGH, 0.612 ms LOW |
| ADC1_IN0 | CCD analog OS | PA0 | 500 kHz sample rate | DMA continuous, T2_TRGO trigger |

System clock: 96 MHz (SYSCLK), APB1 timer clock = 96 MHz, APB2 timer clock = 96 MHz. Already correct in `.ioc`.

---

## 3. Per-Timer Math (Verification of readme.txt Numbers)

### TIM1 — φM @ 2 MHz on PA8 (APB2 timer clock = 96 MHz)
```
f = 96 MHz / (PSC+1) / (ARR+1) = 96e6 / 1 / 48 = 2.000 MHz   ✓
Pulse = 24  → 50% duty                                       ✓
```
**No change needed.** Already correct in `.ioc`.

### TIM2 — ADC trigger @ 500 kHz on PA5 (APB1 timer clock = 96 MHz)
```
f = 96 MHz / 1 / (191+1) = 500.0 kHz                         ✓
Pulse = 96 → 50% duty (irrelevant, only TRGO=Update is used)
```
**Change required:** `.ioc` currently has `Period=709247` (a stale 135 Hz frame value). Set Period=191, leave Pulse=96, and add TRGO=Update + master-mode enable.

### TIM4 — ICG @ 125 Hz on PB6 (APB1 timer clock = 96 MHz)
```
f = 96 MHz / (95+1) / (7999+1) = 125 Hz                      ✓
Period = 8.000 ms                                            ✓
PWM1 + Pulse=7388 + OCPolarity=LOW:
   MCU output is LOW for 7388 ticks (7.388 ms),
                HIGH for 612 ticks  (0.612 ms)
After external inverter:
   CCD ICG is HIGH for 7.388 ms (integration/readout window)
   CCD ICG is LOW  for 0.612 ms (clear pulse)                ✓
```
**Change required:** Add TIM4 to `.ioc`, configure CH1 PWM Generation on PB6.

### TIM3 — SH on PA6 (APB1 timer clock = 96 MHz)
With PSC=95 (1 µs tick):
```
For 8.000 ms SH cycle (one SH per ICG frame, normal mode):
   ARR = 7999, Pulse = 4 → 4 µs HIGH, then 7.996 ms LOW

For 4.000 ms SH cycle (two SH per ICG frame, electronic shutter):
   ARR = 3999, Pulse = 4

For 12.5 µs SH cycle (electronic shutter, max rate):
   ARR = 12,    Pulse = 4
```
**Change required:** Update Period and Pulse from current `.ioc` values (959 / 384) to match the chosen integration time. Polarity and master/slave config to be confirmed (see §6 questions).

### Sanity: 500 kHz ADC × 3694 elements = 7.388 ms readout
```
3694 samples / 500 kHz = 7.388 ms                            ✓
```
This matches the readout window inside the 8 ms ICG frame.

---

## 4. Gap Analysis — What Has To Change in CubeMX

### 4.1 Pinmux changes
| Pin | Current `.ioc` | Target | Action in CubeMX |
|---|---|---|---|
| PA0 | ADC1_IN0 | ADC1_IN0 | none |
| PA5 | TIM2_CH1 | TIM2_CH1 | none |
| PA6 | TIM3_CH1 | TIM3_CH1 (SH) | rename label → `SH` |
| PA8 | TIM1_CH1 | TIM1_CH1 | none |
| **PB6** | unused | **TIM4_CH1** (ICG) | enable TIM4 CH1 PWM, label `ICG` |
| **PB12** | GPIO `SH` | unused | clear pin / remove SH label |
| **PB13** | GPIO `ICG` | unused | clear pin / remove ICG label |

### 4.2 Peripheral additions / changes
| Peripheral | Current | Target | Notes |
|---|---|---|---|
| TIM2 | PWM, Period=709247 | PWM, Period=191, Pulse=96, **TRGO=Update**, **MasterSlaveMode=Enable** | drives ADC |
| TIM3 | PWM, Period=959, Pulse=384 | PWM, PSC=95, Period=TBD, Pulse=4, **Slave Mode = Trigger reset from ITRn(TIM4)** | SH timing |
| **TIM4** | not in `.ioc` | PWM CH1, PSC=95, Period=7999, Pulse=7388, **OCPolarity=Low**, **TRGO=Update**, NVIC enabled (TIM4 IRQ) | ICG / frame master |
| ADC1 | Software trigger | **External Trigger = TIM2_TRGO, rising edge**, **DMA continuous = ENABLE**, **EOC selection = single conversion**, sample time = 15 cycles | matches main.c |
| DMA2 | not in `.ioc` | **Add ADC1 DMA stream** (DMA2 Stream0 Ch0), Mode=Circular OR Normal, half-word, peripheral→memory | matches main.c |
| TIM5 | not in `.ioc` | **Decision needed (see §6 Q4)** — currently unused in firmware logic | leave out unless purpose identified |

### 4.3 NVIC / interrupts
- Enable **TIM4 global interrupt** (firmware uses TIM4 update/PWM-pulse-finished callbacks to start/stop frame capture).
- Keep USB OTG_FS interrupt enabled (already configured).

---

## 5. Step-by-Step CubeMX Click Path

> Open `STM32F411_Basic.ioc` in CubeMX, then walk through these in order.

### 5.1 Pinout view — clear stale pins
1. Right-click **PB12** → "Reset_State" (drops the `SH` GPIO label).
2. Right-click **PB13** → "Reset_State" (drops the `ICG` GPIO label).

### 5.2 Pinout view — add ICG output
3. Left-click **PB6** → choose **TIM4_CH1**. The pin turns green.
4. Right-click **PB6** → "Enter User Label" → type `ICG`.

### 5.3 Pinout view — relabel SH
5. Right-click **PA6** → "Enter User Label" → type `SH`.

### 5.4 TIM4 configuration (Pinout & Configuration → Timers → TIM4)
6. **Mode panel:**
   - Clock Source: Internal Clock
   - Channel 1: PWM Generation CH1
7. **Parameter Settings:**
   - Prescaler (PSC): `95`
   - Counter Mode: Up
   - Counter Period (ARR): `7999`
   - Internal Clock Division: No Division
   - Auto-reload preload: Disable
8. **PWM Generation Channel 1:**
   - Mode: PWM mode 1
   - Pulse: `7388`
   - Output compare preload: Enable
   - Fast Mode: Disable
   - CH Polarity: **Low**
9. **Trigger Output (TRGO) parameters:**
   - Master/Slave Mode (MSM bit): Enable
   - Trigger Event Selection: Update Event
10. **NVIC Settings tab:** check **TIM4 global interrupt**.

### 5.5 TIM2 configuration
11. **Parameter Settings:**
    - Prescaler: `0`
    - Counter Period (ARR): `191`
    - Auto-reload preload: Disable
12. **PWM Channel 1:** Pulse = `96`, Polarity = High.
13. **TRGO parameters:**
    - Master/Slave Mode: Enable
    - Trigger Event Selection: Update Event

### 5.6 TIM3 configuration (SH)
14. **Parameter Settings:**
    - Prescaler: `95`
    - Counter Period (ARR): **default to `7999`** (one SH pulse per 8 ms ICG frame)
    - Auto-reload preload: Enable
15. **PWM Channel 1:** Pulse = `4`, Polarity = **TBD (see Q2)**.
16. **Slave Mode (this is the key sync step):**
    - Slave Mode: **Reset Mode**
    - Trigger Source: **ITR3** (= TIM4's TRGO; on F4 the ITRn map for TIM3 puts TIM4→ITR3 — verify in CubeMX dropdown)
    - This forces TIM3's counter to reset every time TIM4 wraps, so the SH pulse stays edge-locked to the start of the ICG frame.

### 5.7 ADC1 configuration
17. **Parameter Settings:**
    - Clock Prescaler: PCLK2 / 4
    - Resolution: 12-bit
    - Continuous Conversion: Disable
    - DMA Continuous Requests: **Enable**
    - End Of Conversion Selection: EOC flag at end of single conversion
    - External Trigger Conversion Source: **Timer 2 Trigger Out event**
    - External Trigger Conversion Edge: Rising edge
18. **Channel:** ADC1_IN0, Sampling Time = 15 cycles, Rank = 1.

### 5.8 DMA configuration (ADC1)
19. **DMA Settings tab in ADC1:** Add → ADC1
    - DMA Request: ADC1
    - Stream: DMA2 Stream0
    - Direction: Peripheral to Memory
    - Mode: Normal (matches `HAL_ADC_Start_DMA(... CCD_LINE_SAMPLE_COUNT)` — single shot per frame)
    - Increment Address: Memory only
    - Data Width: Peripheral=Half Word, Memory=Half Word
20. **NVIC Settings:** confirm DMA2 stream0 global interrupt is enabled.

### 5.9 Project manager
21. **Project Manager → Code Generator:**
    - "Copy only the necessary library files" (default)
    - "Generate peripheral initialization as a pair of '.c/.h' files per peripheral" — **keep current setting** to avoid mass file restructuring.
    - "Keep User Code when re-generating" — **must be checked** (already is).
22. Save (Ctrl+S) → Generate Code.

### 5.10 Post-generate sanity
23. Open `Core/Inc/main.h`. The macros `SH_Pin`, `SH_GPIO_Port`, `ICG_Pin`, `ICG_GPIO_Port` should be **gone** (since we cleared PB12/PB13). If any code in `main.c` still references them, remove those references.
24. In `main.c`, the `MX_TIM4_Init`, `MX_TIM5_Init` (if kept), and `MX_DMA_Init` functions should now be CubeMX-generated and match what was hand-written. Diff against the previous main.c to confirm no logic regressed in `/* USER CODE BEGIN */` blocks.

---

## 6. Clarification Questions (Please Answer Before Generating)

These affect specific CubeMX dropdowns and I do not want to guess:

**Q1. Hardware wiring — is ICG already physically routed to PB6?**
The `.ioc` and `main.h` say PB13 is ICG. The readme.txt says PB6. Has the PCB / breadboard been rewired to PB6, or is PB13 still the physical connection? If the hardware is still on PB13, we either change the hardware or re-target the plan to PB13. Same question for SH: physical wire on PB12 or PA6?

**Q2. Inverter on SH?**
Readme.txt explicitly mentions an external inverter on ICG (MCU LOW = CCD HIGH). It does not say one way or the other for SH. Is there an inverter on SH as well, or is SH driven directly to the CCD? This determines whether TIM3 CH1 polarity should be `High` (no inverter) or `Low` (inverter).

**Q3. Single-pulse vs electronic-shutter SH mode**
Readme.txt simultaneously describes:
- "the full SH pulse occurs during the ICG low time" (= one SH per frame, classic mode), AND
- "down to 12.5 µs resolution" for integration time (= electronic shutter, many SH pulses per frame).
Which is the actual operating mode for first bring-up? Recommend starting with **one SH per 8 ms frame** and adding e-shutter mode later. Confirm.

**Q4. TIM5 — keep or delete?**
TIM5 exists in `main.c` (Period=191, MasterSlaveMode disabled, no channel configured) but is never started or referenced after init. It looks like dead code from a previous iteration. OK to drop it from the regenerated project?

**Q5. DMA mode — Normal or Circular?**
`main.c` uses `HAL_ADC_Start_DMA(..., CCD_LINE_SAMPLE_COUNT)` and stops/restarts the ADC each frame from the TIM4 update IRQ. That pattern fits **Normal** DMA. Confirm before I lock that into the CubeMX plan.

---

## 7. Verification Plan (Bench Bring-Up Checklist)

Once code is generated and flashed, verify on a scope before connecting the CCD:

1. **PA8 (φM):** continuous 2.000 MHz, 50% duty. ✓
2. **PB6 (ICG, MCU side):** 125 Hz, LOW for 7.388 ms, HIGH for 0.612 ms. After inverter on the CCD side: HIGH 7.388 ms, LOW 0.612 ms.
3. **PA6 (SH):** rising edge falls inside the ICG-LOW (CCD side) window — i.e., during the 0.612 ms HIGH period of the MCU ICG output. SH HIGH width = 4 µs. SH cycle = 8 ms (or whatever ARR was chosen).
4. **t1, t2, t3, t4 timing per TCD1304DG datasheet:** confirm SH/ICG edge separation is within 100–1000 ns (t2) and that φM is HIGH at the moment ICG transitions (t4 ≤ 20 ns).
5. **PA5 (TIM2 / ADC trigger):** 500 kHz square wave whenever ADC capture is armed.
6. **ADC samples in DMA buffer:** 3694 entries per frame, with the first 32 being dummy/light-shielded and the next 3648 being the effective pixels (per datasheet timing chart).
7. **Frame cadence:** TIM4 update IRQ counter (`ccd_icg_start_count`) increments at 125 Hz.

---

## 8. Open Risks / Notes

- **Clock-tree assumption:** APB1 timer clock = 96 MHz (because APB1 prescaler ≠ 1, so STM32 doubles the timer clock). Already correct in `.ioc`. If anyone changes APB1CLKDivider, **all of TIM2/3/4's math breaks**.
- **TIM4 interrupt priority** is set to 0 in current `main.c`. That's the highest level. CubeMX's NVIC tab will let you set it back to 0; otherwise the TIM4 ISR may run later than the application code expects.
- The TCD1304DG **t4 constraint** (ICG edges must occur while φM is HIGH) is satisfied automatically only if TIM1 and TIM4 share a phase relationship. They do not, here. In practice 2 MHz φM has a 250 ns HIGH window every 500 ns, which is wider than typical ICG edge jitter, so this is usually fine — but worth scoping.
- Once the readme.txt plan is implemented and verified, this `timeroutline.md` should be archived and the `readme.txt` updated to reflect the actual final pin map.