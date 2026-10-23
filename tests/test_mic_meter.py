"""Smoke test for capture packet shape using ALSA null input (no mic hardware)."""
import pathlib
import subprocess
import time
import unittest
ROOT=pathlib.Path(__file__).parents[1]

class TestInputBridge(unittest.TestCase):
    def test_null_capture_bridge(self):
        engine=subprocess.Popen([str(ROOT/'build/gtxasio-engine'), '--output','null',
            '--input','null','--rate','44100','--buffer','512'],
            cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                if engine.poll() is not None:
                    self.fail('Engine failed to open ALSA null input: '+engine.stderr.read())
                meter=subprocess.run(['python3',str(ROOT/'tools/mic_meter.py'),'--rate','44100',
                    '--buffer','512','--seconds','0.25'],capture_output=True,text=True,timeout=5)
                if meter.returncode==0:
                    self.assertIn('No input signal detected',meter.stdout)
                    return
                time.sleep(.15)
            self.fail('Mic meter did not receive packets')
        finally:
            engine.terminate()
            try: engine.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                engine.kill();engine.communicate()
