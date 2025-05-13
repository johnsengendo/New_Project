#!/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import os
import signal
import time


def start_capture(interface="client-eth0", outfile="pcap/client.pcap"):
    """
    Start capturing network traffic on the specified interface, filtering for RTMP (TCP port 1935).
    """
    cmd = [
        "tcpdump",
        "-U",        # Unbuffered packet writes
        "-s0",       # Capture full packet
        "-i", interface,
        "tcp",       # Only TCP (RTMP)
        "port", "1935",
        "-w", outfile
    ]
    proc = subprocess.Popen(cmd)
    return proc.pid


def stop_capture(pid):
    """
    Stop the tcpdump process by sending SIGINT.
    """
    try:
        os.kill(pid, signal.SIGINT)
        print("Capture stopped successfully.")
    except OSError as e:
        print(f"Error stopping capture: {e}")


def get_audio_stream():
    """
    Capture and save an RTMP audio stream to a local file.
    """
    out_file = "stream_output.flv"
    capture_traffic = True

    if capture_traffic:
        pid = start_capture()
        time.sleep(2)  # ensure tcpdump is running

    ffmpeg_command = [
        "ffmpeg",
        "-loglevel", "info",
        "-stats",
        "-i", "rtmp://10.0.0.1:1935/live/audio.flv",
        "-t", "120",
        "-vn",               # disable video
        "-c:a", "copy",    # copy audio stream
        out_file
    ]
    subprocess.run(ffmpeg_command, check=True)

    if capture_traffic:
        stop_capture(pid)


if __name__ == "__main__":
    get_audio_stream()
