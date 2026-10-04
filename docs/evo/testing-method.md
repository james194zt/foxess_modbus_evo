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

## Value encodings seen on the EVO

| Kind | Encoding | Example |
|---|---|---|
| Time of day | `hour × 256 + minute` | 01:05 → `261`, 23:59 → `5947` |
| Two percentages in one register | `high × 256 + low` | max 85 / min 30 → `21790` |
| Firmware version | hex digits `major.minor` | `0x0121` → 1.21 |
| BCU version | high byte `.` low byte as 3 digits | `0x0104` → 1.004 |
| Protocol version | 2 registers → 4 bytes | `0x0105`, `0x0400` → V1.05.04.00 |
| Text | ASCII, 2 characters per register | `0x4556`, `0x4F20` → "EVO " |

## Sharing results

When you report a finding, include: model, protocol version (`39000`–`39001`), Master / Slave / Manager
firmware (`36001`–`36003`), the exact reads/writes, and the Fox app's view. Leave out serial numbers.
