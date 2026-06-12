# AFCI version register hunt (EVO)

Fox Cloud **Device Information** shows **Version_AFCI** (e.g. `0.37`). Master / Slave / Manager on EVO use **holding** registers **36001–36003** (PCS hex format, same as manager `0.30` ← raw `0x0030`).

An earlier mapping used **holding 36004** without verification. On many EVO inverters (including units **with** AFCI hardware) that address returns **IllegalAddress** — this is **not** the BCU register (BCU is **37033/37034**).

## Target decode

Fox `0.37` is typically:

| Raw (decimal) | PCS hex decode | Decimal decode |
|---------------|----------------|----------------|
| `55` (`0x0037`) | **0.37** | 0.55 |
| `37` | 0.25 | **0.37** |

Prefer PCS hex (matches manager at 36003).

## Automated probe (foxess_modbus_EVO)

`Version: AFCI` (`afci_version`) now **probes** holding `36004–36012` and `39004–39008` on connect and only registers the address that responds. Check logs for:

`AFCI version probe found register HOLDING <addr> raw=<n> -> 0.37`

Reload the FoxESS Modbus integration after updating.

## Manual scan (Developer Tools → Actions)

Run **`foxess_modbus.read_registers`** for each block. Replace inverter name.

### Version block (holding)

```yaml
action: foxess_modbus.read_registers
data:
  inverter: "EVO-10"
  type: holding
  start_address: 36000
  count: 16
```

Look for raw values **`37`** or **`55`** (or nearby). Decode with PCS hex: `major = raw >> 8`, `minor = raw & 0xFF`, display `f"{major:X}.{minor:02X}"`.

### PCS / protocol block (holding)

```yaml
action: foxess_modbus.read_registers
data:
  inverter: "EVO-10"
  type: holding
  start_address: 39000
  count: 24
```

### Legacy input block (optional)

```yaml
action: foxess_modbus.read_registers
data:
  inverter: "EVO-10"
  type: input
  start_address: 10016
  count: 12
```

## When you find a match

Note the **address**, **register type**, **raw value**, and Fox Cloud **Version_AFCI**. Open an issue or PR on `foxess_modbus_EVO` with that row so we can add a fixed mapping and remove probing.
