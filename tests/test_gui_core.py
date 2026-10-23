"""Dependency-free tests for control center configuration and ALSA discovery."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('gtx_core', str(Path(__file__).resolve().parents[1] / 'app' / 'gtx_core.py'))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

class TestControlCenter(unittest.TestCase):
    def test_ini_roundtrip_all_sizes(self):
        with tempfile.TemporaryDirectory() as td:
            ini = Path(td) / 'gtxasio.ini'
            for rate in core.RATE_CHOICES:
                for frames in core.BUFFER_CHOICES:
                    core.write_audio_settings(ini, rate, frames)
                    self.assertEqual((rate, frames), core.read_audio_settings(ini))
            self.assertIn('BufferFrames=1024', ini.read_text())
            self.assertIn('SampleRate=48000', ini.read_text())

    def test_ini_preserves_other_sections(self):
        with tempfile.TemporaryDirectory() as td:
            ini = Path(td) / 'gtxasio.ini'
            ini.write_text('[Audio]\nSampleRate=44100\nBufferFrames=512\n[Other]\nKeep=1\n')
            core.write_audio_settings(ini, 48000, 64)
            self.assertIn('Keep=1', ini.read_text())

    def test_invalid_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError): core.write_audio_settings(Path(td)/'cfg.ini', 96000, 48)

    def test_parse_alsa_list(self):
        sample = 'null\n    Discards all samples\ndefault\n    Default device\nplughw:CARD=PCH,DEV=0\n    Built-in microphone\n'
        parsed = core.parse_alsa_pcm_names(sample)
        self.assertEqual([n for n, _ in parsed], ['null', 'default', 'plughw:CARD=PCH,DEV=0'])

    def test_missing_fl_executable(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(core.find_fl_studio(Path(td)))

    def test_port_free_or_in_use(self):
        self.assertIsInstance(core.engine_port_is_used(), bool)

if __name__ == '__main__': unittest.main()
