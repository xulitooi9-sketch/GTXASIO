"""Verify the ALSA engine accepts a systemd-style inherited UDP socket and idles out.

Uses only ALSA 'null' (never actual speakers) and does not start user services.
"""
import os
from pathlib import Path
import socket
import subprocess
import time
import unittest
from tools.probe import probe

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'build/gtxasio-engine'

class SocketActivation(unittest.TestCase):
    def test_inherited_socket_replies_then_exits_on_idle(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(('127.0.0.1', 37261))
        # Using a wrapper shell guarantees LISTEN_PID is the engine PID after
        # exec. Descriptor 3 is inherited exactly as systemd passes it.
        def remap_fd():
            if s.fileno() != 3: os.dup2(s.fileno(), 3)
        p = subprocess.Popen(['bash','-c','export LISTEN_PID=$$; exec "$@"','bash',
                              str(ENGINE),'--output','null','--no-input',
                              '--rate','44100','--buffer','64'],
                             env={**os.environ,'LISTEN_FDS':'1'},
                             pass_fds=(s.fileno(),), preexec_fn=remap_fd,
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline=time.monotonic()+5
            success=False
            while time.monotonic()<deadline:
                if p.poll() is not None: break
                try:
                    probe(44100,64,8)
                    success=True
                    break
                except (socket.timeout,ConnectionRefusedError,OSError):
                    time.sleep(.08)
            self.assertTrue(success, 'inherited UDP descriptor did not reply')
            try:
                out,err=p.communicate(timeout=5.5)
            except subprocess.TimeoutExpired:
                self.fail('socket-activated engine failed to exit after idle')
            self.assertEqual(p.returncode,0,err)
            self.assertIn('idle; releasing mic and output',err)
        finally:
            if p.poll() is None:
                p.terminate()
                try: p.communicate(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill();p.communicate()
            s.close()
