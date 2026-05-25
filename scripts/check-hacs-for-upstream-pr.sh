#!/usr/bin/env bash
# Run from repo root before pushing an upstream PR branch.
# Ensures hacs.json still matches nathanmarlor/foxess_modbus (zip_release policy).
set -euo pipefail

if ! git remote get-url upstream &>/dev/null; then
  echo "Add upstream: git remote add upstream https://github.com/nathanmarlor/foxess_modbus.git"
  exit 1
fi

git fetch upstream main --quiet

if git diff --quiet upstream/main -- hacs.json; then
  echo "OK: hacs.json matches upstream/main (zip_release unchanged)."
  exit 0
fi

echo "hacs.json differs from upstream/main:"
git diff upstream/main -- hacs.json
echo ""
echo "Restore upstream hacs.json for PR branches:"
echo "  git checkout upstream/main -- hacs.json"
exit 1
