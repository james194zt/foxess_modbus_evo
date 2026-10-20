# How these findings were made — and how to add your own

FoxESS has not published a Modbus document for the EVO, so everything here comes from testing a real
inverter. This page describes the method, so others can check these results on their own model / firmware
and extend them.

## Tools

With the foxess_modbus integration in Home Assistant, **Developer Tools → Actions** (YAML mode):

```yaml
action: foxess_modbus.read_registers
data:
  inverter: <your inverter's friendly name>
  start_address: 48000
  count: 20
  type: holding
```

```yaml
action: foxess_modbus.write_registers
data:
  inverter: <your inverter's friendly name>
  start_address: 48000
  values: "1,0,0,0,0,0,0,0,0,0"
```

When an action fails with "Unknown error", the real reason is in **Settings → System → Logs** (search
`Failed to write registers`). The Modbus exception code tells you what happened:

| Code | Name | Meaning in practice |
|---|---|---|
| 2 | `IllegalAddress` | the address — or the **shape** of the write, e.g. part of a block — isn't accepted |
| 3 | `IllegalValue` | the write is allowed, but this **value** isn't (e.g. Max SoC below Max SoC From Grid) |

(The first number in `Exception Response(134, 6, …)` is the function code + 128: 134 = write single
register, 144 = write multiple registers.)

If your adapter is Modbus TCP, a small script that talks to it directly (alongside Home Assistant) shows
the exception code straight away. Keep each connection short, and match replies by transaction ID.

## Safety rules

1. **Read before you write**, and note the original values so you can restore them.
2. Pause anything else that writes to the inverter (automations, other integrations) while testing.
3. Make test changes **harmless**: write to a disabled or unused slot, or use low powers (e.g. 1000 W) and
   cut-offs only 1–2 % above the current SoC.
4. **Write whole blocks** in the `48000+` area — never part of a 10-register block.
5. **Restore** afterwards and read back to confirm.

## Mapping a feature to registers: change one thing, compare

1. Set something recognisable in the Fox app — use unusual values (e.g. 01:05–02:35, cut-off 95 %, 11000 W)
   so each register can only match one field.
2. Read the candidate range. If you have a Fox Cloud API key, capture the cloud's view at the same moment —
   it labels the fields.
3. Change **one** setting in the app, read again, and compare. Whatever changed belongs to that setting.

## Searching for an unknown register

- Read in **small chunks** (10 registers) and split any chunk that fails down to single registers: a read
  that includes even one refused address fails as a whole, so large reads can make whole ranges look
  unreadable.
- Decode every value three ways: number, hex (versions often look like `0x0121` = 1.21), and ASCII (model
  names, serials and some versions are text, 2 characters per register).
- Take a full snapshot of the readable registers, change something, take another, and compare the two to
  find what moved.
- Don't stop at `49999`. Battery warm-up turned out to be at `53400`, above every documented range. Holding
  registers `50000`–`65535` are mostly unreadable on the EVO, so this sweep is quick.
- Input registers (FC04) `30000`–`49999` mirror the holding registers on the EVO, so a holding sweep covers them.
- **Writes have shapes too.** Some registers only accept a write as part of a particular block (`48000`–`48009`,
  each scheduler group, `46501`–`46514`), and refuse the same values written alone with exception 2. Before
  deciding a register is read-only, write its **current** value back in a few shapes (alone, with its
  neighbours, from the start of the readable block). Never include registers like the clock (`49222`+) or the
  work mode in a test block: writing back an old copy of a moving value changes it.

## Value encodings seen on the EVO

| Kind | Encoding | Example |
|---|---|---|
| Time of day | `hour × 256 + minute` | 01:05 → `261`, 23:59 → `5947` |
| Two percentages in one register | `high × 256 + low` | max 85 / min 30 → `21790` |
| Firmware version | hex digits `major.minor` | `0x0121` → 1.21 |
| BCU version | high byte `.` low byte as 3 digits | `0x0104` → 1.004 |
| Protocol version | 2 registers → 4 bytes | `0x0105`, `0x0400` → V1.05.04.00 |
| Text | ASCII, 2 characters per register | `0x4556`, `0x4F20` → "EVO " |

## Open questions

Help with any of these is welcome:

- **Unidentified readable blocks:** holding `32001`–`32020`, `50021`–`50045`, `55000`–`55020` and `60003`–`60005`.
  Try the change-one-thing method with a harmless setting from the inverter's own menu or the app.
- **Readable but unconfirmed** (0 / off on the test unit): `39057`–`39060` (both read 3680; probably apparent and
  reactive power maximums), power factor / reactive power `49005`, `49006`, `49010`, balance load `46614`–`46615`,
  idle mode `49229`–`49230`, buzzer `49209`, screen brightness `49221`, relays `49211`–`49212`, ripple control
  `49241`–`49246`.
- **AFCI version:** shown in the Fox app, not found in any register ([details](identity-and-versions.md)).
- **Battery warm-up `53412`–`53414`** (a hidden fourth period?) and whether any register shows warm-up actually
  running. Worth reading while the battery is warming in cold weather ([details](battery-warm-up.md)).
- **Export Power Limit = 0 under solar:** the write works; whether export really drops to ~0 hasn't been watched.
- **Mode Scheduler:** offset +7, the +8 flag bits, the codes for Fox Cloud's `ForceCharge(BAT)` /
  `ForceDischarge(BAT)`, slot modes 4 / 5, and the protocol document's slot SoC rules
  ([details](mode-scheduler.md)).
- **Battery max charge / discharge current** (`46607` / `46608`): readable, writes not tested on the EVO.
- **`37065`–`37068`** read 255 each, one per battery slot.

## Sharing results

When you report a finding, include: model, protocol version (`39000`–`39001`), Master / Slave / Manager
firmware (`36001`–`36003`), the exact reads/writes, and the Fox app's view. Leave out serial numbers.
