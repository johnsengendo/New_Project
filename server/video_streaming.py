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


def stream_segment(input_file, duration, rtmp_url):
    """
    Launch ffmpeg to stream `input_file` for `duration` seconds.
    Returns the Popen object.
    """
    cmd = [
        "ffmpeg",
        "-loglevel", "info",
        "-stats",
        "-re",
        "-i", input_file,
        "-vn",
        "-t", str(duration),
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "1",
        "-f", "flv",
        rtmp_url
    ]
    return subprocess.Popen(cmd)


def main():
    input_audio = "video/audio.wav"
    rtmp_url = "rtmp://localhost:1935/live/audio.flv"

    # Define the sequence of streaming durations (in seconds)
    segments = [20, 20]
    # Pause length after each segment
    pause = 5

    # --- optional tcpdump capture setup ---
    capture = True
    pids = []
    if capture:
        pids.append(start_capture("server-eth0", "pcap/server.pcap"))
        pids.append(start_capture("h6-eth0",     "pcap/h6.pcap"))
        time.sleep(2)  # give tcpdump a moment to spin up

    try:
        for idx, seg_dur in enumerate(segments):
            print(f">> Starting stream segment #{idx+1} for {seg_dur}s")
            p = stream_segment(input_audio, seg_dur, rtmp_url)
            p.wait()  # block until ffmpeg finishes this segment

            # if this isn’t the last segment, pause
            if idx < len(segments) - 1:
                print(f">> Pausing stream for {pause}s")
                time.sleep(pause)

        # after the last segment, you could optionally add one more pause
        print(f">> Final pause for {pause}s before exit")
        time.sleep(pause)

    finally:
        if capture:
            stop_capture(pids)
            print(">> Packet capture stopped.")


if __name__ == "__main__":
    main()
