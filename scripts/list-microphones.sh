#!/usr/bin/env bash
# Lists Linux microphone sources and ALSA PCM names. No system changes.
set -u
printf '\n== Microfonos disponibles en PipeWire / WirePlumber ==\n'
if command -v wpctl >/dev/null 2>&1; then
  wpctl status || true
elif command -v pactl >/dev/null 2>&1; then
  pactl list short sources || true
else
  echo 'Ni wpctl ni pactl disponibles; usa la configuracion de audio de KDE.'
fi
printf '\n== Entradas ALSA (pueden usarse con --input) ==\n'
if command -v arecord >/dev/null 2>&1; then
  arecord -L || true
else
  echo 'Falta arecord; instala alsa-utils (sudo pacman -S --needed alsa-utils).'
fi
printf '\nRECOMENDADO: selecciona tu microfono predeterminado en KDE Audio,\n'
printf 'y arranca el motor con --input default. Si no funciona,\n'
printf 'usa uno de los nombres ALSA listados con --input "nombre".\n'
