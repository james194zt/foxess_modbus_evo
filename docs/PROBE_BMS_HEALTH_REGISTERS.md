# BMS health & harmful-event register hunt (EVO / H3 PRO / H3 SMART)

Fox Cloud Real-time shows battery **Health** and **Tracking of harmful events** fields that are not yet mapped in `foxess_modbus`. Live probing on EVO 10-H shows they are **not cloud-only** in principle: the BMS exposes extra data on the **37xxx** holding block that the public PDF skips.

## Fox Cloud vs Modbus timing

On EVO, **Modbus is the live source** (seconds). The Fox app often **lags by ~1 minute or more**, especially for **PV / power / current** while conditions are changing. Screenshots taken “at the same time” can still disagree on fast-moving fields (voltage under load, battery power, daily energy totals ticking up).

When validating register mappings:

- Prefer **stable** values (SOH, throughput totals, serials, gap counters that do not move every poll).
- Treat small differences on **cumulative** metrics (e.g. 672.0 vs 672.5 Ah) as normal if the cloud snapshot is stale.
- For **live** power/voltage, trust Modbus for the dashboard; use Fox only for rough cross-check, not exact match.
- A “mismatch” (e.g. **37622** vs Fox cycles) is weaker evidence if the cloud row may be computed or cached on a different schedule.

## What the public PDF documents

| Registers | PDF name | Role |
|-----------|----------|------|
| 37609–37620 | Voltage, current, temps, cell mV | General / live |
| **37621–37623** | *(not listed)* | **Gap — prime counter candidates** |
| 37624 | BMS1 SOH | Health |
| **37626–37631** | BMS1 Fault1–6 | **16-bit fault bitfields** |
| 37632–37636 | Remain energy, FCC, design energy, force-charge flag | General |

The Ah throughput discovery (**37613** / **37614**) proved that Fox UI fields can live in PDF gaps with non-obvious scales. The same pattern likely applies to harmful events.

## Harmful events — two mechanisms

### 1. Live fault bitfields (37626–37631)

When the BMS raises a condition (deep discharge, over-temp, etc.), bits in **Fault1–Fault6** may go high. With a healthy pack these read **0** (as in your dumps).

- These are **state**, not necessarily the cumulative count Fox shows in “Number of deep discharge event”.
- Still essential: note the **raw value** and **which bits** changed when Fox reports a new harmful event.

Probe entities: `bms_fault_1_raw` … `bms_fault_6_raw` (enabled by default on supported models).

Decode a raw fault value to bits (Developer Tools → Template), replacing the entity id:

```jinja2
{% set raw = states('sensor.evo_10_bms_fault_1_raw') | int(0) %}
{% set bits = namespace(on=[]) %}
{% for i in range(16) %}
  {% if (raw >> i) & 1 %}{% set bits.on = bits.on + [i] %}{% endif %}
{% endfor %}
{{ bits.on }}
```

Or: `python3 -c "print(f'{12345:016b}')"` for a raw integer from `read_registers`.

### 2. Cumulative counters (likely 37621–37623)

Your stable reads show:

| Register | Raw | Notes |
|----------|-----|-------|
| **37621** | 2 | Fixed across reads — not SOC |
| **37622** | 15 | Fixed; Fox cycles ≈13 — **close but not exact** |
| **37623** | 0 | Fixed |

**37622 = 15** is the strongest lead for a **lifetime counter** (deep discharge count, partial cycles, or BMS-internal equivalent). Fox showing `--` for zero events does **not** rule this out if the counter measures something else (e.g. BMS cycle index).

Probe entities: `bms_gap_37621`, `bms_gap_37622`, `bms_gap_37623`.

**Extreme-temp “time spent”** is often stored as **minutes** (U16 or U32). If U32, try pairing:

- low word = 37621, high word = 37622 (or the reverse)
- test: `37621 + 37622 * 65536` against Fox minutes

## Health metrics (still unmapped)

| Fox UI field | Likely source |
|--------------|---------------|
| Evolution of self-discharging rates | Unknown — may be trend computed in cloud **or** gap register with scale |
| Remaining Power Capacity | Possibly derived from max discharge current × voltage / SOH; check **46616** + **37609** |
| Remaining Round trip efficiency | May be BMS-internal; try gap registers or **37000–37199** block |
| Ohmic resistance | Often mΩ — scan **37037–37096** (between slave versions and serials) |

**37616** / **37625** (= 500 → **50 Ah** at ×0.1) duplicate **FCC** at 100% SOC — not remaining power capacity.

## Correlation test (do this when you can)

1. Enable probe sensors on the FoxESS-Modbus device (Settings → Entities).
2. Record **Fox app screenshot** + `foxess_modbus.read_registers` **37609–37636** at the same moment.
3. After any **deep discharge** or **extreme temperature** event Fox logs, repeat step 2 and note which register **incremented**.
4. Optional wide scan when idle:

```yaml
action: foxess_modbus.read_registers
data:
  inverter: "House Inverter"
  type: holding
  start_address: 37000
  count: 120
```

Compare **37037–37096** against Fox health rows.

### EVO scan result (37000–37119, 2026-05)

| Range | Finding |
|-------|---------|
| **37002** | `1` = BMS1 online (matches `bms_online`) |
| **37003–37004** | Master version `257` (0x0101), control type `113` |
| **37005–37012** | Master SN ASCII — mirrors pack 1 serial start |
| **37013–37031** | All `0` (padding) |
| **37032** | `4` = four slave packs |
| **37033–37036** | `0x1000` … `0x4000` = slave 1–4 version tokens — decode as `{(v>>12)}.{(v&0xFFF):03d}` (e.g. `0x1001` → **1.001**, Fox **Version_BCU**) |
| **37037–37064** | All `0` — **no health counters here** |
| **37065–37068** | All `255` — likely **per-pack manufacture date** sentinels (Fox shows `--`) |
| **37069–37096** | All `0` |
| **37097–37104** | Pack 1 serial → e.g. `6086372058LT085` |
| **37113–37118** | Pack 2 serial **starts identical** to pack 1 in partial read — read **37113–37128** fully |

**Conclusion:** Health / harmful-event **counters are not in 37000–37119**. Continue with **37621–37623** and **37626–37631**, and read **37120–37160** for packs 2–4 serials (Expected life grid).

## Derived health sensors (EVO, algorithmic)

Until Fox-exact registers are found, `foxess_modbus` exposes **estimated** health rows from existing inputs (`modbus_battery_health_sensors.py`):

| Entity key | Formula (summary) |
|------------|-------------------|
| `battery_ah_remaining` | SOC × **37616** nominal Ah / 100 (direct Modbus read, Fox parity) |
| `bms_remaining_power_capacity` | `max_discharge_current × batvolt_1 / 1000 × SOH/100` |
| `bms_round_trip_efficiency_remaining` | `discharge_total / charge_total × 100`, capped by SOH |
| `bms_ohmic_resistance` | Δcell mV / \|current\| under load; SOH baseline at rest |
| `bms_self_discharge_rate` | Low baseline + wear from (100−SOH) and cycles (%/day) |
| `bms_deep_discharge_event_count` etc. | Placeholder **0** until counters mapped |

Tune formulas when Fox eventually shows non-`--` values on an aged pack.

## When a register is confirmed

1. Add scaled entity in `entity_descriptions.py` (`_bms_entities`).
2. Add key to `foxess_plant` `PANEL_ENTITY_SUFFIXES`.
3. Replace `[null, "…"]` row in `DEVICE_NEW_REALTIME_SECTIONS` in `foxess-plant-panel.js`.
