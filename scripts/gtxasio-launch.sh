#!/usr/bin/env bash
# No terminal window; KDE menu launches the graphical application.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -z "${WINEPREFIX:-}" && -f "$HOME/.config/gtxasio/env" ]]; then
  source "$HOME/.config/gtxasio/env"
fi
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-flstudio}"
cd "$ROOT"
exec python3 "$ROOT/app/gtxasio_gui.py" "$@"
