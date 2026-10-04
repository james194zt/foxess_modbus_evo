# FoxESS EVO — Mode Scheduler over Modbus

This page documents how the FoxESS EVO stores the app's **Mode Scheduler** (the per-time-slot work-mode
schedule, also used by Fox "Stormsafe") in its Modbus holding registers, and how to write it safely.

Everything below was confirmed on real hardware by setting known schedules in the Fox app and reading
the registers back, cross-checked against the Fox Cloud Open API (`/op/v3/device/scheduler/get`). Where
something is inferred rather than confirmed, it is marked **unverified**.

- **Inverter:** EVO 10-5-H, Modbus TCP, slave 247
- **Date:** 2026-10-04
- **Modbus protocol version** (registers 39000–39001): V1.05.04.00
- **Firmware:** not yet recorded

## TL;DR

- `48000` is the scheduler master switch. `1` = the app's "Mode Scheduler" is active.
- The schedule is a table of **time groups**, 10 registers each, starting at `48010`.
- **Always write whole 10-register blocks in one write**, including the `48000`–`48009` block that holds
  the switch. The inverter rejects writes that cover only part of a block (even a single-register write to
  `48000`). This is why earlier attempts (writing 4 registers per period) failed with `IllegalAddress` /
  "Unknown error" on some inverters and worked on others.
