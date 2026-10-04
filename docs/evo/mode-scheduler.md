# EVO Mode Scheduler (48000–48249)

How the EVO stores the Fox app's **Mode Scheduler** (per-time-slot work modes, also used by the app's
Stormsafe feature) in holding registers, and how to read and write it safely over Modbus.

Status key: ✅ confirmed on hardware · ⚠️ differs from the FoxESS protocol document · ❓ not yet tested.
See [README](README.md) for the hardware these results come from.

## Summary

- ✅ `48000` is the Mode Scheduler master switch (`1` = on).
- ✅ The schedule is a table of **time groups**, 10 registers each, starting at `48010`.
- ✅ ⚠️ **Write whole 10-register blocks only.** The inverter rejects any write that covers part of a block —
  including a single-register write to `48000`. This is why writing 4 registers per "charge period" works on
  some inverters and fails with `IllegalAddress` on others: it depends on what is already in the block.
- ✅ A schedule set from the Fox app does **not** stop Modbus writes. (A widely repeated claim that a
  cloud-set schedule makes the scheduler read-only to Modbus was not reproduced.)
- ✅ While `48000 = 1`, the slots decide what the inverter does and the work-mode register `49203` is
  ignored — writing `49203` alone will appear to "not work".
- ✅ The earlier slot wins where slots overlap.
- ✅ The Fox app and Fox Cloud do not reliably show changes made over Modbus. Read the registers.

## Register map

### Master switch block (48000–48009)

| Register | Meaning | Status |
|---|---|---|
| `48000` | Mode Scheduler: `0` off (inverter follows `49203`), `1` on | ✅ |
| `48001`–`48009` | always `0` | ✅ |

Write the block as a whole, e.g. `1,0,0,0,0,0,0,0,0,0` to switch on. ✅ A single-register (FC6) write to
`48000` returns `Exception Response(134, 6, IllegalAddress)`.

### Time groups

Group *N* (1-based) starts at **`48010 + 10 × (N − 1)`**. The Fox app manages groups **1–8**. ✅ ⚠️ All
**96** groups (`48010`–`48969`) are readable on the EVO, matching Fox Cloud's `maxGroupCount: 96` — the FoxESS
document says 24. Groups beyond 8 held disabled copies of earlier app schedules.

