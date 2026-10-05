# Battery warm-up (`53400`–`53414`)

The Fox app's **Battery warm-up** settings (start/end temperature and three heating periods) are in an
undocumented block of holding registers at `53400`. ✅ They can be **read** over Modbus. ✅ They **can't be
written**: every write is refused with `IllegalAddress` (exception 2), so change them in the Fox app or with
the Fox Cloud API (`batteryHeating/set`, see [Fox Cloud API](fox-cloud-api.md)).

What warm-up does is described in the EVO user manual (§2.6): it is only available on heated battery
versions, and outside the "full power" periods it heats using surplus PV only.

## Layout

| Register | Field | Encoding | Example |
|---|---|---|---|
| `53400` | Warm-up enabled | 0 off, 1 on | `1` |
| `53401` | Start temperature | °C | `7` |
| `53402` | End temperature | °C | `13` |
| `53403` | Period 1 enabled | 0 / 1 | `1` |
| `53404` | Period 1 start | `hour × 256 + minute` | `267` = 01:11 |
| `53405` | Period 1 end | `hour × 256 + minute` | `534` = 02:22 |
| `53406`–`53408` | Period 2 enabled, start, end | as period 1 | `1`, 03:17, 04:43 |
| `53409`–`53411` | Period 3 enabled, start, end | as period 1 | `1`, 05:29, 06:52 |
| `53412`–`53414` | ❓ unknown — same shape as a period | as period 1 | `1`, 01:09, 05:15 |
| `53415`–`53427` | ❓ unknown, all 0 | | |

The example values are test settings entered in the Fox app (chosen so each field could only match one
register), confirmed against the Fox Cloud's `batteryHeating/get` at the same time. Times use the same
encoding as the [Mode Scheduler](mode-scheduler.md).

`53412`–`53414` look like a fourth period, but the Fox app only shows three and the values there weren't set by
us. A factory default or a hidden period are both possible — reports from other inverters welcome.

## Writes are refused

Tested by writing the current values back unchanged. Directly over Modbus TCP, so the inverter's reply could
be seen:

| Write | Reply |
|---|---|
| Write single register (FC6) `53401` | ❌ exception 2 `IllegalAddress` |
| Write multiple (FC16) `53400` × 3, × 15, × 28 | ❌ exception 2 `IllegalAddress` |

Through `foxess_modbus.write_registers`, which doesn't show the code: FC6 `53400` and `53401`, and FC16
`53400` × 3, × 10, × 12, × 15, × 20, × 28 and `53403` × 3 were all refused.

The same writes were refused in the same way with warm-up switched **off** in the app, so it isn't the
feature being active that locks the registers. Unlike the Mode Scheduler, where the *shape* of a write
matters, no shape was accepted here.

Changes made in the app reached these registers within a couple of minutes. Turning warm-up off cleared
`53400` and each period's enable flag but left the period times in place.

## How it was found

The snapshot-and-compare method in [testing method](testing-method.md) found nothing in the readable holding
registers `30000`–`49999`. Extending the sweep to `50000`–`65535` turned up four small readable areas:
`50021`–`50045`, `53400`–`53427`, `55000`–`55020` and `60003`–`60005`. The warm-up test values were all in
`53400`–`53411`. The other three areas have not been identified.

## In Home Assistant

The foxess_modbus fork in this repository adds read-only entities for the EVO: **Battery Warm-up** (on/off),
**Battery Warm-up Start / End Temperature**, and **Battery Warm-up Period 1–3** (e.g. `01:11-02:22`, or
`Off`).
