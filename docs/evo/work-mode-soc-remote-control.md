# EVO work mode, SoC limits and Remote Control

Status key: ✅ confirmed on hardware · ⚠️ differs from the FoxESS protocol document · ❓ not yet tested.

## Work mode (49203)

| Value | Mode | Status |
|---|---|---|
| 1 | Self Use | ✅ |
| 2 | Feed-in First | ✅ |
| 3 | Back-up | ✅ |
| 4 | Peak Shaving | ❓ |
| 255 | under external Remote Control (read-only state) | ✅ ⚠️ not in the FoxESS document |

- ✅ **Writes use the same 1-based codes as reads.** Writing `2` reads back `2` and the Fox app shows Feed-in
  First. (Some integrations wrote 0-based values, e.g. `1` for Feed-in — which sets Self Use and looks like
  the mode "reverting".)
- ✅ **While the Mode Scheduler is on (`48000 = 1`), `49203` is ignored** — the active slot decides. Choosing
  a plain mode in the Fox app sets `49203` and switches the scheduler off; choosing Mode Scheduler only sets
  `48000`, so `49203` keeps the last plain mode and can look misleading. See
  [Mode Scheduler](mode-scheduler.md).

## SoC limits and nearby settings (46607–46620)

Values below were read from the test inverter with the scheduler off.

| Register | Meaning | Read | Status |
|---|---|---|---|
| `46607` | Battery max charge current (A ×10) | — | ❓ per FoxESS document |
| `46608` | Battery max discharge current (A ×10) | — | ❓ per FoxESS document |
| `46609` | Minimum SoC (off-grid) % | 10 | ✅ writable (FC6) |
| `46610` | System Max SoC % | 100 | ✅ writable (FC6) — but see the rule below |
| `46611` | Minimum SoC on grid % | 10 | ✅ |
| `46612` | EPS frequency (1 = 50 Hz, 2 = 60 Hz) | 1 | value consistent with the document |
| `46613` | EPS output (0 disable, 2 EPS, 3 UPS) | 3 | value consistent with the document |
| `46614` | Balance load (0/1) | 0 | ❓ |
| `46615` | Balance logic first (0/1) | 0 | ❓ |
| `46616`–`46617` | Export power limit, W (I32) | 0, 15000 → 15000 W | value consistent with the document |
| `46618` | Import current limit (A ×10) | 320 → 32.0 A | value consistent with the document |
| `46619` | Export current limit (A ×10) | 630 → 63.0 A | value consistent with the document |
| `46620` | **Max SoC From Grid** % | 100 | ✅ ⚠️ **not in the FoxESS document** |

### The Max SoC rule

✅ **System Max SoC (`46610`) cannot be set below Max SoC From Grid (`46620`).** Writing `99` to `46610`
while `46620` was `100` failed with `IllegalValue` (exception 3) — not `IllegalAddress` — even though the
battery was at 55 %. This looks like "max SoC is read-only on the EVO", which is what several integrations
concluded.

- To **lower**: write `46620` first, then `46610`.
- To **raise**: write `46610` first, then `46620`.

Both were accepted as single-register (FC6) writes.

✅ **System Max SoC (`46610`) also can't be set below the current battery level.** With the battery at 26 %,
writing `15` to `46610` failed with `IllegalValue`, while writing `15` to `46620` was accepted. So when lowering
Max SoC, check the battery level first, or put `46620` back if the `46610` write is refused, otherwise grid
charging is left capped at the lower value.

✅ SoC limit writes are accepted **while Remote Control is active**, and Remote Control keeps running: with a
Remote Control Force Charge in progress, writing `46609`, `46611` and `46610` (unchanged values) was accepted
and the charge carried on. There's no need to switch Remote Control off first.

✅ While the Mode Scheduler is on, the active slot's own SoC limits (+4) apply, so changing `46609`–`46611`
has no visible effect until the scheduler is switched off.

## Remote Control (46001…)

Remote Control is the "do it now" command channel (force charge / discharge at a set power, with a
watchdog timeout). The foxess_modbus integration exposes it as a Remote Control select plus Force Charge /
Discharge Power settings.

- ✅ A Remote Control Force Charge or Force Discharge **overrides a running scheduler slot** immediately;
  disabling Remote Control lets the slot resume.
- ✅ Its power comes from the Remote Control power setting (the inverter's full rating by default — 3.88 kW was
  observed on an EVO 10), not from the slot's `fdPwr`.
- ✅ While active, `49203` has been seen reading `255` in one test, and `3` (Back-up, the integration's fallback
  below) in another (Force Charge at night). Don't rely on either value to detect Remote Control.
- ✅ **foxess_modbus behaviour to be aware of:** while Remote Control is active, the integration writes a
  fallback work mode to `49203` (Force Discharge → Feed-in First, Force Charge → Back-up) so the inverter
  does something sensible if Home Assistant disconnects. Upstream doesn't restore the previous work mode when
  Remote Control is disabled; this fork does (tested: Self Use → Back-up during Force Charge → Self Use).
- ✅ In foxess_modbus, **Force Charge Power limits grid import, not the battery's charge rate**. With solar
  available, the battery charges at that import plus whatever PV adds: set to 1 kW in the morning, the battery
  charged at about 3.7 kW (1 kW from the grid plus solar).
