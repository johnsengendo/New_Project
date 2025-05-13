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
        "tcp",       # Only capture TCP (RTMP runs over TCP)
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
    Stream the specified WAV audio file via FFmpeg over RTMP.
    """
    ffmpeg_cmd = [
        "ffmpeg",
        "-loglevel", "info",
        "-stats",
        "-re",
        "-stream_loop", str(loops),
        "-i", input_file,
        "-vn",                      # disable video
        "-t", str(duration),
        "-c:a", "aac",              # encode as AAC
        "-ar", "44100",             # sample rate
        "-ac", "1",                 # mono audio
        "-f", "flv",                # FLV container for RTMP
        rtmp_url
    ]
    subprocess.run(ffmpeg_cmd, check=True)


def main():
    input_audio = "video/audio.wav"  # Your downloaded WAV file
    loops = 0
    duration = 120
    capture = True
    pids = []

    if capture:
        pids.append(start_capture("server-eth0", "pcap/server.pcap"))
        pids.append(start_capture("h6-eth0", "pcap/h6.pcap"))
        time.sleep(2)  # ensure tcpdump is running

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
