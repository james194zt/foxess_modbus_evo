# Fox Cloud Open API and the EVO

The Fox Cloud Open API (`https://www.foxesscloud.com/op/...`, signed with your API key) and the Fox app
show what the cloud believes, which is **not always what the inverter is doing**. Use it for things Modbus
can't do; don't use it to judge the inverter's state.

Status key: ✅ confirmed on hardware · ❓ not yet tested.

## Calls tested on an EVO 10-5-H

| Call | Body | Result | Status |
|---|---|---|---|
| `POST /op/v0/device/list` | `{"currentPage":1,"pageSize":50}` | device list with `deviceSN`, `moduleSN` | ✅ |
| `POST /op/v3/device/scheduler/get` | `{"deviceSN": …}` | scheduler groups (see [Mode Scheduler](mode-scheduler.md) for field mapping) and `maxGroupCount: 96` | ✅ but may be stale |
| `POST /op/v1/device/scheduler/get/flag` | `{"deviceSN": …}` | `{"enable": …, "support": true}` | ✅ but `enable` does not track `48000` |
| `POST /op/v0/device/batteryHeating/get` | `{"sn": …}` | warm-up enable, state, start/end temperature, 3 heating periods | ✅ |
| `POST /op/v0/device/batteryHeating/get` | `{"deviceSN": …}` | errno 40257 "Parameters do not meet expectations" | ✅ use `sn` |
| `POST /op/v0/device/setting/get` | `{"sn": …, "key": "WorkMode"}` | errno 42015 "does not currently support this feature" | ✅ |

Signing: header `signature = md5(path + "\r\n" + token + "\r\n" + timestamp)` with a literal backslash-r
backslash-n in the string, plus headers `token`, `timestamp` (ms) and `lang`. The API is rate-limited; keep
about a second between calls.

## The cloud doesn't track Modbus changes reliably

- A slot change written over Modbus once appeared in `scheduler/get` within ~2 minutes; another had not
  appeared after 20+ minutes while it was actively running.
- The Mode Scheduler switch (`48000`) was never reflected: after switching it off over Modbus the app kept
  showing Mode Scheduler, and after switching it on the app kept showing the plain work mode.
- The Fox website did pick up a `49203` change within a few minutes, even though the API can't read the work
  mode at all (`WorkMode` → 42015).

Saving in the Fox app while it shows a stale state writes that state back to the inverter — the app rewrites
scheduler groups 1–8 on every save.

## Battery warm-up

The EVO user manual (§2.6) describes battery heating: it is only available on heated battery versions, heats
cells between −20 °C and 0 °C up to 5 °C, and outside three configurable "full power" heating periods it uses
surplus PV only. Full heating is off by default. `batteryHeating/get` returns these settings
(`batteryWarmUpEnable`, `startTemperature`, `endTemperature`, `time1Enable` … `time3EndMinute`, and a state
string). ❓ `batteryHeating/set` has not been tested.
