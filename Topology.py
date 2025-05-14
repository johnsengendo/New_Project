
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import subprocess
import sys
import time
import threading
import signal

from comnetsemu.cli import CLI
from comnetsemu.net import Containernet, VNFManager
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.node import Controller

# Helper: add streaming container
def add_streaming_container(manager, name, role, image, shared_dir):
    return manager.addContainer(
        name, role, image, '',
        docker_args={
            'volumes': { shared_dir: {'bind': '/home/pcap/', 'mode': 'rw'} }
        }
    )

# Helper: start server inside container
def start_server():
    info('*** Starting streaming server\n')
    subprocess.run([
        'docker', 'exec', '-it', 'streaming_server',
        'bash', '-c', 'cd /home && python3 video_streaming.py'
    ])

# Helper: start client inside container
def start_client():
    info('*** Starting streaming client\n')
    subprocess.run([
        'docker', 'exec', '-it', 'streaming_client',
        'bash', '-c', 'cd /home && python3 get_video_streamed.py'
    ])

# Iperf server/client functions
def start_iperf_server(host, port=5001):
    info(f'*** Starting iperf server on {host.name}\n')
    host.cmd(f'iperf -s -p {port} -u &')

def start_iperf_client(host, server_ip, port=5001, bandwidth='10K', duration=120):
    info(f'*** Starting iperf client on {host.name} to {server_ip}\n')
    host.cmd(f'iperf -c {server_ip} -p {port} -u -b {bandwidth} -t {duration} &')

def stop_iperf_client(host):
    info(f'*** Stopping iperf on {host.name}\n')
    host.cmd('pkill iperf')

# Start tcpdump on an interface, return process
def capture_traffic(interface, pcap_file):
    info(f'*** Starting tcpdump on {interface} -> {pcap_file}\n')
    return subprocess.Popen([
        'tcpdump', '-i', interface, '-s', '1500', '-w', pcap_file
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Schedule dynamic netem events on middle link
def schedule_middle_link_events(intf, events):
    for ev in events:
        time.sleep(ev['delay'])
        cmd = ['tc', 'qdisc', 'change', 'dev', intf, 'root', 'netem']
        if 'rate' in ev:
            cmd += ['rate', f"{ev['rate']}mbit"]
        if 'loss' in ev:
            cmd += ['loss', f"{ev['loss']}%"]
        if 'delay_ms' in ev:
            cmd += ['delay', f"{ev['delay_ms']}ms"]
        info(f"*** At t+{ev['delay']}s: {' '.join(cmd)}\n")
        subprocess.call(cmd)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Audio streaming with dynamic middle-link events')
    parser.add_argument('--autotest', action='store_true', help='Run without CLI and exit')
    parser.add_argument('--bandwidth', type=int, default=10, help='Initial bw (Mbps)')
    parser.add_argument('--delay', type=int, default=5, help='Initial delay (ms)')
    args = parser.parse_args()

    # Prepare pcap directory
    base_dir = os.path.abspath(os.path.dirname(__file__))
    pcap_dir = os.path.join(base_dir, 'pcap')
    os.makedirs(pcap_dir, exist_ok=True)

    setLogLevel('info')
    net = Containernet(controller=Controller, link=TCLink, xterms=False)
    mgr = VNFManager(net)

    info('*** Adding controller\n')
    net.addController('c0')

    info('*** Creating hosts\n')
    server = net.addDockerHost('server', dimage='dev_test', ip='10.0.0.1', docker_args={'hostname': 'server'})
    client = net.addDockerHost('client', dimage='dev_test', ip='10.0.0.2', docker_args={'hostname': 'client'})
    h1 = net.addHost('h1', ip='10.0.0.3')
    h2 = net.addHost('h2', ip='10.0.0.4')
    h3 = net.addHost('h3', ip='10.0.0.5')
    h4 = net.addHost('h4', ip='10.0.0.7')
    h5 = net.addHost('h5', ip='10.0.0.8')
    h6 = net.addHost('h6', ip='10.0.0.6')

    info('*** Adding switches and links\n')
    s1 = net.addSwitch('s1')
    s2 = net.addSwitch('s2')
    net.addLink(s1, server)
    net.addLink(s1, h1)
    mid = net.addLink(s1, s2, bw=args.bandwidth, delay=f"{args.delay}ms")
    net.addLink(s2, client)
    net.addLink(s2, h2)
    net.addLink(s1, h3)
    net.addLink(s2, h6)
    net.addLink(s1, h4)
    net.addLink(s2, h5)

    intf1 = mid.intf1.name
    intf2 = mid.intf2.name
    info(f"*** Middle link: {intf1} <-> {intf2}\n")

    info('*** Starting network\n')
    net.start()

    # Basic connectivity test
    info('*** Ping test from client to server\n')
    print(client.cmd('ping -c 3 10.0.0.1'))

    # Add streaming containers
    streaming_server = add_streaming_container(mgr, 'streaming_server', 'server', 'streaming_server_image', pcap_dir)
    streaming_client = add_streaming_container(mgr, 'streaming_client', 'client', 'streaming_client_image', pcap_dir)

    # Start tcpdump on both sides of middle link
    ts = time.strftime('%Y%m%d-%H%M%S')
    pcap1 = os.path.join(pcap_dir, f'mid_{intf1}_{ts}.pcap')
    pcap2 = os.path.join(pcap_dir, f'mid_{intf2}_{ts}.pcap')
    dump1 = capture_traffic(intf1, pcap1)
    dump2 = capture_traffic(intf2, pcap2)

    # Start servers and clients
    threading.Thread(target=start_iperf_server, args=(h5,)).start()
    threading.Thread(target=start_iperf_server, args=(h6,)).start()

    # Iperf background traffic
    def bg_traffic():
        time.sleep(2)
        start_iperf_client(h3, '10.0.0.6')
        start_iperf_client(h4, '10.0.0.8')
        time.sleep(20)
        stop_iperf_client(h3)
        stop_iperf_client(h4)
    threading.Thread(target=bg_traffic, daemon=True).start()

    # Streaming threads
    server_t = threading.Thread(target=start_server)
    client_t = threading.Thread(target=start_client)
    server_t.start()
    client_t.start()

    # Define and start dynamic middle-link events
    events = [
        {'delay': 5,  'rate': 5},
        {'delay': 15, 'loss': 10},
        {'delay': 25, 'delay_ms': 50},
        {'delay': 35, 'rate': 20, 'loss': 0}
    ]
    threading.Thread(target=schedule_middle_link_events, args=(intf1, events), daemon=True).start()

    try:
        if not args.autotest:
            CLI(net)
        else:
            server_t.join()
            client_t.join()
            time.sleep(max(e['delay'] for e in events) + 5)
    except KeyboardInterrupt:
        info('*** Interrupted by user\n')
    finally:
        # Stop captures
        for p in (dump1, dump2):
            if p:
                p.send_signal(signal.SIGINT)
                p.wait()
        info('*** Cleared captures\n')

        # Cleanup
        mgr.removeContainer('streaming_server')
        mgr.removeContainer('streaming_client')
        net.stop()
        mgr.stop()
