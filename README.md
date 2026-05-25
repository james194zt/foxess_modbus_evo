# FoxESS - Modbus

[![GitHub Release][releases-shield]][releases]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]
[![Community Forum][forum-shield]][forum]

\*\* **This project is not endorsed by, directly affiliated with, maintained, authorized, or sponsored by FoxESS** \*\*

## Introduction

A Home Assistant custom component which communicates with FoxESS inverters locally via Modbus (no cloud).

**This fork** ([james194zt/foxess_modbus_evo](https://github.com/james194zt/foxess_modbus_evo)) adds **FoxESS EVO 10-H** support on the markybry register map: charge periods **48010–48023**, BMS pack sensors (**37609–37632**), corrected SOC/SoH, EPS/load power, and computed remaining kWh. See [docs/INSTALL_HA.md](docs/INSTALL_HA.md) for Raspberry Pi / HA OS install steps.

HA domain: **`foxess_modbus`** — integration name **FoxESS - Modbus** (not `foxess_modbus_evo`).

Supported models include:

- FoxESS **EVO 10-H** (this fork)
- FoxESS H1 (including AC1, AIO-H1 and G2)
- FoxESS H3 (including AC3 and AIO-H3)
- FoxESS H3 PRO / SMART
- FoxESS KH
- Kuara H3, Sonnenkraft SK-HWR, STAR, Solavita SP, a-TroniX AX, Enpal, 1KOMMA5°

You will need a direct connection to your inverter.
In most cases, this means buying a modbus to ethernet/USB adapter and wiring this to a port on your inverter.
See the documentation for details.

**[See the wiki](https://github.com/nathanmarlor/foxess_modbus/wiki) for how-to articles and FAQs.**

## Installation

### HACS (recommended on Home Assistant OS / Raspberry Pi)

This fork installs from **source** (no `zip_release`) so commit-based testing works without a GitHub release zip. Upstream uses tagged zip releases instead — see [docs/FORK_HACS.md](docs/FORK_HACS.md). Contributing EVO changes back upstream: [docs/UPSTREAM_PR.md](docs/UPSTREAM_PR.md).

1. HACS → **⋮** → **Custom repositories**
2. URL: `https://github.com/james194zt/foxess_modbus_evo` — category **Integration**
3. Install **FoxESS - Modbus**, restart Home Assistant
4. **Settings → Devices & services → Add integration → FoxESS - Modbus**
5. EVO 10-H: connection **AUX**, holding registers

Manual copy: see [docs/INSTALL_HA.md](docs/INSTALL_HA.md).

### Upstream HACS

For non-EVO inverters, the original [nathanmarlor/foxess_modbus](https://github.com/nathanmarlor/foxess_modbus) HACS entry may suffice.

## Usage

1. Navigate to Settings -> Devices & Services to find:

![Usage](images/usage.png)

2. Select '1 device' to find all Modbus readings:

![Example](images/example.png)

## Charge Periods

If your inverter supports setting charge periods, you can use install the [Charge Periods lovelace card](https://github.com/nathanmarlor/foxess_modbus_charge_period_card):

![Charge Periods](images/charge-periods.png)

## Services

### Write Service

A service to write any modbus address is available, similar to the native Home Assistant service. To use a service, navigate to Developer Tools -> Services and select it from the drop-down.

![Service](images/svc-write.png)

### Update Charge Periods

Updates one of the two charge periods (if supported by your inverter).

![Service](images/svc-charge-1.png)

### Update All Charge Periods

Sets all charge periods in one service call. The service "Update Charge Period" is easier for end-users to use.

![Service](images/svc-charge-2.png)

---

[buymecoffee]: https://www.buymeacoffee.com/nathanmarlor
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
[hacs]: https://hacs.xyz
[my-hacs]: https://my.home-assistant.io/redirect/hacs_repository/?owner=nathanmarlor&repository=foxess_modbus&category=integration
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[releases-shield]: https://img.shields.io/github/release/nathanmarlor/foxess_modbus.svg?style=for-the-badge
[releases]: https://github.com/nathanmarlor/foxess_modbus/releases
