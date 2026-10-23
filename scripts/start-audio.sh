#!/usr/bin/env bash
# Start the Linux engine with the EXACT buffer and rate stored by GTXASIO panel.
set -euo pipefail
cd "$(dirname "$0")/.."
# The socket-activated service is launched outside the installer's shell.
if [[ -z "${WINEPREFIX:-}" && -f "$HOME/.config/gtxasio/env" ]]; then
  # File created by scripts/install-auto.sh with shell-escaped values (mode 0600).
  source "$HOME/.config/gtxasio/env"
fi
export WINEPREFIX="${WINEPREFIX:-$HOME/.wine-flstudio}"
CFG="$WINEPREFIX/drive_c/GTXASIO/gtxasio.ini"
if [[ ! -r "$CFG" ]]; then
  echo "Missing $CFG; run registration first: env WINEPREFIX=... bash scripts/register-wine.sh" >&2
  exit 1
fi
getval() {
  awk -F= -v needle="$1" '
    { sub(/\r$/, "", $0); if ($1 == needle) {gsub(/[[:space:]]/,"",$2); answer=$2} }
    END {print answer}' "$CFG"
}
rate="$(getval SampleRate)"; frames="$(getval BufferFrames)"
case "$rate" in 44100|48000) ;; *) echo "Invalid SampleRate: $rate" >&2; exit 1;; esac
case "$frames" in 64|128|256|512|1024) ;; *) echo "Invalid BufferFrames: $frames" >&2; exit 1;; esac
[[ -x build/gtxasio-engine ]] || { echo 'Build engine first: make' >&2; exit 1; }
echo "GTXASIO - Starting ${rate} Hz / ${frames} frames (configure with Show ASIO panel)"
echo "Microphone/output: ALSA default; optional additional --input/--output arguments are forwarded"
exec ./build/gtxasio-engine --rate "$rate" --buffer "$frames" "$@"
