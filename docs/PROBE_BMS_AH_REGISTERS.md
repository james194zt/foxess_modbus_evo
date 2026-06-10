# BMS Ah throughput registers (found on EVO)

Fox Real-time **Charge / Discharge Capacity throughput** (Ah) map to the PDF gap between SOC and max cell temp.

## Confirmed mapping (live EVO, 2026-05)

| Register | Raw (example) | Scale | Fox UI |
|----------|---------------|-------|--------|
| **37614** | 1792 | **× 3/8 (0.375)** | Charge capacity throughput **672.5 Ah** (672.0 rounded) |
| **37613** | 2304 | **× 4/15 (0.266̄)** | Discharge capacity throughput **614.4 Ah** |

Validation:

- `1792 × 3/8 = 672.0` ≈ Fox 672.5 Ah  
- `2304 × 4/15 = 614.4` = Fox 614.4 Ah  

Modbus entities: `bms_charge_capacity_throughput_ah`, `bms_discharge_capacity_throughput_ah`.

## Other gap registers (same dump, not Ah throughput)

| Register | Raw | Notes |
|----------|-----|-------|
| 37615 | 0 | unused / reserved |
| 37616 | 500 | ×0.1 → 50 Ah (matches FCC / remaining @ 100% SOC) |
| 37621 | 0 | reserved |
| 37622 | 15 | unknown (Fox cycles showed 13 — different counter?) |
| 37623 | 0 | reserved |
| 37625 | 500 | same as 37616 |

## Re-verify after firmware update

```yaml
action: foxess_modbus.read_registers
data:
  inverter: "House Inverter"
  type: holding
  start_address: 37609
  count: 28
```

After a charge session, **37614** should increase; after discharge, **37613** should increase.
