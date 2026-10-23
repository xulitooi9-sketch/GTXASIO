<div align="center">
  <img src="assets/gtxasio.png" alt="GTXASIO" width="96" height="96">

  # GTXASIO

  **Low-latency ASIO audio for FL Studio on Linux**

  [![CI](https://img.shields.io/badge/tests-16%20passed-2ea44f)](#build-and-test) [![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE) [![Status](https://img.shields.io/badge/status-alpha-orange)](#compatibility)
</div>

GTXASIO is an experimental 64-bit ASIO driver for FL Studio running through Wine. It provides audio output, microphone capture and adjustable buffer sizes using a native ALSA engine. The engine starts on demand through a per-user systemd socket; no terminal or separate audio application is needed for daily use.

## Features

- 64, 128, 256, 512 and 1024-sample ASIO buffers.
- 44.1 kHz and 48 kHz sample rates.
- Stereo playback and two ASIO input channels; mono microphone sources are duplicated to L/R.
- Built-in ASIO buffer panel in FL Studio.
- Automatic engine startup and shutdown through `systemd --user`.
- Runs as your user account, without a system-wide audio service.

## Compatibility

| Component | Current support |
| --- | --- |
| Distribution | CachyOS / Arch-based Linux; other distributions are not validated |
| Application | FL Studio 25 (64-bit) through Wine |
| Audio backend | ALSA `default` (may be provided by PipeWire's ALSA compatibility layer) |
| Session | `systemd --user` required |
| Architecture | x86_64 |

**Alpha software.** Tested in a single CachyOS + Wine + FL Studio environment, including playback and microphone capture at 64 samples. Results depend on your audio device, Wine version and host configuration. The displayed buffer length is not total round-trip latency. This is a userspace ASIO bridge, not a Linux kernel driver or an official Image-Line/Steinberg product.

## Install (CachyOS / Arch)

Install the required packages:

```bash
sudo pacman -S --needed base-devel mingw-w64-gcc wine python alsa-lib
```

Download the latest source package from **Releases**, extract it, and open a terminal in the extracted `GTXASIO` directory. To clone the source instead, copy the repository URL from GitHub's **Code** button and run `git clone` with that URL.

With FL Studio closed, install the driver using the **same Wine prefix where FL Studio is installed**:

```bash
WINEPREFIX="$HOME/.wine-flstudio" bash scripts/install-auto.sh
```

If FL Studio is installed under your default prefix instead:

```bash
WINEPREFIX="$HOME/.wine" bash scripts/install-auto.sh
```

The installer builds the x64 ASIO DLL and Linux engine, registers the driver in the selected Wine prefix, and installs a per-user socket-activated service. It requires no `sudo`. If `WINEPREFIX` is omitted, it looks for `~/.wine-flstudio` and then `~/.wine`.

### Use with FL Studio

1. Start FL Studio as usual, using the same Wine prefix.
2. Open **Options → Audio Settings** and select **GTXASIO**.
3. Choose **Show ASIO panel** to set the buffer (64–1024 samples) or sample rate.
4. Restart FL Studio after changing these settings.
5. In the Mixer, choose **Input 1** or **Input 2** to record your microphone.

GTXASIO starts automatically when the application requests audio and releases the audio device after it becomes idle. No separate start command is needed.

For a first test, use **256 or 512 samples** and headphones at a low volume. Decrease to 128 or 64 only if playback and recording stay clean and underruns do not continually increase.

## Troubleshooting

**GTXASIO is missing from FL Studio**

Make sure FL Studio and the installer are using the *same* `WINEPREFIX`. Close and reopen FL Studio after installation. The driver is 64-bit only.

**No audio / driver will not start**

```bash
systemctl --user status gtxasio.socket
systemctl --user status gtxasio.service
journalctl --user -u gtxasio.service -n 60 --no-pager
```

**Crackles, dropouts or distorted mic input**

Raise the buffer to 128, 256 or 512 samples, then restart FL Studio. Verify the mic and output chosen by the system's default ALSA device. Keep the system rate and GTXASIO rate compatible.

**Using another Wine prefix**

Close FL Studio, then rerun `scripts/install-auto.sh` with the desired `WINEPREFIX`. The selected prefix is saved for the user service. Avoid running two instances of the engine: both would try to use UDP port `37261`.

**Restore the previous DLL**

```bash
bash scripts/rollback-auto.sh
```

Restoration requires a backup from an earlier GTXASIO installation. If there is no backup, use the uninstall command instead.

## Uninstall

Close FL Studio, then run from the extracted source directory:

```bash
bash scripts/uninstall.sh
```

The uninstall script removes the ASIO registration, local engine and user service. It preserves your Wine prefix and the `gtxasio.ini` audio settings.

## Build and test

Build the Linux audio engine and run the tests:

```bash
make check
```

Build the Windows x64 ASIO DLL using MinGW-w64:

```bash
bash scripts/build-cachyos.sh
```

The automated tests use the ALSA `null` device and a local UDP socket; they do **not** measure actual soundcard latency or prove stability on every machine. Driver builds and user-level systemd activation must also be tested on real Linux/Wine installations.

## Report a bug

Open a GitHub issue with your Linux distribution, Wine and FL Studio versions, buffer size, sample rate, and the last 60 lines from:

```bash
journalctl --user -u gtxasio.service -n 60 --no-pager
```

Do not include personal paths, usernames or device serial numbers in public logs.

## Licenses

GTXASIO is released under the [MIT License](LICENSE). ASIO is a trademark of Steinberg Media Technologies GmbH; FL Studio is a product of Image-Line. GTXASIO is independent of both companies.

<details>
<summary>Instalación rápida en español</summary>

1. Instala Wine y las herramientas de compilación: `sudo pacman -S --needed base-devel mingw-w64-gcc wine python alsa-lib`.
2. Descarga el ZIP de **Releases**, extráelo y abre una terminal en la carpeta `GTXASIO`.
3. Cierra FL Studio y ejecuta `WINEPREFIX="$HOME/.wine-flstudio" bash scripts/install-auto.sh`. Si usas otro prefijo, cambia la ruta.
4. Abre FL Studio normalmente, entra a **Options → Audio Settings**, selecciona **GTXASIO** y configura el búfer en **Show ASIO panel**.
5. Si hay cortes o pitidos, sube a 128/256/512 samples y reinicia FL Studio.
6. Para desinstalar, cierra FL Studio y ejecuta `bash scripts/uninstall.sh` desde la carpeta del proyecto.

</details>