| Offset | Meaning | Encoding | Status |
|---|---|---|---|
| +0 | Group enabled | `1` / `0` | ✅ |
| +1 | Start time | `hour × 256 + minute` (e.g. `261` = 01:05) | ✅ |
| +2 | End time | `hour × 256 + minute` (e.g. `5947` = 23:59) | ✅ |
| +3 | Work mode | see [work-mode codes](#work-mode-codes) | ✅ |
| +4 | Max SoC / Min SoC (on grid) | `max × 256 + min` (e.g. `21790` = 85 % / 30 %) | ✅ |
| +5 | Cut-off SoC (`fdSoc`) | % — Force Charge stops at this SoC, Force Discharge stops at this SoC | ✅ |
| +6 | Force charge / discharge power (`fdPwr`) | W | ✅ |
| +7 | Unknown | always `0` observed | ❓ |
| +8 | Flags | see below | ⚠️ |
| +9 | Slot marker | `1` on groups 1–8, `0` on groups 9+ in every capture | ⚠️ ❓ |

**+8 flags.** ⚠️ The FoxESS document calls +7, +8 and +9 "reserved", but the app writes to them. In
app-created slots +8 was `3` for Force Charge / Force Discharge, `1` for Feed-in and `0` for Self-Use; for
the force slots the app showed "Charge from grid: Enabled" and "Charge/Discharge from PV: Enabled", which
would fit bit 0 = PV and bit 1 = grid (❓ not tested bit by bit). The value is **not** recalculated when the
app changes a slot's mode. When a Force Charge slot is written over Modbus, the inverter stores `0` in +8
even if `3` is written — and the slot **still charges from the grid** (✅). A Feed-in slot written with `1`
kept `1`. **Write the app's values, but don't verify this field after writing.**

### Work-mode codes

Slots use the same codes as `49203`:

| Code | Mode | Status |
|---|---|---|
| 1 | Self Use | ✅ |
| 2 | Feed-in First | ✅ |
| 3 | Back-up | ✅ |
| 4 | Peak Shaving | ❓ listed in the FoxESS document; the Fox app doesn't offer it for slots |
| 5 | PowerStation | ❓ listed in the FoxESS document |
| 6 | Force Charge | ✅ |
| 7 | Force Discharge | ✅ |

Fox Cloud also lists `ForceCharge(BAT)` and `ForceDischarge(BAT)` slot modes; their codes are unknown.

## Example: a schedule created in the Fox app

| Slot | Time | Mode | Settings |
|---|---|---|---|
| 1 | 01:05–02:35 | Force Charge | cut-off 95 %, power 11000 W |
| 2 | 16:10–17:40 | Force Discharge | cut-off 25 %, power 12000 W |
| 3 | 20:15–21:45 | Feed-in First | min 30 %, max 85 % |
| (remaining) | 00:00–23:59 | Self-Use | min 10 %, max 100 % |

```
48000: 1
48010: 1  261  547 6 25610 95 11000 0 3 1   slot 1: 01:05–02:35, Force Charge, 100/10, cut-off 95 %, 11000 W
48020: 1 4106 4392 7 25610 25 12000 0 3 1   slot 2: 16:10–17:40, Force Discharge, cut-off 25 %, 12000 W
48030: 1 5135 5421 2 21790 10     0 0 1 1   slot 3: 20:15–21:45, Feed-in, max 85 / min 30
48040: 1    0 5947 1 25610 10     0 0 0 1   "Remaining Time Slots": 00:00–23:59, Self Use
48050: 0    0    0 1 25610 10     0 0 0 1   unused slot (same for 48060, 48070, 48080)
48090: 0    0    0 1 25610 95 11000 0 3 0   stale disabled copy of an old slot (groups 9+)
```

## How the Fox app uses the table

- ✅ **"Remaining Time Slots" is a real group** — an enabled 00:00–23:59 slot placed after the user's slots.
  Because the earlier slot wins, the user's slots take priority over it.
- ✅ **Choosing a plain work mode** (Self-Use, Back-up, …) sets `49203` and `48000 = 0`; the groups are left as
  they are. **Choosing Mode Scheduler** sets `48000 = 1` and leaves `49203` unchanged.
- ✅ **Changing a slot's mode** only changes +3; power, cut-off and flags keep their old values.
- ✅ **Deleting a slot** sets +0 = 0 and zeroes the times; the mode, SoC and power values stay behind.
- ✅ **Every save rewrites groups 1–8.** A value written over Modbus into an unused slot was wiped by the next
  app save. If something else (e.g. Home Assistant) owns the schedule, don't edit it in the app.
- ✅ Disabled copies of old slots linger in groups 9+ (with +9 = 0).

## Write behaviour

| Write | Scheduler | Result |
|---|---|---|
| 4 registers of a group (enable, start, end, mode), FC16 | on (set from the Fox app) | ✅ **rejected** |
| all 10 registers of a disabled group, FC16 | on (set from the Fox app) | ✅ accepted, read back exactly |
| all 10 registers of an enabled group, FC16 | on | ✅ accepted, read back exactly (except +8, see above) |
| `48000` alone, FC6 | off | ✅ **rejected** (`IllegalAddress`) |
| `48000`–`48009` as one block, FC16 | off → on, on → off | ✅ accepted |
| groups 1–8 (`48010`–`48089`) as one 80-register block | — | ❓ the FoxESS document says this is allowed; it would make a schedule write atomic |

## Behaviour of a Force Charge slot

Tested with the scheduler on and a Force Charge slot (power 1000 W, cut-off a couple of % above the current
SoC) placed before the all-day Self-Use slot, at night:

- ✅ **Priority:** it ran even though the Self-Use slot covers the whole day.
- ✅ **Power:** the battery charged from the grid at ~990 W — `fdPwr` is honoured.
- ✅ **Cut-off:** charging stopped at the cut-off SoC (allow ~1 % for rounding / BMS vs system SoC).
- ✅ **After the cut-off the battery holds** for the rest of the slot: the house runs from the grid and the
  battery neither charges nor discharges. Self Use resumed when the slot ended.
- ✅ **Remote Control** Force Discharge overrode the running slot immediately; disabling Remote Control let
  the slot resume. See [work mode, SoC limits and Remote Control](work-mode-soc-remote-control.md).

## Fox Cloud field mapping

The Fox Cloud scheduler API holds the same data (see [Fox Cloud API](fox-cloud-api.md) for reliability):

| Cloud field | Register |
|---|---|
| group `enable` | +0 (the cloud only lists enabled groups) |
| `startHour` / `startMinute` | +1 |
| `endHour` / `endMinute` | +2 |
| `workMode` | +3 |
| `extraParam.maxSoc` / `extraParam.minSocOnGrid` | +4 high / low byte |
| `extraParam.fdSoc` | +5 |
| `extraParam.fdPwr` | +6 |
| top-level `enable` and `get/flag` → `enable` | `48000` (but the cloud does not track it, see Fox Cloud API) |

`pvLimit`, `importLimit`, `exportLimit`, `reactivePower` and `secondWorkMode` also appear in the cloud JSON;
they were not found in the group block.

## Recommendations for integrations

1. Read the table, change what you need, then write **each changed group as one 10-register block**.
   Never write part of a block.
2. Set every field explicitly — leftovers from earlier app edits are common.
3. Write the groups first, then the `48000`–`48009` block.
4. Read back and compare (skip +8). On a mismatch, fail with a clear error rather than trying other write
   patterns.
5. Always add an all-day "remaining" slot after your slots, as the app does.
6. While the scheduler is on, change behaviour through the slots — not `49203` or the global SoC registers.
7. To cap a grid charge, use the slot's cut-off SoC (+5); the battery then holds until the slot ends.
8. Use the registers, not the Fox app or cloud, as the source of truth.

## Comparison with the FoxESS protocol document

FoxESS's *Modbus Protocol V1.05.03.00* Table 3-11 "Time Period Table" has the same layout (`48000`
"TimeMode Flag", 10-register groups from `48010`, fields +0…+6, the same work-mode codes). Differences
and gaps found on the EVO are marked ⚠️ above. The document also states — ❓ untested on the EVO:

