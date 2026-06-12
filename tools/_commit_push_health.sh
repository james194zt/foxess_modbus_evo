#!/bin/bash
set -e
cd ~/foxess_fork
git add \
  custom_components/foxess_modbus/entities/entity_descriptions.py \
  custom_components/foxess_modbus/entities/modbus_battery_health_sensors.py \
  tests/test_battery_health_sensors.py \
  docs/BMS_EXTENDED_REGISTERS.md \
  docs/PROBE_BMS_AH_REGISTERS.md \
  docs/PROBE_BMS_HEALTH_REGISTERS.md
git commit -F /mnt/c/Users/James/Documents/repo/foxess_modbus_EVO/tools/_commit_health_msg.txt
git push origin HEAD
