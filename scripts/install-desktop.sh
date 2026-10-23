#!/usr/bin/env bash
# Per-user installation for CachyOS/KDE. Does NOT replace or register the Wine ASIO DLL.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$HOME/.local/share/gtxasio"
APPS="$HOME/.local/share/applications"
ICONDIR="$HOME/.local/share/icons/hicolor/128x128/apps"
SVGDIR="$HOME/.local/share/icons/hicolor/scalable/apps"

if ! python3 -c 'import PyQt6.QtWidgets' >/dev/null 2>&1; then
  echo 'ERROR: instala primero la interfaz Qt6:' >&2
  echo '  sudo pacman -S --needed python-pyqt6' >&2
  exit 1
fi
if ! command -v make >/dev/null || ! command -v cc >/dev/null; then
  echo 'ERROR: necesitas base-devel: sudo pacman -S --needed base-devel' >&2
  exit 1
fi
mkdir -p "$DEST" "$APPS" "$ICONDIR" "$SVGDIR"
# Copy the new control center + unchanged verified audio source. Existing Wine DLL stays installed.
cp -a "$ROOT/app" "$ROOT/assets" "$ROOT/native" "$ROOT/common" "$ROOT/scripts" "$DEST/"
cp -a "$ROOT/Makefile" "$ROOT/README.md" "$ROOT/LICENSE" "$DEST/"
make -C "$DEST" -B all
chmod +x "$DEST/scripts/gtxasio-launch.sh"
cp "$DEST/assets/gtxasio.png" "$ICONDIR/gtxasio.png"
cp "$DEST/assets/gtxasio.svg" "$SVGDIR/gtxasio.svg"
# desktop-file quoting is required for spaces and other special characters in home directories.
DESKTOP_EXEC="\"${DEST//\\/\\\\}/scripts/gtxasio-launch.sh\""
cat > "$APPS/gtxasio.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=GTXASIO
GenericName=ASIO Audio Control Center
Comment=Gestiona audio, micrófono y latencia de FL Studio en Wine
Exec=$DESKTOP_EXEC
Icon=gtxasio
Terminal=false
StartupNotify=true
Categories=AudioVideo;Audio;Settings;
Keywords=ASIO;FL Studio;audio;micrófono;latencia;
EOF
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS" >/dev/null 2>&1 || true
fi
printf '\n✓ GTXASIO Control Center instalado.\n'
printf '  Menú de KDE → busca "GTXASIO".\n'
printf '  Para abrirlo ahora (una sola vez): %s\n' "$DEST/scripts/gtxasio-launch.sh"
printf '  La DLL ASIO en Wine no se modificó.\n'
