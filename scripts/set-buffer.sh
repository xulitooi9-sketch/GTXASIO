#!/usr/bin/env bash
# CLI fallback if the Wine ASIO control panel does not show on a specific setup.
set -euo pipefail
if [[ -z "${WINEPREFIX:-}" && -f "$HOME/.config/gtxasio/env" ]]; then
  source "$HOME/.config/gtxasio/env"
fi
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-flstudio}"
settings="$WINEPREFIX/drive_c/GTXASIO/gtxasio.ini"
size="${1:-}"
case "$size" in
  64|128|256|512|1024) ;;
  *) echo 'Uso: bash scripts/set-buffer.sh 64|128|256|512|1024' >&2; exit 2;;
esac
if [[ ! -f "$settings" ]]; then
  echo "No existe $settings - registra GTXASIO v0.1.5 primero." >&2; exit 1
fi
if ! grep -q '^BufferFrames=' "$settings"; then
  echo 'Configuracion invalida: falta BufferFrames' >&2; exit 1
fi
sed -i -E "s/^BufferFrames=.*/BufferFrames=$size/" "$settings"
echo "GTXASIO: $size samples configurado. Reinicia FL Studio para aplicar el cambio."