- Full-group writes are accepted **while a schedule set from the Fox app / cloud is active**. The
  commonly reported "the cloud makes the scheduler read-only to Modbus" was not reproduced (see
  [Write behaviour](#write-behaviour)).
- While `48000 = 1`, the work-mode register `49203` is overridden by the schedule. Writing `49203` alone
  will appear to "not work".
- System Max SoC (`46610`) is writable, but can't go below Max SoC From Grid (`46620`) — see
  [SoC limits](#soc-limits-scheduler-off).
- The Fox app / cloud doesn't reliably show changes made over Modbus; read the registers instead.

## Register map

### Master switch

| Register | Meaning |
|---|---|
| `48000` | Scheduler enable. `1` = Mode Scheduler on, `0` = off (inverter follows `49203`). |
| `48001`–`48009` | Always `0` in every capture. |

`48000`–`48009` behaves like a group: write all 10 registers together (e.g. `1,0,0,0,0,0,0,0,0,0`).
A single-register write (FC6) to `48000` is rejected with `IllegalAddress`.

### Time groups

Group *N* (1-based) starts at **`48010 + 10 × (N − 1)`**. Fox Cloud reports `maxGroupCount: 96` for this
inverter; the app itself manages groups **1–8** (see [App behaviour](#app-behaviour)).

| Offset | Meaning | Encoding |
|---|---|---|
| +0 | Group enabled | `1` / `0` |
| +1 | Start time | `hour << 8 \| minute` (e.g. `261` = 01:05) |
| +2 | End time | `hour << 8 \| minute` (e.g. `5947` = 23:59) |
| +3 | Work mode | see [Work-mode codes](#work-mode-codes) |
| +4 | Max SoC / Min SoC | `max_soc << 8 \| min_soc` (e.g. `21790` = 85 % / 30 %) |
| +5 | Cut-off SoC (`fdSoc`) | percent. Force charge: stop charging at this SoC. Force discharge: stop discharging at this SoC. |
| +6 | Force charge / discharge power (`fdPwr`) | watts |
| +7 | Unknown | `0` in every capture (**unverified**; possibly the "after cut-off" mode, with Self-Use = 0) |
| +8 | Flags | meaning **unverified** — don't depend on it, see below |
| +9 | Slot marker | `1` on groups 1–8, `0` on groups 9+ in every capture (**unverified** meaning) |

**+8 flags:** in app-written slots the values were `3` for Force Charge and Force Discharge, `1` for
Feed-in and `0` for Self-Use, and the app showed "Charge from grid: Enabled" and "Charge / Discharge from
PV: Enabled" for the force slots (which would fit bit 0 = PV, bit 1 = grid). The value is **not**
recalculated when the app changes a slot's mode (Force Discharge → Back-up kept `3`). However, when a Force
Charge slot is written **over Modbus**, the inverter stores `0` here even if `3` is written, and the slot
still charges from the grid (see [Behaviour of a Force Charge slot](#behaviour-of-a-force-charge-slot)). A
Feed-in slot written with `1` kept `1`. Integrations should write the app's values but not verify this field.

### Work-mode codes

Group work modes use the same 1-based codes as register `49203`:

| Code | Mode | Status |
|---|---|---|
| 1 | Self Use | confirmed |
| 2 | Feed-in First | confirmed |
| 3 | Back-up | confirmed |
| 6 | Force Charge | confirmed |
| 7 | Force Discharge | confirmed |

Fox Cloud also lists `ForceCharge(BAT)` and `ForceDischarge(BAT)` for scheduler slots; their codes are
unknown. Peak Shaving (code `4` in `49203`) is not offered by the scheduler.

**`49203` is written with the same 1-based codes it reads.** Writing `2` read back as `2` and the Fox app
showed Feed-in First. (Earlier reports that EVO writes are 0-based, e.g. #1134, don't hold on this
inverter: writing `1` for "Feed-in" sets Self Use, which looks like the mode "reverting".)

### Fox Cloud field mapping

The Fox Cloud scheduler API stores the same data. Its group fields map onto the registers like this:

| Cloud field | Register |
|---|---|
| `enable` (group) | +0 (the cloud only lists enabled groups) |
| `startHour` / `startMinute` | +1 |
| `endHour` / `endMinute` | +2 |
| `workMode` | +3 |
| `extraParam.maxSoc` / `extraParam.minSocOnGrid` | +4 high / low byte |
| `extraParam.fdSoc` | +5 |
| `extraParam.fdPwr` | +6 |
| `enable` (top level) and `get/flag` → `enable` | `48000` |

`pvLimit`, `importLimit`, `exportLimit`, `reactivePower` and `secondWorkMode` also appear in the cloud
JSON but were not found inside the group block.

## Worked example

Schedule set in the Fox app (Mode Scheduler on):

| Slot | Time | Mode | Settings |
|---|---|---|---|
| 1 | 01:05–02:35 | Force Charge | cut-off 95 %, power 11000 W |
| 2 | 16:10–17:40 | Force Discharge | cut-off 25 %, power 12000 W |
| 3 | 20:15–21:45 | Feed-in First | min 30 %, max 85 % |
| (remaining) | 00:00–23:59 | Self-Use | min 10 %, max 100 % |

Registers read back:

```
48000: 1
48010: 1  261 547 6 25610 95 11000 0 3 1    ← slot 1  (01:05–02:35, Force Charge, 100/10, 95 %, 11000 W)
48020: 1 4106 4392 7 25610 25 12000 0 3 1   ← slot 2  (16:10–17:40, Force Discharge, 25 %, 12000 W)
48030: 1 5135 5421 2 21790 10     0 0 1 1   ← slot 3  (20:15–21:45, Feed-in, 85/30)
48040: 1    0 5947 1 25610 10     0 0 0 1   ← "Remaining Time Slots" filler (00:00–23:59, Self Use)
48050: 0    0    0 1 25610 10     0 0 0 1   ← blank slot (same for 48060, 48070, 48080)
48090: 0    0    0 1 25610 95 11000 0 3 0   ← stale, disabled copy (groups 9+)
```

## App behaviour

- **"Remaining Time Slots" is a real group.** The app writes it as an enabled 00:00–23:59 group after the
  user's slots. With overlapping groups the earlier slot takes priority (confirmed: a Force Charge slot
  placed before the all-day filler ran during its window).
- **Choosing a plain work mode** (e.g. Self-Use, Back-up) in the app sets `49203` to that mode and
  `48000 = 0`. The groups are left untouched.
- **Choosing Mode Scheduler** sets `48000 = 1` and leaves `49203` at whatever it was.
- **Changing a slot's mode** changes only +3. Power, cut-off SoC and flags keep their previous values.
- **Deleting a slot** sets +0 = 0 and zeroes the times. The mode, SoC and power values stay behind
  (flags are cleared on disabled slots).
- **Every save in the app rewrites groups 1–8.** A test value written over Modbus into a blank slot was
  wiped by the next app save. If Home Assistant owns the schedule, don't edit it in the Fox app.
- Disabled copies of old slots linger in groups 9+ with +9 = 0.

## Write behaviour

| Write | Scheduler | Result |
|---|---|---|
| 4 registers of a group (enable, start, end, mode), FC16 | on (set from the Fox app) | **Rejected** (Home Assistant: "Unknown error") |
| All 10 registers of a disabled group, FC16 | on (set from the Fox app) | **Accepted**, read back exactly |
| `48000` alone, FC6 | off | **Rejected**, `Exception Response(134, 6, IllegalAddress)` |
| `48000`–`48009` as one block, FC16 | off → on | **Accepted** |
| All 10 registers of an *enabled* group, FC16 | on | **Accepted**, read back exactly |

A schedule set from the Fox app / cloud did not stop Modbus writes in any of these tests.

### Fox Cloud / Fox app don't reliably reflect Modbus changes

- A slot change written over Modbus once appeared in Fox Cloud `scheduler/get` within ~2 minutes; another
  (written with raw register writes) had not appeared after 20+ minutes while it was actively running.
- The scheduler switch `48000` was never reflected: after switching it off over Modbus the cloud/app kept
  showing Mode Scheduler, and after switching it on they kept showing the plain work mode.
- The website did pick up a `49203` change (Feed-in) within a few minutes, but the Open API's
  `device/setting/get` with `WorkMode` returns errno 42015 (not supported) on the EVO.

Treat the registers as the truth. Saving in the Fox app while it shows a stale state may write that state
back to the inverter.

## Behaviour of a Force Charge slot

Tested with the scheduler on, a Force Charge slot (`fd_pwr` 1000 W, `fd_soc` a few % above the current SoC)
placed before the all-day Self-Use filler:

- **Slot order:** the earlier slot wins where slots overlap — it charged even though the filler covers the
  whole day.
- **Power:** it charged from the grid at ~990 W, i.e. `fd_pwr` is honoured (Remote Control instead uses its
  own Force Charge / Discharge Power settings, typically the inverter's full rating).
- **Cut-off:** charging stopped at `fd_soc` (allow ~1 % for rounding / BMS vs system SoC). For the rest of the
  slot the battery **held** at the cut-off and the house ran from the grid; the filler's Self Use resumed
  when the slot ended.
- **+8 flags:** written as `3` (what the app writes) it read back `0`, even with a raw write, yet grid charging
  still worked. Integrations shouldn't depend on this field for Force Charge.
- **Remote Control** Force Discharge overrode the active slot immediately; setting it back to Disable let the
  slot resume.

## SoC limits (scheduler off)

`46610` (System Max SoC) **is writable**. Writing `99` while `46620` (Max SoC From Grid) was `100` failed with
`IllegalValue` (not `IllegalAddress`): System Max can't be set below Max SoC From Grid. Lower `46620` first,
then `46610`; to raise, write `46610` first, then `46620`. Single-register writes were accepted for both.

While the Mode Scheduler is on, the inverter takes SoC limits from the active slot (+4), so changing the
global `46609`–`46611` then has no visible effect. That is a likely source of reports that EVO max SoC "can't
be changed".

## Remote Control (46001 …) alongside the scheduler

- A Remote Control Force Charge / Force Discharge **overrides** the active slot straight away, and the slot
  resumes when Remote Control is disabled.
- Its power comes from the Remote Control power setting, not from the slot's `fdPwr`.
- foxess_modbus's remote-control manager writes a "fallback" work mode to `49203` while active (Force
  Discharge → Feed-in First, Force Charge → Back-up) so the inverter does something sensible if Home
  Assistant disconnects. Upstream does not restore the previous work mode when Remote Control is disabled,
  so `49203` is left changed afterwards.

## Fox Cloud Open API notes (EVO)

| Call | Result on the EVO 10-5-H |
|---|---|
| `POST /op/v3/device/scheduler/get` with `{"deviceSN": …}` | Works; returns the groups shown above, but may be stale |
| `POST /op/v1/device/scheduler/get/flag` with `{"deviceSN": …}` | Works; `enable` does not track `48000` |
| `POST /op/v0/device/batteryHeating/get` with `{"sn": …}` | Works (warm-up enable, start/stop temperatures, 3 time windows) |
| `POST /op/v0/device/batteryHeating/get` with `{"deviceSN": …}` | errno 40257 ("Parameters do not meet expectations") |
| `POST /op/v0/device/setting/get` with `WorkMode` | errno 42015 (not supported on this device) |

## Recommendations for integrations

1. Read the group table, change what you need, then write **each changed group as one 10-register
   block**. Never write a partial group.
2. Set every field explicitly. Leftover values from earlier app edits are common.
3. Write the groups first, then the `48000`–`48009` block (as one block, never `48000` alone).
4. Read back and compare (except +8). Fail loudly on mismatch instead of trying alternative write patterns.
5. While `48000 = 1`, change behaviour through the groups, not `49203` or the global SoC registers.
6. Use the registers as the source of truth, never the Fox Cloud / app view.
7. To cap a grid charge, use the slot's cut-off SoC (+5); the battery then holds until the slot ends.

## Relation to earlier work

- **nathanmarlor/foxess_modbus#1071** mapped EVO charge periods onto the H1 `41xxx` registers, which do
  not exist on the EVO (see issue #1240).
- **#1134** moved them to `48010–48013` / `48020–48023`, treating +0 as "charge from grid" and +3 as a
  charge / no-charge flag (`6` / `1`). In this layout +0 is the group enable and +3 is the work mode
  (6 = Force Charge, 1 = Self Use). Only 4 of the 10 registers were written, so whether it worked depended
  on what the app had previously left in the other 6.
- **#1245** described the same 10-register layout for the H3 Smart / H3 Pro from the FoxESS protocol
  document (Table 3-11) and treated +7 and +8 as reserved. On the EVO the app writes non-zero values to
  +8, but the inverter stores `0` there for Force Charge slots written over Modbus and still grid-charges,
  so writing `0` appears harmless for Force Charge.
- **#1248** found System Max SoC (`46610`) rejecting 99 with exception 3 and suspected a dependency on
  Max SoC From Grid. Confirmed here: `46610` must be ≥ `46620`.
