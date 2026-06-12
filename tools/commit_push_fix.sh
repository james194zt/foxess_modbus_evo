#!/bin/bash
set -euo pipefail
cd ~/foxess_fork
git add custom_components/foxess_modbus/entities/modbus_battery_ah_remaining_sensor.py
git -c user.name=James -c user.email=james194zt@users.noreply.github.com commit -m "$(cat <<'EOF'
Fix integration load failure on Ah remaining sensor.

Add missing EntityFactory.serialize implementation so entity_descriptions loads at import time.
EOF
)"
git push origin HEAD
git log -1 --oneline
git status --short
