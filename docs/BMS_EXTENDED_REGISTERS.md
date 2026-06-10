# BMS extended registers (H3 PRO / H3 SMART / EVO)

Fox Cloud Real-time shows several battery health fields that are not yet mapped in `foxess_modbus`. This document tracks what is known from the Fox H3 Smart Modbus PDF (via [TippvomTibb](https://tippvomtibb.de/mediawiki/FOX_ESS_Photovoltaik-Anlage)) and what still needs live probing.

## Mapped in this fork (holding registers, pack 1)

| Register | Fox signal | Unit | Scale | Entity key | Fox UI label |
|----------|------------|------|-------|------------|--------------|
| 37633 | BMS1 FCC Capacity | Ah | 0.1 | `bms_ah_fcc` | (used for Remaining Capacity calc) |
| 37635 | BMS1 Design Energy | Wh | **10** (EVO: raw 1024 → 10240 Wh) | `bms_design_energy_wh` | **Capacity** (e.g. 10240 Wh) |
| — | SoC × FCC / 100 | Ah | — | `battery_ah_remaining` | **Remaining Capacity** |

See **[PROBE_BMS_AH_REGISTERS.md](PROBE_BMS_AH_REGISTERS.md)** for the Ah throughput register hunt (gaps 37613–37616).

## Already mapped (reference)

| Register | Entity key | Fox UI |
|----------|------------|--------|
| 37609–37620 | `batvolt_1`, `bat_current_1`, `battery_soc_1`, `battery_soh`, temps, cell mV | General / Health |
| 37632 | `bms_kwh_remaining_1` | Nominal capacity (kWh) — used for cycle math |
| 39605–39610 | charge/discharge totals | Energy throughput (kWh) |
| 37097+ | `bms_pack_serial_modbus` | Expected life serials |

## Probe unknown registers on your inverter

Use **Developer Tools → Actions → `foxess_modbus.read_registers`**:

```yaml
action: foxess_modbus.read_registers
data:
  inverter: "<your inverter friendly name>"
  type: holding
  start_address: 37609
  count: 28
```

Compare raw values with Fox Cloud Real-time (especially while values change):

| Register | PDF name | Notes |
|----------|----------|-------|
| 37613–37616 | (gap) | Not in public PDF — candidate for Ah throughput counters |
| 37621–37623 | (gap) | Not in public PDF — **probe sensors** `bms_gap_37621` etc. |
| 37626–37631 | BMS1 Fault1–6 | Bitfields — **probe sensors** `bms_fault_1_raw` … `bms_fault_6_raw` |
| 37634 | reserve | Unknown |

See **[PROBE_BMS_HEALTH_REGISTERS.md](PROBE_BMS_HEALTH_REGISTERS.md)** for harmful-event and health correlation tests.

### Still unmapped (likely on Modbus, address TBD)

These appear on Fox Cloud; the public PDF does not name them, but **37613/37614** showed they can still be on the wire:

- Evolution of self-discharging rates
- Remaining Power Capacity
- Remaining Round trip efficiency
- Ohmic resistance
- Deep discharge event count — **37622** is a lead (raw 15 vs Fox cycles ≈13)
- Time spent in extreme temp / charging in extreme temp — try **37621–37623** as U16/U32 minutes

**Mapped:** Charge / Discharge **Capacity** throughput (Ah) — **37614 / 37613**.

When probing finds stable matches, add entities in `entity_descriptions.py` and wire them in `foxess_plant` `PANEL_ENTITY_SUFFIXES`.
