# EVO identity, firmware and battery version registers

Status key: ✅ confirmed on hardware (matched against the Fox app's device screen) · ⚠️ differs from the
FoxESS protocol document · ❓ not yet tested.

| Register(s) | Meaning | Encoding | Example (Fox app shows) | Status |
|---|---|---|---|---|
| `30000`–`30015` | Model name | ASCII, 2 chars per register | `EVO 10-5-H` | ✅ |
| `30016`–`30031` | Inverter serial | ASCII | the PCS SN | ✅ |
| `30032`–`30047` | Manufacturer ID | ASCII | (all zero on the test unit) | ❓ |
| `39000`–`39001` | Modbus protocol version | 4 bytes → `Va.bb.cc.dd` | `0x0105`,`0x0400` → **V1.05.04.00** | ✅ |
| `39002`–`39017` | Model name (copy) | ASCII | `EVO 10-5-H` | ✅ |
| `39018`–`39033` | Inverter serial (copy) | ASCII | | ✅ |
| `36001` | Master firmware | high byte `.` low byte, hex digits | `0x0121` → **1.21** | ✅ |
| `36002` | Slave firmware | as above | `0x0101` → **1.01** | ✅ |
| `36003` | Manager firmware | as above | `0x0120` → **1.20** | ✅ |
| `36100`+, `36200`+ | Meter 1 / Meter 2 SN, manufacturer, type, version | ASCII | (all zero on the test unit) | ❓ per FoxESS document |
| `37002` | BMS connection (0 offline, 1 online) | | `1` | ✅ |
| `37003` | **BMS master (BCU) version** | high byte `.` low byte as 3 digits | `0x0104` → **1.004** ("Version_BCU") | ✅ |
| `37004` | BMS master type | number | `113` | ❓ meaning of the value |
| `37005`–`37020` | Battery (BMS master) serial | ASCII | the Battery SN | ✅ |
| `37032` | Number of BMS slaves (packs) | number | `1` | ✅ |
| `37033`+ | "BMS slave *n* version" per the FoxESS document | — | `0x1000`, `0x2000`, `0x3000`, `0x4000` | ⚠️ these are slot numbers, not versions — reported for 4 slots even with 1 pack |
| `37097` + 16 × (*n* − 1) | BMS slave *n* serial | ASCII | the Battery SN, repeated per slot | ✅ |
| `37065`–`37068` | unknown, one per slot | | `255` each | ❓ |

The Fox app's "Version_Master / Slave / Manager" and "Version_BCU" map as above. Integrations showing
"BMS pack *n* version" from `37033`+ will show meaningless values on the EVO.

## AFCI version — not in the holding registers

The Fox app shows "Version_AFCI" (0.37 on the test unit), but **no holding register from 30000 to 49999
holds it** — every readable register in that range was read and checked for `0x0037`, `37` and ASCII "0.37".
The FoxESS document has no AFCI version register either (only a "DC arc fault" alarm). It is most likely
reported only to the Fox datalogger / cloud. Input registers were not searched.

## Readable ranges

Some ranges refuse reads entirely on the EVO (e.g. `36004`–`36059`, `37637`–`37699`), and any read that
includes one refused address fails as a whole. Read in small chunks and narrow down on failures — see
[testing method](testing-method.md).
