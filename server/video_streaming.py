#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import os
import time
import signal
import random

def start_capture(interface, outfile="pcap/server.pcap"):
    """
    Start packet capture on the given interface, filtering for RTMP (TCP port 1935).
    """
    cmd = [
        "tcpdump",
        "-U",
        "-s0",
        "-i", interface,
        "tcp", "port", "1935",
        "-w", outfile
    ]
    proc = subprocess.Popen(cmd)
    return proc.pid

def stop_capture(pids):
    """
    Stop all tcpdump processes via SIGINT.
    """
    for pid in pids:
        try:
            os.kill(pid, signal.SIGINT)
        except OSError as e:
            print(f"Error stopping capture (pid={pid}): {e}")

def stream_audio_segment(input_file, duration, rtmp_url):
    """
    Stream a segment of the WAV audio file for a specific duration over RTMP.
    """
    ffmpeg_cmd = [
        "ffmpeg",
        "-loglevel", "info",
        "-stats",
        "-re",
        "-i", input_file,
        "-t", str(duration),
        "-vn",
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "1",
        "-f", "flv",
        rtmp_url
    ]
    subprocess.run(ffmpeg_cmd, check=True)

def main():
    input_audio = "video/audio.wav"
    rtmp_url = "rtmp://localhost:1935/live/audio.flv"
    capture = True
    stream_duration = 20  # seconds
    max_duration = 600    # 10 minutes
    total_time = 0
    segment_count = 0
    pids = []

    if capture:
        pids.append(start_capture("server-eth0", "pcap/server.pcap"))
        pids.append(start_capture("h6-eth0", "pcap/h6.pcap"))
        time.sleep(2)  # Ensure tcpdump is running

    try:
        while total_time + stream_duration <= max_duration:
            print(f">> Streaming segment {segment_count + 1} for {stream_duration}s (Elapsed: {total_time}s)")
            stream_audio_segment(input_audio, stream_duration, rtmp_url)
            total_time += stream_duration
            segment_count += 1

            pause_duration = random.choice([2, 3, 5])
            if total_time + pause_duration <= max_duration:
                print(f">> Pausing for {pause_duration}s")
                time.sleep(pause_duration)
                total_time += pause_duration
            else:
                break

        print(">> Finished streaming for 10 minutes.")

    finally:
        if capture:
            stop_capture(pids)

if __name__ == "__main__":
    main()
