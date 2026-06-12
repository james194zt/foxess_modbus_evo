#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

export GIT_AUTHOR_NAME=james194zt
export GIT_AUTHOR_EMAIL=james194zt@users.noreply.github.com
export GIT_COMMITTER_NAME=james194zt
export GIT_COMMITTER_EMAIL=james194zt@users.noreply.github.com

git add \
  custom_components/foxess_modbus/entities/modbus_afci_version_sensor.py \
  custom_components/foxess_modbus/entities/entity_descriptions.py \
  docs/PROBE_AFCI_VERSION.md \
  tests/test_modbus_afci_version_sensor.py \
  "tests/__snapshots__/test_entity_descriptions/test_entities[EVO-AUX-latest].json"

git commit -m "Probe EVO AFCI version register instead of fixed holding 36004.

The fixed 36004 address caused IllegalAddress repairs on many units; probe
likely holding registers on connect and only poll the address that responds."

git push origin main
