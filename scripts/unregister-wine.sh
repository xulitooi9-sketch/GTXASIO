#!/usr/bin/env bash
set -euo pipefail
command -v wine >/dev/null || exit 1
WINEDEBUG=-all wine regsvr32 /u 'C:\GTXASIO\gtxasio.dll' || true
echo "Registro GTXASIO eliminado en prefijo: ${WINEPREFIX:-$HOME/.wine}"
