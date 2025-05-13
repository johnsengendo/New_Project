#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import os
import time
import signal


def start_capture(interface, outfile="pcap/server.pcap"):
    """
    Start packet capture on the given interface, filtering for RTMP (TCP port 1935).
    Writes raw packets to `outfile`.
    """
    cmd = [
        "tcpdump",
        "-U",        # Make packet writes unbuffered
        "-s0",       # Capture full packet
        "-i", interface,
        "tcp",        # Only capture TCP (RTMP runs over TCP)
        "port", "1935",
        "-w", outfile
    ]
    proc = subprocess.Popen(cmd)
    return proc.pid


def stop_capture(pids):
    """
    Stop all tcpdump processes given by pid list via SIGINT.
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
    Stream the specified audio file via FFmpeg over RTMP.

    - `-re`: read input at native frame rate
    - `-stream_loop`: number of loops (0 = no loop)
    - `-vn`: disable video stream
    - `-c:a aac`: encode audio as AAC
    - `-ar 44100`: set audio sampling rate
    - `-ac 1`: single audio channel
    - `-t`: limit duration (seconds)
    - `-f flv`: output format for RTMP
    """
    ffmpeg_cmd = [
        "ffmpeg",
        "-loglevel", "info",
        "-stats",
        "-re",
        "-stream_loop", str(loops),
        "-i", input_file,
        "-vn",
        "-t", str(duration),
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "1",
        "-f", "flv",
        rtmp_url
    ]
    subprocess.run(ffmpeg_cmd, check=True)


def main():
    # Path to your audio file
    input_audio = "video/track.mp3"
    # Number of times to loop (-1 for infinite, 0 for no loop)
    loops = 0
    # Capture duration in seconds (None to disable)
    duration = 120

    capture = True
    pids = []

    if capture:
        # start capture on both interfaces
        pids.append(start_capture("server-eth0"))
        pids.append(start_capture("h6-eth0"))
        time.sleep(2)  # ensure tcpdump is up

    # Start streaming audio
    try:
        stream_audio(
            input_file=input_audio,
            loops=loops,
            duration=duration,
            rtmp_url="rtmp://localhost:1935/live/audio.flv"
        )
    finally:
        # Cleanup packet capture
        if capture:
            stop_capture(pids)


if __name__ == "__main__":
    main()
