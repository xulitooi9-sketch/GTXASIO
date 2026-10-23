#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -s build/gtxasio-diag.exe ]]; then
  echo 'ERROR: Compila primero con bash scripts/build-cachyos.sh' >&2
  exit 1
fi
if [[ -z "${WINEPREFIX:-}" && -f "$HOME/.config/gtxasio/env" ]]; then
  source "$HOME/.config/gtxasio/env"
fi
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-flstudio}"
echo "GTXASIO diagnosticando Wine: $WINEPREFIX"
# This calls the installed COM driver but does not connect to ALSA or open audio.
env WINEDEBUG=-all wine "$PWD/build/gtxasio-diag.exe"
