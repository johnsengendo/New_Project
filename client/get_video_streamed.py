#!/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import os
import signal
import time
import random

def start_capture():
    """
    Start capturing RTMP traffic on client-eth0.
    """
    proc = subprocess.Popen([
        "tcpdump", "-U", "-s0", "-i", "client-eth0",
        "tcp", "port", "1935",
        "-w", "pcap/client.pcap"
    ])
    return proc.pid

def stop_capture(pid):
    """
    Stop tcpdump process via SIGINT.
    """
    try:
        os.kill(pid, signal.SIGINT)
        print(">> Packet capture stopped.")
    except OSError as e:
        print(f"Error stopping capture: {e}")

def receive_audio_segment(output_file, duration):
    """
    Receive a chunk of audio stream using FFmpeg for a given duration.
    """
    cmd = [
        "ffmpeg",
        "-loglevel", "info",
        "-stats",
        "-i", "rtmp://10.0.0.1:1935/live/audio.flv",
        "-t", str(duration),
        "-vn",
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "1",
        "-f", "flv",
        output_file
    ]
    subprocess.run(cmd, check=True)

def get_audio_stream():
    """
    Main function to handle segmented audio stream reception.
    """
    capture_traffic = True
    stream_duration = 20  # seconds
    max_duration = 600    # 10 minutes
    total_time = 0
    segment_count = 0

    if capture_traffic:
        pid = start_capture()
        time.sleep(2)  # Ensure tcpdump is ready

    try:
        while total_time + stream_duration <= max_duration:
            segment_file = f"stream_output_segment{segment_count}.flv"
            print(f">> Receiving stream segment {segment_count + 1} for {stream_duration}s (Elapsed: {total_time}s)")
            receive_audio_segment(segment_file, stream_duration)
            total_time += stream_duration
            segment_count += 1

            pause_duration = random.choice([2, 3, 5])
            if total_time + pause_duration <= max_duration:
                print(f">> Pausing for {pause_duration}s")
                time.sleep(pause_duration)
                total_time += pause_duration
            else:
                break

        print(">> 10-minute audio stream complete.")

    finally:
        if capture_traffic:
            stop_capture(pid)

if __name__ == "__main__":
    get_audio_stream()
