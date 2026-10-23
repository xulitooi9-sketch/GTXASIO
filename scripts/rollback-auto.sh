#!/usr/bin/env bash
# Restore the previous working ASIO DLL and disable automatic socket activation.
set -euo pipefail
if [[ -z "${WINEPREFIX:-}" && -f "$HOME/.config/gtxasio/env" ]]; then
  source "$HOME/.config/gtxasio/env"
fi
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-flstudio}"
DLL="$WINEPREFIX/drive_c/GTXASIO/gtxasio.dll"
BACKUP="$DLL.backup"
if [[ ! -f "$BACKUP" ]]; then echo "ERROR: no existe backup: $BACKUP" >&2; exit 1; fi
systemctl --user disable --now gtxasio.socket || true
systemctl --user stop gtxasio.service 2>/dev/null || true
cp -f "$BACKUP" "$DLL"
env WINEDEBUG=-all wine 'C:\windows\system32\regsvr32.exe' /s 'C:\GTXASIO\gtxasio.dll'
echo '✓ DLL anterior restaurada. El socket automatico está desactivado.'
