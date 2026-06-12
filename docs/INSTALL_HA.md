# Installing foxess_modbus on Home Assistant (EVO 10-H)

This repo ([james194zt/foxess_modbus_evo](https://github.com/james194zt/foxess_modbus_evo)) ships the **markybry** EVO register map as HA domain **`foxess_modbus`** (“FoxESS - Modbus”), plus EVO 10-H BMS, SOC/SoH, EPS, and load entities validated on a live unit.

**Upstream basis:** [markybry/foxess_modbus_EVO @ `feature/evo-10h-fixes`](https://github.com/markybry/foxess_modbus_EVO/tree/feature/evo-10h-fixes)

## Important differences from AdamNewberry’s fork

| | AdamNewberry `main` | markybry `feature/evo-10h-fixes` |
|---|---|---|
| HA domain | `foxess_modbus_evo` | `foxess_modbus` |
| Integration name in HA | FoxESS - Modbus (EVO) | FoxESS - Modbus |
| EVO charge periods | 41xxx (incorrect on many EVO units) | **48010–48023** |
| Work mode value 255 | Often missing | **Remote Control** |

Do **not** run both integrations against the same inverter.

After switching, entity IDs change (e.g. `sensor.foxess_modbus_evo_10_*` → `sensor.<your_device_name>_*`). Update `dashboard.yaml` and automations accordingly.

---

## Option A — Manual install (recommended for a specific branch)

1. Copy the integration into Home Assistant:

   ```text
   config/custom_components/foxess_modbus/
   ```

   From this repo, copy everything under:

   ```text
   custom_components/foxess_modbus/
   ```

2. Restart Home Assistant.

3. **Settings → Devices & services → Add integration** → **FoxESS - Modbus**.

4. Configure **AUX** connection (EVO 10-H is matched as `EVO \d+-([\d\.]+)-H` on AUX / holding registers).

To update later, replace that folder with a fresh copy of the branch and restart HA.

---

## Option B — HACS custom repository

HACS installs from the default branch unless you use a release. For `feature/evo-10h-fixes`:

1. HACS → **⋮** → **Custom repositories**
2. Repository: `https://github.com/james194zt/foxess_modbus_evo`
3. Category: **Integration**
4. Install **FoxESS - Modbus**

If HACS only offers `main`, use **Option A** or ask the maintainer to publish a release from `feature/evo-10h-fixes`.

---

## Option C — Develop on this machine

This workspace copy is already the branch zip:

```text
c:\Users\James\Documents\repo\foxess_modbus_EVO
```

Edit files under `custom_components/foxess_modbus/`, then copy that folder to your HA `config/custom_components/` and restart.

Run tests (from repo root, with Python 3):

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pytest tests
```

---

## Adding registers from the FoxESS Modbus protocol PDF

New sensors/controls are defined in Python, not YAML.

1. Find the **holding register** address in the protocol doc (EVO uses **holding** registers on **AUX**).
2. Add a description in `custom_components/foxess_modbus/entities/entity_descriptions.py` with `models=Inv.EVO` (or the appropriate model set).
3. If it is a charge-period or special type, check `charge_period_descriptions.py` and related factories.
4. Run `pytest tests` and update snapshots if prompted:  
   `pytest tests/__snapshots__/test_entity_descriptions/ -k EVO`
5. Redeploy to HA and reload the integration.

Example pattern:

```python
ModbusSensorDescription(
    key="my_new_sensor",
    name="My New Sensor",
    addresses=[ModbusAddressesSpec(holding=[39XXX], models=Inv.EVO)],
    scale=0.1,
    unit=UnitOfMeasurement.KILO_WATT,
),
```

Use the existing EVO entries in `entity_descriptions.py` (search for `Inv.EVO`) as templates.

---

## Write service (ad‑hoc Modbus)

**Developer tools → Services →** `foxess_modbus.write_register`  
Use this to probe addresses from the PDF before adding permanent entities.

---

## Your dashboard

`HADashboard/dashboard.yaml` references entities such as `sensor.evo_10_*` and `sensor.foxess_modbus_evo_10_*`. After reinstalling, open **Settings → Devices** and map old entity names to new ones (or rename the device during setup to keep `evo_10` prefixes).
