#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

export GIT_AUTHOR_NAME=james194zt
export GIT_AUTHOR_EMAIL=james194zt@users.noreply.github.com
export GIT_COMMITTER_NAME=james194zt
export GIT_COMMITTER_EMAIL=james194zt@users.noreply.github.com

git add -A
git commit -m "Remove AFCI probe and BCU pack-token version decoding.

Drop afci_version entity and revert BMS pack versions to standard hex format."

git push origin main