- slot Max SoC and Min SoC On Grid are `[10, 100]`, Min SoC On Grid ≥ the global Minimum SoC (`46609`) and
  ≤ the slot Max SoC, and the cut-off SoC is `[slot Min SoC On Grid, 100]` (Fox Cloud reports a minimum of 5);
- at most 24 groups — ⚠️ the EVO has 96 readable groups (see above);
- the table can also be written as four blocks: `48000–48009`, `48010–48089`, `48090–48169`, `48170–48249`.

## Relation to earlier foxess_modbus work

- **nathanmarlor/foxess_modbus#1071** mapped EVO charge periods onto the H1 `41xxx` registers, which the EVO
  doesn't use for this (see issue #1240).
- **#1134** moved them to `48010–48013` / `48020–48023`, treating +0 as "charge from grid" and +3 as a
  charge / no-charge flag (`6` / `1`). In fact +0 is the group enable and +3 the work mode (6 = Force Charge,
  1 = Self Use), and only 4 of the 10 registers were written — so whether it worked depended on what the
  app had left in the rest of the block.
- **#1245** described this layout for the H3 Smart / H3 Pro from the protocol document.
- **#1248** found System Max SoC rejecting 99 and suspected a dependency on Max SoC From Grid — confirmed,
  see [work mode, SoC limits and Remote Control](work-mode-soc-remote-control.md).
