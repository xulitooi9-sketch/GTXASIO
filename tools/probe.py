#!/usr/bin/env python3
"""Loopback-protocol smoke test. No speaker/microphone hardware needed with --output null."""
import argparse
import math
import socket
import struct
import time
MAGIC, VERSION, PORT = 0x31585447, 1, 37261
HEADER = '<6I'

def probe(rate=48000, frames=512, blocks=100, tone=False):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1)
    last = time.monotonic()
    try:
        return _run(s, rate, frames, blocks, tone, last)
    finally:
        s.close()

def _run(s,rate,frames,blocks,tone,last):
    for k in range(blocks):
        data = [0.0] * (frames * 2)
        if tone:
            for i in range(frames):
                v = 0.05 * math.sin(2 * math.pi * 440 * (k * frames + i) / rate)
                data[2*i] = data[2*i+1] = v
        packet = struct.pack(HEADER, MAGIC,VERSION,k,frames,rate,0) + struct.pack('<%df' % (frames*2),*data)
        s.sendto(packet,('127.0.0.1',PORT))
        raw, _ = s.recvfrom(len(packet))
        if len(raw) != len(packet):
            raise RuntimeError('Bad packet size %d' % len(raw))
        magic,vers,seq,count,hz,status = struct.unpack(HEADER,raw[:24])
        if (magic,vers,seq,count,hz,status) != (MAGIC,VERSION,k,frames,rate,0):
            raise RuntimeError('Bad reply: %s' % ((magic,vers,seq,count,hz,status),))
        if any(not math.isfinite(x) for x in struct.unpack('<%df' % (frames*2),raw[24:])):
            raise RuntimeError('Non-finite captured samples')
    elapsed = time.monotonic()-last
    ideal = blocks*frames/rate
    print('OK: %d/%d packets; %.2fs, ideal %.2fs; avg %.2f ms/block' % (blocks,blocks,elapsed,ideal,elapsed*1000/blocks))
    return elapsed
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--rate',type=int,default=48000)
    p.add_argument('--buffer',type=int,default=512)
    p.add_argument('--blocks',type=int,default=100)
    p.add_argument('--tone',action='store_true',help='Low volume 440Hz; do not use with actual speakers unless intended')
    a=p.parse_args()
    probe(a.rate,a.buffer,a.blocks,a.tone)
