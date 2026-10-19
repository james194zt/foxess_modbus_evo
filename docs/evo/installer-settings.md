# EVO installer settings

Settings an installer sets on the inverter itself (its on-board menus) that the Fox app doesn't show. The fork
exposes them all as read-only sensors, and a few as controls you can change (see [Writable settings](#writable-settings)).
Read on an EVO 10-5-H (5 kW model) set up for a UK G99 connection limited to 3.68 kW.

| Sensor | Holding register(s) | Format | Example | Notes |
|---|---|---|---|---|
| Grid Standard Code | 49079 | U16 | 3 | Number from the protocol's table 4-2: 2 G98_UK, 3 G99_UK, 7 VDE4105_DE, 72/73 G98/G99_NI … (98 codes, every region) |
| Rated Power | 39053–39054 | I32 W | 3680 | |
| Max Active Power | 39055–39056 | I32 W | 3680 | The most the inverter puts out on the AC side. PV above it charges the battery; it's only lost (clipped) when the battery can't take it |
| Active Power Limit | 49007 | I16, 0.1 % | 1000 (100.0 %) | 100 % = no derating |
| Fixed Active Power Derate | 49008–49009 | U32 W | 0 | 0 = not set |
| Export Power Limit (Installer) | 46616–46617 | I32 W | 15000 | 15 kW = effectively no limit |
| Grid Point Power Limit | 49136–49137 | I32 W | 15000 | Protocol default is Pmax |
| Import Current Limit | 46618 | I16, 0.1 A | 320 (32.0 A) | |
| Export Current Limit | 46619 | I16, 0.1 A | 630 (63.0 A) | |
| Import Power Limit (Installer) | 46501–46502 | I32 W | 13000 | The most the system draws from the grid |
| Peak Shaving Threshold SoC | 46503 | U16 % | 0 | Peak Shaving work mode (4) only |
| Peak Shaving Export Limit | 46504–46505 | I32 W | 13000 | Peak Shaving work mode only |
| Meter 1 / CT 1 | 49207 | U16 code | 2 | 0 off, 1 single-phase meter, 2 CT, 3 three-phase meter |
| Meter 2 / CT 2 | 49208 | U16 code | 0 | as above |
| Meter Compensation | 49248 | I16 W | 0 | Offset for a meter/CT that reads slightly off, ±500 W |
| EPS Output Mode | 46613 | U16 code | 3 | 0 disable, 2 EPS mode, 3 UPS mode |
| EPS Frequency Setting | 46612 | U16 code | 1 | 0 invalid, 1 50 Hz, 2 60 Hz (the live EPS frequency is 39218) |
| MPPT Scan | 49210 | U16 | 0 | 0 off, 1 on |

46500 refuses reads on the EVO (the block starts at 46501). 46506–46514 (peak-shaving "charge in low import"
times) read 0. Also readable and 0 / off here, not exposed: power factor and reactive power settings (49005,
49006, 49010), balance load (46614–46615), idle mode (49229–49230), off-grid master (49247), buzzer (49209),
screen brightness (49221), relays (49211–49212), ripple control (49241–49246), DRM (49206, Australia only).

39057–39060 also read 3680 on this inverter (probably apparent and reactive power maximums; not mapped).
Max charge / discharge current (46607 / 46608, 50.0 A here) were already mapped.

Evidence the AC cap is real: on a clear day PV peaked at 4.48 kW while the inverter's AC output never went above
3.688 kW, sitting at 3.67 kW for long stretches; the battery took the rest.

32-bit values are two registers, high word first (the fork lists them low word first, its read convention).

## Writable settings

Tested on the same EVO 10-5-H (19 Oct 2026): each one was set to a different harmless value, read back and put back.

| Control | Register(s) | Range | How the inverter accepts the write |
|---|---|---|---|
| Export Power Limit (number, W) | 46616–46617 | 0–15000 | Both registers together (function 16). 15000 = no limit; 0 = no export while Self Use carries on |
| Import Power Limit (number, W) | 46501–46502 | 0–15000 | **Only the whole 46501–46514 block** (function 16, 14 registers) |
| Peak Shaving Export Limit (number, W) | 46504–46505 | 0–15000 | Only the whole 46501–46514 block |
| Peak Shaving Threshold SoC (number, %) | 46503 | 0–100 | On its own (function 6) |
| MPPT Scan (select Off / On) | 49210 | 0 / 1 | On its own (function 6) |

46501–46502 and 46504–46505 refuse every smaller write (on their own, as a pair, 46501 ×3, ×5) with exception 2
(illegal address), but take the full 14-register block. The fork reads the block, changes only its own registers and
writes the block back, so the rest of it is left as it was.

The numbers are installer settings the inverter probably keeps in flash memory, so the fork treats them carefully:
it reads the registers live first and doesn't write if nothing would change, allows one change a minute per
setting (a quicker second change is refused with a message), and reads the value back afterwards (an error if it
didn't stick). Don't drive them from an automation that follows the house load; switch them at fixed times.

**Not writable:**
- Meter Compensation (49248) refuses every write shape tried (on its own, 49247 ×2, 49241 ×8 / ×13, 49229 ×25,
  49248 ×6). The readable block runs 49200–49253 and includes the work mode and the inverter clock, so a write of the
  whole block wasn't tried.
- Left read-only on purpose: Grid Standard Code, Rated / Max Active Power, Active Power Limit, Fixed Active Power
  Derate, Grid Point Power Limit (G99 / DNO settings), Meter 1 / 2 type (metering) and EPS Frequency. Changing these
  belongs to the installer.
