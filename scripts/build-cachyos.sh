#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v cc >/dev/null || { echo 'Falta gcc: sudo pacman -S --needed base-devel'; exit 1; }
command -v x86_64-w64-mingw32-g++ >/dev/null || { echo 'Falta cross-compiler: sudo pacman -S --needed mingw-w64-gcc'; exit 1; }
make -B
x86_64-w64-mingw32-g++ -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter -D_WIN64 \
  -shared windows/driver.cpp -o build/gtxasio.dll -lws2_32 -lole32 -luuid -ladvapi32 \
  -luser32 -lgdi32 -static -static-libgcc -static-libstdc++
x86_64-w64-mingw32-g++ -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter \
  windows/diag.cpp -o build/gtxasio-diag.exe -lole32 -luuid \
  -static -static-libgcc -static-libstdc++
echo 'OK: build/gtxasio-engine, build/gtxasio.dll y build/gtxasio-diag.exe (64-bit)' 
command -v file >/dev/null && file build/gtxasio.dll || true
if command -v x86_64-w64-mingw32-objdump >/dev/null; then
  echo 'Importaciones de GTXASIO:'
  x86_64-w64-mingw32-objdump -p build/gtxasio.dll | grep 'DLL Name:' || true
fi
