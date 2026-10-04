# FoxESS EVO — Modbus findings

Community notes on controlling a **FoxESS EVO** inverter over Modbus, based on testing a real inverter.

## Why this exists

The only Modbus document FoxESS has published (*Modbus Protocol V1.05.03.00*, January 2025) **does not
mention the EVO**, and the EVO reports a newer protocol version (V1.05.04.00) than that document describes.
Integrations built from it — and from trial and error — have repeatedly concluded things that turned out to
be wrong ("max SoC is read-only", "the cloud makes the scheduler read-only", "the scheduler can't be written
over Modbus"). Everything here was checked against a real EVO by reading and writing registers and
comparing with the Fox app and Fox Cloud.

## Tested on

| | |
|---|---|
| Model | EVO 10-5-H, 1 battery pack, Modbus TCP (slave 247) |
| Modbus protocol version | V1.05.04.00 |
| Firmware | Master 1.21, Slave 1.01, Manager 1.20, BCU 1.004 |
| Date | October 2026 |

Other EVO models and firmware may differ. Please share results from yours (see
[testing method](testing-method.md)).

**Status key** used throughout: ✅ confirmed on hardware · ⚠️ differs from the FoxESS protocol document ·
❓ not yet tested.

## Pages

- **[Mode Scheduler](mode-scheduler.md)** — the Fox app's per-time-slot schedule (`48000`–`48249`): layout,
  how to write it safely, how a Force Charge slot behaves, and how the app uses the table.
- **[Work mode, SoC limits and Remote Control](work-mode-soc-remote-control.md)** — `49203`, `46609`–`46620`
  (including the undocumented Max SoC From Grid rule), and Remote Control alongside the scheduler.
- **[Identity and version registers](identity-and-versions.md)** — model, serials, firmware, BCU version,
  and why "BMS pack version" sensors show nonsense on the EVO.
- **[Fox Cloud API](fox-cloud-api.md)** — which Open API calls work on the EVO, and why the cloud can't be
  trusted to show the inverter's state.
- **[Testing method](testing-method.md)** — how to probe safely, find unknown registers, decode values, and
  read Modbus exception codes.

## The things most likely to catch you out

1. **Scheduler writes must cover whole 10-register blocks** (including `48000`–`48009`). Partial writes are
   rejected — whether an older "charge period" integration works on your inverter can depend on leftover
   values in the block.
2. **While the Mode Scheduler is on, the work mode (`49203`) and the global SoC limits are ignored** — the
   active slot decides. This is the usual cause of "my work mode won't change".
3. **`49203` is written with the same 1-based codes it reads** (1 Self Use, 2 Feed-in, 3 Back-up). Writing
   0-based values sets the wrong mode.
4. **System Max SoC can't go below Max SoC From Grid** (`46620`, undocumented). Lower `46620` first.
5. **The Fox app and cloud lag behind or miss Modbus changes** — especially the Mode Scheduler switch. Read
   the registers; and saving in the app may write its stale view back.
6. **A Force Charge slot honours its power and cut-off SoC, then holds the battery** until the slot ends.

## Using this with Home Assistant

This repository's foxess_modbus fork implements the findings: `foxess_modbus.get_evo_schedule`,
`set_evo_schedule` and `set_evo_schedule_enabled` read and write the Mode Scheduler as whole blocks with
read-back verification, and a "Mode Scheduler" binary sensor shows whether the schedule is in control.
