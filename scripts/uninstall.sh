#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -eq 0 ]]; then echo 'Run without sudo.' >&2; exit 1; fi
CONFIG="$HOME/.config/gtxasio/env"
if [[ -z "${WINEPREFIX:-}" && -f "$CONFIG" ]]; then
  source "$CONFIG"
fi
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-flstudio}"
systemctl --user disable --now gtxasio.socket 2>/dev/null || true
systemctl --user stop gtxasio.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/gtxasio.socket" "$HOME/.config/systemd/user/gtxasio.service"
systemctl --user daemon-reload
if [[ -f "$WINEPREFIX/drive_c/GTXASIO/gtxasio.dll" ]] && command -v wine >/dev/null 2>&1; then
  env WINEPREFIX="$WINEPREFIX" WINEDEBUG=-all wine 'C:\windows\system32\regsvr32.exe' /s /u 'C:\GTXASIO\gtxasio.dll' || true
fi
rm -f "$WINEPREFIX/drive_c/GTXASIO/gtxasio.dll"
rm -rf "$HOME/.local/share/gtxasio"
rm -f "$HOME/.local/share/applications/gtxasio.desktop"
rm -f "$HOME/.local/share/icons/hicolor/128x128/apps/gtxasio.png"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/gtxasio.svg"
rm -f "$CONFIG"
echo 'GTXASIO uninstalled. Your Wine prefix and audio settings were preserved.'
