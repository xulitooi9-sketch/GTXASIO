#!/usr/bin/env bash
# GTXASIO x64. Install only into the selected Wine prefix, verify PE architecture and report errors.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v wine >/dev/null; then
  echo 'ERROR: Wine no esta instalado.' >&2
  exit 1
fi
if [[ ! -s build/gtxasio.dll ]]; then
  echo 'ERROR: Falta build/gtxasio.dll. Primero ejecuta: bash scripts/build-cachyos.sh' >&2
  exit 1
fi
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine}"
if [[ ! -e "$WINEPREFIX/system.reg" ]]; then
  echo "ERROR: no existe el prefijo Wine $WINEPREFIX; revisa WINEPREFIX." >&2
  exit 1
fi
if command -v file >/dev/null && ! file build/gtxasio.dll | grep -Eq 'PE32\+.*x86-64|PE32\+.*x86_64'; then
  echo 'ERROR: la DLL no parece ser PE32+ para x86_64.' >&2
  file build/gtxasio.dll
  exit 1
fi
DEST="$WINEPREFIX/drive_c/GTXASIO"
mkdir -p "$DEST" logs
# Preserve the previous working version for quick recovery.
if [[ -f "$DEST/gtxasio.dll" && ! -f "$DEST/gtxasio.dll.backup" ]]; then
  cp -f "$DEST/gtxasio.dll" "$DEST/gtxasio.dll.backup"
fi
cp -f build/gtxasio.dll "$DEST/gtxasio.dll"
if [[ ! -f "$DEST/gtxasio.ini" ]]; then
  cat > "$DEST/gtxasio.ini" <<'EOF'
[Audio]
SampleRate=44100
BufferFrames=512
EOF
  echo 'Created GTXASIO settings: 44100 Hz / 512 frames (choose lower values in Show ASIO panel).'
fi
echo "Wine: $WINEPREFIX"
echo "DLL: $DEST/gtxasio.dll"
if command -v x86_64-w64-mingw32-objdump >/dev/null; then
  echo 'Dependencias Windows declaradas:'
  x86_64-w64-mingw32-objdump -p "$DEST/gtxasio.dll" | grep 'DLL Name:' || true
fi
# Explicitly choose 64-bit regsvr32 for the 64-bit ASIO COM server.
# Do not suppress loader errors: they can identify missing dependencies.
LOG="$PWD/logs/registro-wine.log"
echo "Registrando... diagnostico: $LOG"
if env WINEDEBUG=+loaddll,+module wine 'C:\windows\system32\regsvr32.exe' /s 'C:\GTXASIO\gtxasio.dll' >"$LOG" 2>&1; then
  if env WINEDEBUG=-all wine reg query 'HKLM\Software\ASIO\GTXASIO'; then
    echo 'OK: GTXASIO registrado. Reinicia FL Studio antes de probar.'
    exit 0
  else
    echo 'ERROR: Wine devolvio exito pero no aparece la clave ASIO.' >&2
  fi
else
  echo 'ERROR: Wine no ha conseguido registrar GTXASIO.' >&2
fi
echo "Revisa el log completo: $LOG" >&2
echo 'Ultimos errores relevantes del cargador:' >&2
grep -Ei 'err:|failed|not found|c000|import|wrong architecture|invalid image|module not found' "$LOG" | tail -n 35 >&2 || true
exit 1
