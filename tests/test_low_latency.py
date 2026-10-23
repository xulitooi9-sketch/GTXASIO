"""Silent loopback low buffer checks. Does NOT measure actual hardware latency."""
import pathlib
import socket
import subprocess
import time
import unittest
from tools.probe import probe

ROOT = pathlib.Path(__file__).resolve().parents[1]

class LowLatencyTest(unittest.TestCase):
    def run_case(self, rate, frames):
        p=subprocess.Popen([str(ROOT/'build/gtxasio-engine'),'--output','null','--no-input',
                            '--rate',str(rate),'--buffer',str(frames)],
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            ready=False
            deadline=time.monotonic()+3
            while time.monotonic() < deadline:
                if p.poll() is not None:
                    self.fail(f'Engine stopped at {rate}Hz/{frames}frames: {p.stderr.read()}')
                try:
                    elapsed=probe(rate, frames, 30)
                    self.assertGreater(elapsed, 0)
                    ready=True
                    break
                except (socket.timeout, ConnectionRefusedError, OSError):
                    time.sleep(.03)
            self.assertTrue(ready,f'No loopback response for {rate}Hz/{frames} frames')
        finally:
            p.terminate()
            try:
                p.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill();p.communicate()

    def test_64_44100(self): self.run_case(44100,64)
    def test_64_48000(self): self.run_case(48000,64)
    def test_128_44100(self): self.run_case(44100,128)
    def test_128_48000(self): self.run_case(48000,128)
    def test_256_44100(self): self.run_case(44100,256)
    def test_512_44100(self): self.run_case(44100,512)
    def test_1024_44100(self): self.run_case(44100,1024)
