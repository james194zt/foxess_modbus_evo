#!/usr/bin/env bash
# Sync Windows working copy -> WSL git clone -> commit -> push.
# Git repo: ~/foxess_fork  (NOT the broken .git under foxess_modbus_EVO on /mnt/c)
set -euo pipefail
SRC="/mnt/c/Users/James/Documents/repo/foxess_modbus_EVO"
DEST="$HOME/foxess_fork"
MSG_FILE="${1:-$SRC/tools/commit_msg_bms_extended.txt}"

if [[ ! -d "$DEST/.git" ]]; then
  git clone git@github.com:james194zt/foxess_modbus_evo.git "$DEST"
fi

rsync -a --delete \
  --exclude=.git --exclude=.venv --exclude=__pycache__ --exclude='*.pyc' \
  "$SRC/" "$DEST/"

cd "$DEST"
shift_files=("${@:2}")
if ((${#shift_files[@]})); then
  git add "${shift_files[@]}"
else
  git add -A
fi
git -c user.name=James -c user.email=james194zt@users.noreply.github.com \
  commit -F "$MSG_FILE"
git push origin main
git log -1 --oneline
git status -sb
