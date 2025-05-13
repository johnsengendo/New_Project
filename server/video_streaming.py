#!/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import os
import signal
import time

def start_capture():
    """
    Start capturing RTMP traffic (TCP port 1935) on client-eth0.
    """
    proc = subprocess.Popen([
        "tcpdump", "-U", "-s0", "-i", "client-eth0",
        "tcp", "port", "1935",
        "-w", "pcap/client.pcap"
    ])
    return proc.pid

def stop_capture(pid):
    """
    Stop the tcpdump process gracefully by sending SIGINT.
    """
    try:
        os.kill(pid, signal.SIGINT)
        print("Capture stopped successfully.")
    except OSError as e:
        print(f"Error stopping capture: {e}")

def get_audio_stream():
    """
    Main function to handle audio-only streaming.
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
        "-i", "rtmp://10.0.0.1:1935/live/audio.flv",  # audio endpoint
        "-t", "120",            # limit to 120 seconds
        "-vn",                  # disable video
        "-c:a", "aac",          # re-encode audio as AAC
        "-ar", "44100",         # sampling rate
        "-ac", "1",             # mono
        "-f", "flv",
        out_file
    ]
    subprocess.run(ffmpeg_command, check=True)

    if capture_traffic:
        stop_capture(pid)

if __name__ == "__main__":
    get_audio_stream()
