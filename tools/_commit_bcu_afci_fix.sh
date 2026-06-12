#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

export GIT_AUTHOR_NAME=james194zt
export GIT_AUTHOR_EMAIL=james194zt@users.noreply.github.com
export GIT_COMMITTER_NAME=james194zt
export GIT_COMMITTER_EMAIL=james194zt@users.noreply.github.com

git add \
  custom_components/foxess_modbus/entities/modbus_version_sensor.py \
  custom_components/foxess_modbus/entities/modbus_afci_version_sensor.py \
  custom_components/foxess_modbus/entities/entity_descriptions.py \
  docs/PROBE_AFCI_VERSION.md \
  tests/test_modbus_version_sensor.py \
  tests/test_modbus_afci_version_sensor.py \
  "tests/__snapshots__/test_entity_descriptions/test_entities[EVO-AUX-latest].json"

git commit -m "Fix EVO BCU sub-register merge and tighten AFCI probe.

Pack 1 reads holding 37034 when 37033 minor is zero (1.000+4 → 1.004).
AFCI probe skips implausible registers (e.g. 0x3130 → 31.30)."

git push origin main
