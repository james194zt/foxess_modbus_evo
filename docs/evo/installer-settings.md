# EVO installer settings (read-only)

Settings an installer sets on the inverter itself (its on-board menus) that the Fox app doesn't show. The fork
exposes them as read-only sensors; nothing here is ever written. Read on an EVO 10-5-H (5 kW model) set up for a
UK G99 connection limited to 3.68 kW.

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

39057–39060 also read 3680 on this inverter (probably apparent and reactive power maximums; not mapped).
Max charge / discharge current (46607 / 46608, 50.0 A here) were already mapped.

Evidence the AC cap is real: on a clear day PV peaked at 4.48 kW while the inverter's AC output never went above
3.688 kW, sitting at 3.67 kW for long stretches; the battery took the rest.

32-bit values are two registers, high word first (the fork lists them low word first, its read convention).
