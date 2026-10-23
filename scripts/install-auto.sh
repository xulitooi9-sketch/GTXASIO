#!/usr/bin/env bash
# GTXASIO v0.1.7 — install ALSA engine + Wine DLL with on-demand systemd user socket.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HOME/.local/share/gtxasio"
UNITS="$HOME/.config/systemd/user"
# Locate a Wine prefix unless the caller supplied one explicitly.
if [[ -z "${WINEPREFIX:-}" ]]; then
  if [[ -f "$HOME/.wine-flstudio/system.reg" ]]; then
    WINEPREFIX="$HOME/.wine-flstudio"
  elif [[ -f "$HOME/.wine/system.reg" ]]; then
    WINEPREFIX="$HOME/.wine"
  else
    echo 'ERROR: Wine prefix not found. Set WINEPREFIX to the prefix where FL Studio is installed.' >&2
    exit 1
  fi
fi
export WINEPREFIX
# Resolve to an absolute path before persisting for systemd --user.
[[ "$WINEPREFIX" = /* ]] || { echo 'ERROR: WINEPREFIX must be an absolute path.' >&2; exit 1; }

if [[ ${EUID} -eq 0 ]]; then echo 'ERROR: Ejecuta sin sudo (es un servicio de usuario).' >&2; exit 1; fi
for cmd in systemctl make cc x86_64-w64-mingw32-g++ wine python3; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: falta $cmd; instala las herramientas necesarias." >&2; exit 1; }
done
if ! systemctl --user show-environment >/dev/null 2>&1; then
  echo 'ERROR: systemd --user no está disponible en esta sesión de escritorio.' >&2; exit 1
fi
if [[ ! -f "$WINEPREFIX/system.reg" ]]; then
  echo "ERROR: no existe el Wine prefix: $WINEPREFIX" >&2; exit 1
fi
# Refuse to take over the localhost port from a manually launched 0.1.6 engine.
if ! systemctl --user is-active --quiet gtxasio.socket; then
  if ! python3 - <<'PY'
import socket
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
try:
    s.bind(('127.0.0.1',37261))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
  then
    echo 'ERROR: Puerto 37261 ocupado. Cierra FL Studio y el motor anterior con Ctrl+C, luego repite.' >&2
    exit 1
  fi
fi

echo 'GTXASIO: compilando motor ALSA y DLL ASIO x64...'
(cd "$ROOT" && bash scripts/build-cachyos.sh)
mkdir -p "$DEST" "$DEST/build" "$UNITS" "$HOME/.config/gtxasio"
# The user service does not inherit environment variables from the install shell.
# Store the selected Wine prefix locally; no environment changes are needed afterwards.
printf 'WINEPREFIX=%q\n' "$WINEPREFIX" > "$HOME/.config/gtxasio/env"
chmod 600 "$HOME/.config/gtxasio/env"
# Preserve the previous GUI installation (if installed); update only runtime files.
cp -a "$ROOT/native" "$ROOT/common" "$ROOT/scripts" "$DEST/"
cp -f "$ROOT/Makefile" "$ROOT/README.md" "$ROOT/LICENSE" "$DEST/"
cp -f "$ROOT/build/gtxasio-engine" "$DEST/build/gtxasio-engine"
chmod +x "$DEST/build/gtxasio-engine" "$DEST/scripts/start-audio.sh"

# Wine registration before enabling on-demand socket; retain previous DLL backup.
echo 'GTXASIO: actualizando DLL Wine y preservando los ajustes existentes...'
(cd "$ROOT" && bash scripts/register-wine.sh)

cat > "$UNITS/gtxasio.socket" <<'UNIT'
[Unit]
Description=GTXASIO on-demand local audio socket

[Socket]
ListenDatagram=127.0.0.1:37261
Service=gtxasio.service

[Install]
WantedBy=sockets.target
UNIT
cat > "$UNITS/gtxasio.service" <<'UNIT'
[Unit]
Description=GTXASIO ALSA engine (started by FL Studio)

[Service]
Type=simple
ExecStart=%h/.local/share/gtxasio/scripts/start-audio.sh
Restart=no
TimeoutStopSec=5
UNIT

# When updating, terminate any previous socket-activated engine before reloading the unit.
systemctl --user stop gtxasio.service 2>/dev/null || true
systemctl --user daemon-reload
systemctl --user enable --now gtxasio.socket
if ! systemctl --user is-active --quiet gtxasio.socket; then
  echo 'ERROR: no se pudo activar gtxasio.socket. Usa systemctl --user status gtxasio.socket.' >&2
  exit 1
fi
printf '\n✓ GTXASIO instalado. Socket listo para iniciar solo al seleccionar GTXASIO en FL Studio.\n'
printf '  Configuracion: %s/drive_c/GTXASIO/gtxasio.ini\n' "$WINEPREFIX"
printf '  Diagnostico: journalctl --user -u gtxasio.service -n 60 --no-pager\n'
printf '  Recuerda: no abras manualmente el motor antiguo, pues el puerto ahora lo reserva systemd.\n'
