import subprocess, unittest, pathlib, time, socket
ROOT=pathlib.Path(__file__).parents[1]
class TestLoopback(unittest.TestCase):
    def test_silent_null_playback(self):
        p=subprocess.Popen([str(ROOT/'build/gtxasio-engine'),'--output','null','--no-input'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                if p.poll() is not None: self.fail('Engine did not start: '+p.stderr.read())
                try:
                    from tools.probe import probe
                    elapsed=probe(48000,512,20)
                    self.assertGreater(elapsed,0.1)
                    break
                except (socket.timeout, OSError): time.sleep(.1)
            else: self.fail('Engine not responding')
        finally:
            p.terminate()
            try: p.communicate(timeout=3)
            except subprocess.TimeoutExpired: p.kill(); p.communicate()
