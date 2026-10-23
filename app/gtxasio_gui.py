#!/usr/bin/env python3
"""GTXASIO Control Center — KDE desktop front-end for the existing ALSA engine.

Does not modify the working ASIO DLL, audio protocol or FL Studio settings beyond
writing the same shared gtxasio.ini already consumed by GTXASIO v0.1.5.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

try:
    from PyQt6.QtCore import Qt, QProcess, QTimer
    from PyQt6.QtGui import QAction, QIcon, QCloseEvent
    from PyQt6.QtWidgets import (
        QApplication, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout,
        QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
        QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QSystemTrayIcon,
        QVBoxLayout, QWidget, QMenu,
    )
except ImportError:
    print('GTXASIO necesita PyQt6: sudo pacman -S --needed python-pyqt6', file=sys.stderr)
    sys.exit(2)

from gtx_core import (
    BUFFER_CHOICES, RATE_CHOICES, autostart_path, driver_config_path,
    engine_port_is_used, find_fl_studio, fl_studio_running, gui_prefs_path,
    list_pcm_devices, load_prefs, read_audio_settings, save_prefs,
    set_autostart, wine_prefix, write_audio_settings,
)

BASE = Path(__file__).resolve().parent.parent
ENGINE = BASE / 'build' / 'gtxasio-engine'
ICON_PATH = BASE / 'assets' / 'gtxasio.png'
LAUNCHER = BASE / 'scripts' / 'gtxasio-launch.sh'

QSS = '''
QMainWindow, QWidget#base {background: #0d1321; color: #e5edf6; font-family: "Noto Sans", "Inter", sans-serif; font-size: 13px;}
QWidget#sidebar {background: #101c2d; border-right: 1px solid #24354b;}
QFrame#card {background: #142238; border: 1px solid #2a3b52; border-radius: 14px;}
QLabel#eyebrow {color: #8a9fba; font-size: 11px; font-weight: 700;}
QLabel#brand {color: #e9fff8; font-size: 24px; font-weight: 800;}
QLabel#heading {color: #e9f3ff; font-size: 22px; font-weight: 700;}
QLabel#subheading {color: #8fa4bd; font-size: 12px;}
QLabel#value {color: #f0fbff; font-size: 24px; font-weight: 700;}
QLabel#muted {color: #8ea3b9; font-size: 12px;}
QLabel#statusGood {color: #4ce4b9; font-weight: 700;}
QLabel#statusBad {color: #ffa077; font-weight: 700;}
QLabel#statusIdle {color: #9eb0c7; font-weight: 700;}
QPushButton {background: #24354d; border: 1px solid #38506a; color: #e8f5ff; padding: 10px 14px; border-radius: 8px; font-weight: 650;}
QPushButton:hover {background: #2d4761;}
QPushButton:disabled {color: #6b8098; background: #1c2939; border-color: #26394d;}
QPushButton#primary {background: #43e0b7; color: #0b2225; border: 1px solid #43e0b7;}
QPushButton#primary:hover {background: #7af7d5;}
QPushButton#danger {background: #453037; color: #ffb9b2; border: 1px solid #714950;}
QPushButton#navigation {background: transparent; border: 0; color: #a6b9cc; text-align: left; padding: 14px 16px;}
QPushButton#navigation:checked {background: #203a4a; color: #65f0c6;}
QComboBox {background: #0b1828; color: #f0f7ff; border: 1px solid #36506a; border-radius: 8px; padding: 9px 13px; min-height: 20px;}
QComboBox:hover {border-color: #58cdb4;}
QComboBox QAbstractItemView {background: #142238; color: #f1f7ff; selection-background-color: #2b5f67;}
QCheckBox {color: #d8e5f0; spacing: 9px;}
QCheckBox::indicator {width: 17px; height: 17px;}
QProgressBar {background: #233344; border: none; border-radius: 5px; height: 11px; text-align: center; color: transparent;}
QProgressBar::chunk {background: #4ce4b9; border-radius: 5px;}
QPlainTextEdit {background: #0b1727; color: #abf3d3; border: 1px solid #2c3e57; border-radius: 10px; padding: 10px; font-family: monospace; font-size: 11px;}
QScrollArea {border: 0; background: transparent;}
'''


def card(title: str) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName('card')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    heading = QLabel(title)
    heading.setStyleSheet('font-weight: 700; font-size: 15px; color: #f3f9ff;')
    layout.addWidget(heading)
    return frame, layout


def label(text: str, role: str = 'muted') -> QLabel:
    out = QLabel(text)
    out.setObjectName(role)
    out.setWordWrap(True)
    return out


class GTXWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.prefix = wine_prefix()
        self.ini = driver_config_path(self.prefix)
        self.prefs = load_prefs()
        self.engine = QProcess(self)
        self.engine.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.engine.readyReadStandardOutput.connect(self.read_engine_log)
        self.engine.finished.connect(self.engine_finished)
        self.is_engine_ready = False
        self.last_log: list[str] = []
        self.partial_output = ""
        self.exit_requested = False
        self.started_process = None
        self.rate, self.frames = read_audio_settings(self.ini)
        self.setWindowTitle('GTXASIO — Control Center')
        self.setMinimumSize(890, 615)
        self.resize(1030, 705)
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.setStyleSheet(QSS)
        self.build_ui()
        self.build_tray()
        self.refresh_devices()
        self.refresh_status()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(1500)
        if self.prefs.get('auto_engine', True):
            QTimer.singleShot(300, self.start_engine)

    def build_ui(self) -> None:
        base = QWidget()
        base.setObjectName('base')
        self.setCentralWidget(base)
        row = QHBoxLayout(base)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(226)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(17, 28, 17, 22)
        side.setSpacing(12)
        brand = QLabel('◉  GTXASIO')
        brand.setObjectName('brand')
        side.addWidget(brand)
        side.addWidget(label('AUDIO DRIVER  /  LINUX', 'eyebrow'))
        side.addSpacing(26)
        self.tabs = []
        for title in ('Audio', 'Diagnóstico', 'Preferencias'):
            b = QPushButton(title)
            b.setCheckable(True)
            b.setObjectName('navigation')
            index = len(self.tabs)
            b.clicked.connect(lambda _checked=False, index=index: self.change_page(index))
            side.addWidget(b)
            self.tabs.append(b)
        side.addStretch()
        self.sidebar_state = label('● Motor detenido', 'statusIdle')
        side.addWidget(self.sidebar_state)
        side.addWidget(label('GTXASIO  •  v0.1.7', 'eyebrow'))
        row.addWidget(sidebar)
        self.stack = QStackedWidget()
        row.addWidget(self.stack, 1)
        self.build_audio_page()
        self.build_diag_page()
        self.build_prefs_page()
        self.change_page(0)

    def make_page(self, title: str, subtitle: str) -> QVBoxLayout:
        wrapper = QScrollArea()
        wrapper.setWidgetResizable(True)
        inner = QWidget()
        inner.setObjectName('base')
        v = QVBoxLayout(inner)
        v.setContentsMargins(28, 29, 28, 29)
        v.setSpacing(16)
        v.addWidget(label('GTXASIO CONTROL CENTER', 'eyebrow'))
        v.addWidget(label(title, 'heading'))
        v.addWidget(label(subtitle, 'subheading'))
        wrapper.setWidget(inner)
        self.stack.addWidget(wrapper)
        return v

    def build_audio_page(self) -> None:
        page = self.make_page('Control de audio', 'Controla el motor sin abrir Konsole.')
        status_frame, status_layout = card('Estado del controlador')
        state = QHBoxLayout()
        self.state_label = label('Detenido', 'statusIdle')
        self.state_label.setStyleSheet('font-size: 18px; font-weight: 700;')
        state.addWidget(self.state_label)
        state.addStretch()
        self.latency_label = label(f'{self.frames} samples  •  {self.rate:,} Hz')
        state.addWidget(self.latency_label)
        status_layout.addLayout(state)
        self.health_label = label('El motor no está encendido.')
        status_layout.addWidget(self.health_label)
        actions = QHBoxLayout()
        self.start_button = QPushButton('▶  Encender audio')
        self.start_button.setObjectName('primary')
        self.start_button.clicked.connect(self.start_engine)
        self.stop_button = QPushButton('■  Detener')
        self.stop_button.setObjectName('danger')
        self.stop_button.clicked.connect(self.stop_engine)
        self.fl_button = QPushButton('↗  Abrir FL Studio')
        self.fl_button.clicked.connect(self.open_fl_studio)
        actions.addWidget(self.start_button)
        actions.addWidget(self.stop_button)
        actions.addWidget(self.fl_button)
        status_layout.addLayout(actions)
        page.addWidget(status_frame)

        settings_frame, settings_layout = card('Dispositivos y latencia')
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(13)
        grid.addWidget(label('Búfer / samples', 'eyebrow'), 0, 0)
        grid.addWidget(label('Frecuencia', 'eyebrow'), 0, 1)
        self.buffer = QComboBox()
        for n in BUFFER_CHOICES:
            self.buffer.addItem(f'{n} samples   ·   {n/self.rate*1000:.2f} ms/bloque', n)
        self.buffer.setCurrentIndex(BUFFER_CHOICES.index(self.frames))
        self.rate_combo = QComboBox()
        for n in RATE_CHOICES: self.rate_combo.addItem(f'{n:,} Hz', n)
        self.rate_combo.setCurrentIndex(RATE_CHOICES.index(self.rate))
        self.rate_combo.currentIndexChanged.connect(self.update_buffer_descriptions)
        grid.addWidget(self.buffer, 1, 0)
        grid.addWidget(self.rate_combo, 1, 1)
        grid.addWidget(label('Entrada / micrófono', 'eyebrow'), 2, 0)
        grid.addWidget(label('Salida / auriculares', 'eyebrow'), 2, 1)
        self.input_device = QComboBox()
        self.output_device = QComboBox()
        grid.addWidget(self.input_device, 3, 0)
        grid.addWidget(self.output_device, 3, 1)
        settings_layout.addLayout(grid)
        self.preset_note = label('64 samples es exigente; si aparecen cortes, prueba 128 o 256.')
        settings_layout.addWidget(self.preset_note)
        foot = QHBoxLayout()
        self.refresh_button = QPushButton('⟳  Actualizar dispositivos')
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.apply_button = QPushButton('Guardar y aplicar')
        self.apply_button.setObjectName('primary')
        self.apply_button.clicked.connect(self.apply_settings)
        foot.addWidget(self.refresh_button)
        foot.addStretch()
        foot.addWidget(self.apply_button)
        settings_layout.addLayout(foot)
        page.addWidget(settings_frame)

        meter_frame, meter_layout = card('Micrófono · nivel de entrada')
        self.mic_meter = QProgressBar()
        self.mic_meter.setRange(0, 100)
        self.mic_meter.setValue(0)
        self.mic_meter.setTextVisible(False)
        meter_layout.addWidget(self.mic_meter)
        self.mic_note = label('El nivel aparece cuando FL Studio está enviando audio al motor.')
        meter_layout.addWidget(self.mic_note)
        page.addWidget(meter_frame)
        page.addStretch()

    def build_diag_page(self) -> None:
        page = self.make_page('Diagnóstico', 'Actividad en tiempo real y detalles de audio.')
        frame, layout = card('Estado ALSA y recuperación')
        grid = QGridLayout()
        self.metrics = {}
        for i, (key, name) in enumerate((('playback_recoveries','Recuperaciones de salida'),
                                         ('capture_recoveries','Recuperaciones de entrada'),
                                         ('invalid','Paquetes inválidos'), ('blocks','Bloques procesados'))):
            grid.addWidget(label(name, 'eyebrow'), i // 2 * 2, i % 2)
            metric = label('—', 'value')
            self.metrics[key] = metric
            grid.addWidget(metric, i // 2 * 2 + 1, i % 2)
        layout.addLayout(grid)
        page.addWidget(frame)
        log_frame, log_layout = card('Registro del motor')
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.document().setMaximumBlockCount(500)
        self.log_edit.setMinimumHeight(265)
        log_layout.addWidget(self.log_edit)
        buttons = QHBoxLayout()
        copy = QPushButton('Copiar registro')
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.log_edit.toPlainText()))
        clear = QPushButton('Limpiar vista')
        clear.clicked.connect(self.log_edit.clear)
        buttons.addWidget(copy)
        buttons.addWidget(clear)
        buttons.addStretch()
        log_layout.addLayout(buttons)
        page.addWidget(log_frame)
        page.addStretch()

    def build_prefs_page(self) -> None:
        page = self.make_page('Preferencias', 'Integración de escritorio KDE / CachyOS.')
        card1, layout = card('Inicio automático')
        self.auto_engine = QCheckBox('Encender motor al abrir GTXASIO')
        self.auto_engine.setChecked(self.prefs.get('auto_engine', True))
        self.auto_engine.toggled.connect(self.save_gui_options)
        self.start_with_linux = QCheckBox('Abrir GTXASIO al iniciar sesión de Linux')
        self.start_with_linux.setChecked(autostart_path().exists())
        self.start_with_linux.toggled.connect(self.toggle_autostart)
        self.minimize_check = QCheckBox('Dejar GTXASIO activo en la bandeja al cerrar la ventana')
        self.minimize_check.setChecked(self.prefs.get('minimize_to_tray', True))
        self.minimize_check.toggled.connect(self.save_gui_options)
        layout.addWidget(self.auto_engine)
        layout.addWidget(self.start_with_linux)
        layout.addWidget(self.minimize_check)
        page.addWidget(card1)
        card2, lay2 = card('Instalación actual')
        lay2.addWidget(label('Prefijo Wine', 'eyebrow'))
        lay2.addWidget(label(str(self.prefix)))
        lay2.addWidget(label('Configuración compartida con el panel ASIO de FL Studio', 'eyebrow'))
        lay2.addWidget(label(str(self.ini)))
        lay2.addWidget(label('El controlador DLL ya instalado no se reemplaza al instalar esta interfaz.'))
        page.addWidget(card2)
        page.addStretch()

    def build_tray(self) -> None:
        self.tray = QSystemTrayIcon(QIcon(str(ICON_PATH)), self)
        context = QMenu(self)
        show_action = QAction('Mostrar GTXASIO', self)
        show_action.triggered.connect(self.restore_window)
        self.tray_start = QAction('Encender audio', self)
        self.tray_start.triggered.connect(self.start_engine)
        fl_action = QAction('Abrir FL Studio', self)
        fl_action.triggered.connect(self.open_fl_studio)
        quit_action = QAction('Salir de GTXASIO', self)
        quit_action.triggered.connect(self.quit_app)
        context.addAction(show_action)
        context.addAction(self.tray_start)
        context.addAction(fl_action)
        context.addSeparator()
        context.addAction(quit_action)
        self.tray.setContextMenu(context)
        self.tray.activated.connect(lambda reason: self.restore_window() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        if QSystemTrayIcon.isSystemTrayAvailable(): self.tray.show()

    def change_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for i, item in enumerate(self.tabs): item.setChecked(index == i)

    def log(self, message: str) -> None:
        for ln in message.rstrip().splitlines():
            self.log_edit.appendPlainText(ln)
            self.last_log.append(ln)
        self.last_log = self.last_log[-200:]

    def update_buffer_descriptions(self) -> None:
        rate = int(self.rate_combo.currentData() or 44100)
        old = self.buffer.currentIndex()
        self.buffer.blockSignals(True)
        for i, n in enumerate(BUFFER_CHOICES):
            self.buffer.setItemText(i, f'{n} samples   ·   {n/rate*1000:.2f} ms/bloque')
        self.buffer.setCurrentIndex(old)
        self.buffer.blockSignals(False)

    def refresh_devices(self) -> None:
        for combo, capture, current in ((self.input_device, True, self.prefs['input']),
                                         (self.output_device, False, self.prefs['output'])):
            options = list_pcm_devices(capture)
            combo.clear()
            for name, description in options:
                combo.addItem(('Predeterminado (KDE)' if name == 'default' else name), name)
                combo.setItemData(combo.count() - 1, description, Qt.ItemDataRole.ToolTipRole)
            names = [n for n, _ in options]
            if current not in names and current:
                combo.addItem(f'{current} (configurado)', current)
            target = combo.findData(current)
            combo.setCurrentIndex(max(0, target))
        self.log('Dispositivos ALSA actualizados.')

    def _save_preferences(self) -> None:
        self.prefs['input'] = str(self.input_device.currentData() or 'default')
        self.prefs['output'] = str(self.output_device.currentData() or 'default')
        self.prefs['auto_engine'] = self.auto_engine.isChecked()
        self.prefs['minimize_to_tray'] = self.minimize_check.isChecked()
        save_prefs(self.prefs)

    def save_gui_options(self) -> None:
        self._save_preferences()

    def toggle_autostart(self, enabled: bool) -> None:
        try: set_autostart(enabled, LAUNCHER)
        except OSError as exc:
            QMessageBox.warning(self, 'GTXASIO', f'No se pudo modificar el inicio automático: {exc}')
            self.start_with_linux.blockSignals(True)
            self.start_with_linux.setChecked(not enabled)
            self.start_with_linux.blockSignals(False)

    def running(self) -> bool:
        return self.engine.state() != QProcess.ProcessState.NotRunning

    def start_engine(self) -> None:
        if self.running(): return
        if not ENGINE.is_file():
            QMessageBox.warning(self, 'GTXASIO', 'Falta el motor. Compílalo con el instalador incluido.')
            self.change_page(1)
            return
        if not self.ini.exists():
            QMessageBox.warning(self, 'GTXASIO', 'Falta la configuración de GTXASIO en Wine. Registra primero la DLL.')
            return
        if engine_port_is_used():
            self.health_label.setText('Puerto 37261 ocupado: otro motor GTXASIO ya está encendido.')
            self.log('ERROR: puerto ocupado por otra instancia. Detén la versión abierta en Konsole antes de iniciar este panel.')
            self.change_page(1)
            return
        rate, frames = read_audio_settings(self.ini)
        self.rate, self.frames = rate, frames
        self.is_engine_ready = False
        self.partial_output = ''
        args = ['--rate', str(rate), '--buffer', str(frames), '--input', self.prefs['input'], '--output', self.prefs['output']]
        self.log(f'Iniciando motor · {rate} Hz · {frames} muestras · in={self.prefs["input"]} · out={self.prefs["output"]}')
        self.engine.setWorkingDirectory(str(BASE))
        self.engine.start(str(ENGINE), args)
        if not self.engine.waitForStarted(1500):
            self.log(f'ERROR: {self.engine.errorString()}')
        self.refresh_status()

    def stop_engine(self) -> None:
        if not self.running(): return
        self.log('Deteniendo GTXASIO…')
        pid = int(self.engine.processId())
        if pid:
            try: os.kill(pid, signal.SIGTERM)
            except ProcessLookupError: pass
        if not self.engine.waitForFinished(2200):
            self.engine.kill()
            self.engine.waitForFinished(1000)
        self.is_engine_ready = False
        self.refresh_status()

    def engine_finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        self.is_engine_ready = False
        self.log(f'Motor detenido (código {code}).')
        self.refresh_status()

    def read_engine_log(self) -> None:
        raw = bytes(self.engine.readAllStandardOutput()).decode('utf-8', errors='replace')
        self.partial_output += raw
        # QProcess may deliver arbitrary chunk boundaries; parse full lines only.
        while '\n' in self.partial_output:
            line, self.partial_output = self.partial_output.split('\n', 1)
            self.log(line)
            if 'GTXASIO engine v' in line: self.is_engine_ready = True
            if 'capture disabled' in line or 'in=silence' in line:
                self.health_label.setText('Atención: entrada de micrófono no disponible; comprueba el dispositivo ALSA.')
            metrics = re.search(r'blocks=(\d+) playback_recoveries=(\d+) capture_recoveries=(\d+) invalid=(\d+) mic_peak=([\d.]+)%', line)
            if metrics:
                keys = ('blocks', 'playback_recoveries', 'capture_recoveries', 'invalid')
                for key, value in zip(keys, metrics.groups()[:4]): self.metrics[key].setText(value)
                peak = float(metrics.group(5))
                self.mic_meter.setValue(min(100, max(0, int(peak))))
                self.mic_note.setText(f'Pico de entrada: {peak:.1f}%  ·  medido por el motor')
                if int(metrics.group(2)) + int(metrics.group(3)) > 0:
                    self.health_label.setText('Hay recuperaciones ALSA: revisa la estabilidad o sube el búfer.')

    def refresh_status(self) -> None:
        active = self.running()
        if active and self.is_engine_ready:
            status, name = '● Activo', 'statusGood'
        elif active:
            status, name = '◌ Iniciando', 'statusIdle'
        else:
            status, name = '○ Detenido', 'statusIdle'
        self.state_label.setObjectName(name)
        self.state_label.setText(status)
        self.state_label.style().unpolish(self.state_label)
        self.state_label.style().polish(self.state_label)
        self.sidebar_state.setText(status)
        self.sidebar_state.setObjectName(name)
        self.sidebar_state.style().unpolish(self.sidebar_state)
        self.sidebar_state.style().polish(self.sidebar_state)
        rate, frames = read_audio_settings(self.ini)
        self.latency_label.setText(f'{frames} samples · {rate:,} Hz')
        if not active:
            self.health_label.setText('Motor apagado. Pulsa Encender audio antes de abrir FL Studio.')
            self.mic_meter.setValue(0)
        self.start_button.setEnabled(not active)
        self.stop_button.setEnabled(active)
        self.tray_start.setText('Detener audio' if active else 'Encender audio')
        try: self.tray_start.triggered.disconnect()
        except TypeError: pass
        self.tray_start.triggered.connect(self.stop_engine if active else self.start_engine)
        self.tray.setToolTip(f'GTXASIO — {"Activo" if active else "Detenido"}')

    def apply_settings(self) -> None:
        if fl_studio_running():
            QMessageBox.warning(self, 'Cerrar FL Studio',
                'FL Studio está abierto. Ciérralo completamente antes de cambiar la frecuencia o el búfer para evitar cortes.')
            return
        should_restart = self.running()
        new_rate = int(self.rate_combo.currentData())
        new_buffer = int(self.buffer.currentData())
        try:
            write_audio_settings(self.ini, new_rate, new_buffer)
            self._save_preferences()
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, 'GTXASIO', f'No se pudieron guardar ajustes: {exc}')
            return
        if should_restart:
            self.stop_engine()
            self.start_engine()
        self.refresh_status()
        self.log(f'Ajustes aplicados · {new_rate} Hz · {new_buffer} muestras. Reinicia FL Studio si estaba abierto.')

    def open_fl_studio(self) -> None:
        if not shutil.which('wine'):
            QMessageBox.warning(self, 'GTXASIO', 'Wine no está instalado.')
            return
        if fl_studio_running():
            QMessageBox.information(self, 'GTXASIO', 'FL Studio ya está abierto.')
            return
        if not self.running():
            self.start_engine()
            if not self.running(): return
        exe = find_fl_studio(self.prefix)
        if not exe:
            QMessageBox.warning(self, 'GTXASIO', 'No encontré FL64.exe dentro de ~/.wine-flstudio. Comprueba la instalación de FL Studio.')
            return
        env = os.environ.copy()
        env['WINEPREFIX'] = str(self.prefix)
        logpath = Path.home() / '.cache' / 'gtxasio' / 'flstudio.log'
        logpath.parent.mkdir(parents=True, exist_ok=True)
        try:
            with logpath.open('ab') as f:
                subprocess.Popen(['wine', str(exe)], cwd=exe.parent, env=env,
                                 stdout=f, stderr=subprocess.STDOUT, start_new_session=True)
            self.log('FL Studio iniciado con el prefijo Wine configurado.')
        except OSError as exc:
            QMessageBox.critical(self, 'GTXASIO', f'Error al iniciar FL Studio: {exc}')

    def restore_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_app(self) -> None:
        if self.running() and fl_studio_running():
            answer = QMessageBox.question(self, 'Salir de GTXASIO',
                'FL Studio sigue abierto. Salir apagará el motor y cortará su audio. ¿Salir de todos modos?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes: return
        self.exit_requested = True
        self.stop_engine()
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self.exit_requested and self.minimize_check.isChecked() and QSystemTrayIcon.isSystemTrayAvailable():
            event.ignore()
            self.hide()
            self.tray.showMessage('GTXASIO', 'El motor sigue funcionando en segundo plano.',
                                  QSystemTrayIcon.MessageIcon.Information, 1800)
            return
        event.ignore()
        self.quit_app()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName('GTXASIO')
    app.setQuitOnLastWindowClosed(False)
    window = GTXWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
