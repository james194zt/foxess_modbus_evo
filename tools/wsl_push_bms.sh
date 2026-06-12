#!/usr/bin/env bash
set -euo pipefail
SRC="/mnt/c/Users/James/Documents/repo/foxess_modbus_EVO"
DEST="$HOME/foxess_fork"
rsync -a --delete --exclude=.git --exclude=.venv --exclude=__pycache__ "$SRC/" "$DEST/"
cd "$DEST"
git add custom_components/foxess_modbus/entities/entity_descriptions.py docs/BMS_EXTENDED_REGISTERS.md
git -c user.name=James -c user.email=james194zt@users.noreply.github.com commit -F "$SRC/tools/commit_msg_bms_extended.txt"
git push origin main
git log -1 --oneline
git status -sb
