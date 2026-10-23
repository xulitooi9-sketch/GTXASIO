#!/usr/bin/env python3
"""Quick muted-output input meter for the GTXASIO ALSA<->Wine UDP bridge.
Run ONLY when FL Studio is closed, with the GTXASIO engine already running.
This does not record audio to disk or access the microphone outside the engine.
"""
import argparse
import math
import socket
import struct
import time

MAGIC, VERSION, PORT = 0x31585447, 1, 37261
HEADER = struct.Struct('<6I')

def run(rate: int, frames: int, seconds: float) -> None:
    payload = bytes(frames * 2 * 4)  # silence, never generate an audible tone
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.5)
    blocks = max(1, int(seconds * rate / frames))
    got_signal = False
    print('GTXASIO mic meter (test with headphones; FL Studio must be closed).')
    print('Speak into the microphone. The input peak should become > 0%.')
    try:
        for seq in range(blocks):
            packet = HEADER.pack(MAGIC, VERSION, seq, frames, rate, 0) + payload
            sock.sendto(packet, ('127.0.0.1', PORT))
            try:
                raw, _ = sock.recvfrom(len(packet))
            except socket.timeout as e:
                raise RuntimeError('No engine reply. Check its terminal, rate and buffer.') from e
            if len(raw) != len(packet):
                raise RuntimeError('Unexpected engine reply length')
            magic, ver, number, block_frames, hz, status = HEADER.unpack_from(raw)
            if (magic, ver, number, block_frames, hz, status) != (MAGIC, VERSION, seq, frames, rate, 0):
                raise RuntimeError('Engine and mic meter settings mismatch or audio error')
            samples = struct.unpack_from(f'<{frames*2}f', raw, HEADER.size)
            peak = max(abs(x) if math.isfinite(x) else 0.0 for x in samples)
            if peak > 0.001:
                got_signal = True
            if (seq + 1) % max(1, rate // frames // 4) == 0 or seq == blocks-1:
                print(f'\rInput peak: {min(peak*100,100):5.1f}%  ', end='', flush=True)
    finally:
        sock.close()
        print()
    if got_signal:
        print('OK: GTXASIO receives non-silent microphone audio.')
    else:
        print('No input signal detected. Check default mic, mute and ALSA capture status.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--rate', type=int, choices=[44100, 48000], default=44100)
    parser.add_argument('--buffer', type=int, choices=[128, 256, 512, 1024], default=512)
    parser.add_argument('--seconds', type=float, default=6)
    args = parser.parse_args()
    try:
        run(args.rate, args.buffer, args.seconds)
    except (RuntimeError, OSError) as e:
        parser.exit(1, f'ERROR: {e}\n')
