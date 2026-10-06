# Battery temperatures

The EVO reports three battery temperatures. Only two are cell readings, and the names upstream foxess_modbus
gave them on the EVO were misleading. This page shows what each register measures, the evidence, and why the
fork renamed two sensors.

## Summary

| Register | Fox protocol name | What it measures | Fork sensor (EVO) | Status |
|---|---|---|---|---|
| `37611` | BMS1 Ambient Temperature | Air temperature inside the battery's BMS control unit (the board) — **not a cell** | **Battery 1 BMS Board Temp** (was "Battery 1 Temp") | ✅ ⚠️ |
| `37617` | BMS1 Max Temperature | Warmest cell | BMS 1 Cell Temp High | ✅ |
| `37618` | BMS1 Min Temperature | Coldest cell | BMS 1 Cell Temp Low, and **Battery 1 Min Cell Temp** (was "Ambient Temp") | ✅ ⚠️ |

All are holding registers, signed (I16), ×0.1 °C.

**For cold-weather decisions use `37618` (coldest cell).** The BMS limits or blocks charging based on its
cell temperatures; the board temperature (`37611`) runs about 12 °C warmer than the warmest cell and would make
a cold battery look warm.

## Evidence

### 1. FoxESS's own register names

*Modbus Protocol V1.05.03.00* lists the BMS1 block as:

```
37611  BMS1 Ambient Temperature   RO  I16  ℃  /10
37612  BMS1 SoC                   RO  U16  %
37617  BMS1 Max Temperature       RO  I16  ℃  /10
37618  BMS1 Min Temperature       RO  I16  ℃  /10
```

"Ambient" here is the BMS's ambient — the inside of the battery's control unit — not outdoor air and not a
cell.

### 2. Three days of readings (EVO 10-5-H, one pack, early October 2026)

Home Assistant history for `37611`, the inverter temperature (`39141`), both cell readings and battery power,
sampled every 15 minutes over 3 days:

| Sensor | Min | Mean | Max |
|---|---|---|---|
| `37611` | 32.3 °C | 37.9 °C | 40.8 °C |
| Inverter (`39141`) | — | 39.7 °C | — |
| Coldest cell (`37618`) | — | 19.7 °C | — |
| Warmest cell (`37617`) | — | 25.7 °C | — |

How closely `37611` follows each of the others:

| Compared with | Correlation (r) | Average difference | Spread of the difference (sd) |
|---|---|---|---|
| Warmest cell (`37617`) | **+0.86** | +12.1 °C | **1.0 °C** |
| Inverter (`39141`) | +0.81 | −1.9 °C | 1.6 °C |
| Coldest cell (`37618`) | +0.74 | +18.2 °C | 1.6 °C |
| Battery power (charge or discharge, absolute) | +0.04 | — | — |

What this shows:

- **It is not a cell.** It reads 12–18 °C above both cell sensors all the time, including at night with the
  battery idle. Cells inside the same pack can't sit that far apart.
- **It is not the inverter.** When the inverter heats up, `37611` does not follow. Examples:
  - Saturday 14:08: `37611` 40.3 °C, inverter 45.2 °C.
  - Monday 23:08: `37611` 40.8 °C, inverter 44.3 °C.

  At other times it reads *above* the inverter (Monday 11:08: 39.2 °C vs 38.6 °C), so it is not a fixed
  offset from it either.
- **It sits on the battery side.** Its best and steadiest match is the warmest cell, at a near-constant
  +12 °C (spread only 1 °C): a board in the pack's control unit, warmed by its own electronics and following
  the pack's overall temperature.
- **Battery power makes no difference** (r = 0.04), so it is not a power-stage or DC converter sensor that
  heats with current.

### 3. `37618` was labelled "Ambient Temp"

Upstream foxess_modbus mapped the generic **Ambient Temp** sensor to `37618` on the EVO, because the EVO has
no separate ambient sensor. `37618` is the BMS minimum (coldest) cell temperature — the same register as
**BMS 1 Cell Temp Low**. The name made it look like outdoor or room temperature.

## What changed in the fork

- `37611`: **Battery 1 Temp → Battery 1 BMS Board Temp**.
- `37618`: **Ambient Temp → Battery 1 Min Cell Temp**. It is a duplicate of BMS 1 Cell Temp Low and is kept
  so existing dashboards and history keep working.

Only the display names changed, and only for the EVO. Entity IDs and unique IDs are unchanged, so history,
automations and dashboards carry on working. If you created the integration before this change, Home
Assistant keeps the old entity IDs (e.g. `sensor.…_ambtemp`, `sensor.…_battery_temp_1`); only the friendly
name updates. Other models (H1, H3, H3 Pro, KH, …) are untouched — their registers may mean something
different, so this was not applied to them without testing.

## Reproducing this

1. Record `37611`, `37617`, `37618`, `39141` and battery power in Home Assistant for a few days (the fork's
   sensors already do this).
2. Pull the history with the REST API (`/api/history/period/<start>?filter_entity_id=…&end_time=<now>` —
   without `end_time` Home Assistant returns only one day).
3. Sample all series onto the same 15-minute grid and compare: correlation and the mean and spread of the
   difference. The register whose difference to `37611` has the smallest spread is the one it moves with.

Please share results from other EVO models or with more than one battery pack — see
[testing method](testing-method.md).
