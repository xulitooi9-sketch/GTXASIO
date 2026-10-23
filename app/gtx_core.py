"""GTXASIO desktop controller's backend. No Qt dependency for testability."""
from __future__ import annotations

import configparser
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile

BUFFER_CHOICES = (64, 128, 256, 512, 1024)
RATE_CHOICES = (44100, 48000)
ENGINE_PORT = 37261
DEFAULT_PREFIX = Path.home() / '.wine-flstudio'
CONFIG_NAME = 'gtxasio.ini'


def wine_prefix() -> Path:
    return Path(os.environ.get('WINEPREFIX', str(DEFAULT_PREFIX))).expanduser().resolve()


def driver_config_path(prefix: Path | None = None) -> Path:
    return (prefix or wine_prefix()) / 'drive_c' / 'GTXASIO' / CONFIG_NAME


def gui_prefs_path() -> Path:
    return Path.home() / '.config' / 'gtxasio' / 'desktop.json'


def read_audio_settings(path: Path) -> tuple[int, int]:
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    if path.exists():
        cfg.read(path, encoding='utf-8')
    rate = cfg.getint('Audio', 'SampleRate', fallback=44100)
    buffer = cfg.getint('Audio', 'BufferFrames', fallback=512)
    if rate not in RATE_CHOICES: rate = 44100
    if buffer not in BUFFER_CHOICES: buffer = 512
    return rate, buffer


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def write_audio_settings(path: Path, rate: int, frames: int) -> None:
    if rate not in RATE_CHOICES or frames not in BUFFER_CHOICES:
        raise ValueError('Unsupported sample rate or buffer')
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    if path.exists(): cfg.read(path, encoding='utf-8')
    if not cfg.has_section('Audio'): cfg.add_section('Audio')
    cfg.set('Audio', 'SampleRate', str(rate))
    cfg.set('Audio', 'BufferFrames', str(frames))
    from io import StringIO
    output = StringIO()
    cfg.write(output, space_around_delimiters=False)
    _atomic_text(path, output.getvalue())


def load_prefs() -> dict:
    default = {'input': 'default', 'output': 'default', 'auto_engine': True, 'minimize_to_tray': True}
    path = gui_prefs_path()
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(obj, dict):
            for key in default:
                if isinstance(obj.get(key), type(default[key])) and (not isinstance(obj.get(key), str) or obj.get(key)):
                    default[key] = obj[key]
    except (FileNotFoundError, ValueError, OSError): pass
    return default


def save_prefs(prefs: dict) -> None:
    _atomic_text(gui_prefs_path(), json.dumps(prefs, indent=2) + '\n')


def parse_alsa_pcm_names(output: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    lines = output.splitlines()
    for i, line in enumerate(lines):
        if not line or line[0].isspace() or line.startswith('#'): continue
        key = line.strip()
        if not re.fullmatch(r'[A-Za-z0-9_.,:=\-/]+', key): continue
        desc = (lines[i+1].strip() if i+1 < len(lines) and lines[i+1].startswith(' ') else '')
        if key not in [k for k, _ in result]: result.append((key, desc))
    return result


def list_pcm_devices(capture: bool) -> list[tuple[str, str]]:
    cmd = 'arecord' if capture else 'aplay'
    found = [('default', 'Dispositivo predeterminado de KDE / PipeWire')]
    if not shutil.which(cmd): return found
    try:
        completed = subprocess.run([cmd, '-L'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   text=True, timeout=4, check=False)
        options = parse_alsa_pcm_names(completed.stdout)
        for key, description in options:
            if key != 'default': found.append((key, description))
    except (OSError, subprocess.TimeoutExpired): pass
    return found


def engine_port_is_used() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.bind(('127.0.0.1', ENGINE_PORT))
            return False
        except OSError:
            return True


def find_fl_studio(prefix: Path) -> Path | None:
    root = prefix / 'drive_c'
    candidates = [
        root / 'Program Files' / 'Image-Line' / 'FL Studio 2025' / 'FL64.exe',
        root / 'Program Files' / 'Image-Line' / 'FL Studio 2024' / 'FL64.exe',
        root / 'Program Files' / 'Image-Line' / 'FL Studio 2026' / 'FL64.exe',
    ]
    for item in candidates:
        if item.is_file(): return item
    for base in (root / 'Program Files' / 'Image-Line', root / 'Program Files (x86)' / 'Image-Line'):
        if base.is_dir():
            try:
                for item in base.rglob('FL64.exe'):
                    if item.is_file(): return item
            except OSError: pass
    return None


def fl_studio_running() -> bool:
    # Detect running FL Studio in Wine without terminating unrelated processes.
    try:
        out = subprocess.run(['ps', '-eo', 'comm='], capture_output=True, text=True, timeout=3)
        return any(name.strip().lower() in ('fl64.exe', 'fl.exe') for name in out.stdout.splitlines())
    except (OSError, subprocess.TimeoutExpired):
        return False


def autostart_path() -> Path:
    return Path.home() / '.config' / 'autostart' / 'gtxasio.desktop'


def set_autostart(enabled: bool, launcher: Path) -> None:
    destination = autostart_path()
    if enabled:
        desktop = f'''[Desktop Entry]
Type=Application
Name=GTXASIO
Comment=GTXASIO audio control
Exec="{launcher}"
Icon=gtxasio
Terminal=false
Categories=AudioVideo;Audio;
X-GNOME-Autostart-enabled=true
'''
        _atomic_text(destination, desktop)
    else:
        destination.unlink(missing_ok=True)
