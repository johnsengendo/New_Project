#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import os
import time
import signal


def start_capture(interface, outfile="pcap/server.pcap"):
    """
    Start packet capture on the given interface, filtering for RTMP (TCP port 1935).
    """
    cmd = [
        "tcpdump",
        "-U",        # unbuffered packet writes
        "-s0",       # capture full packet
        "-i", interface,
        "tcp",       # only TCP (RTMP)
        "port", "1935",
        "-w", outfile
    ]
    proc = subprocess.Popen(cmd)
    return proc.pid


def stop_capture(pids):
    """
    Stop tcpdump processes by sending SIGINT to each pid.
    """
    for pid in pids:
        try:
            os.kill(pid, signal.SIGINT)
        except OSError as e:
            print(f"Error stopping capture (pid={pid}): {e}")


def stream_audio(input_file,
                 loops=0,
                 duration=120,
                 rtmp_url="rtmp://localhost:1935/live/audio.flv"):
    """
    Stream the specified audio file (e.g., WAV) via FFmpeg over RTMP.

    - `-re`: read input at native rate
    - `-stream_loop`: number of loops (0=no loop)
    - `-i`: input file (wav, mp3, etc.)
    - `-vn`: disable video
    - `-c:a aac`: encode to AAC
    - `-ar 44100`: sampling rate
    - `-ac 1`: mono
    - `-t`: stream duration
    - `-f flv`: RTMP format
    """
    ffmpeg_cmd = [
        "ffmpeg",
        "-loglevel", "info",
        "-stats",
        "-re",
        "-stream_loop", str(loops),
        "-i", input_file,
        "-vn",
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "1",
        "-t", str(duration),
        "-f", "flv",
        rtmp_url
    ]
    subprocess.run(ffmpeg_cmd, check=True)


def main():
    # Path to your downloaded WAV file
    input_audio = "audio/downloaded_track.wav"
    loops = 0        # 0 = no loop, -1 = infinite
    duration = 120   # seconds to stream
    capture = True
    pids = []

    if capture:
        pids.append(start_capture("server-eth0"))
        pids.append(start_capture("h6-eth0"))
        time.sleep(2)  # wait for tcpdump

    try:
        stream_audio(
            input_file=input_audio,
            loops=loops,
            duration=duration,
            rtmp_url="rtmp://localhost:1935/live/audio.flv"
        )
    finally:
        if capture:
            stop_capture(pids)


if __name__ == "__main__":
    main()
