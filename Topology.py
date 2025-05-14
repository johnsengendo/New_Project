#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Importing required modules
import argparse
import os
import subprocess
import sys
import time
import threading
import signal
import random

# Importing necessary functionalities from ComNetsEmu and Mininet
from comnetsemu.cli import CLI, spawnXtermDocker
from comnetsemu.net import Containernet, VNFManager
from mininet.link import TCLink
from mininet.log import info, setLogLevel
from mininet.node import Controller

# Function to add streaming container
def add_streaming_container(manager, name, role, image, shared_dir):
    return manager.addContainer(
        name, role, image, '', docker_args={
            'volumes': {
                shared_dir: {'bind': '/home/pcap/', 'mode': 'rw'}
            }
        }
    )

# Function to start server
def start_server():
    info('*** Starting streaming server\n')
    subprocess.run(['docker', 'exec', '-it', 'streaming_server', 'bash', '-c', 'cd /home && python3 video_streaming.py'])

# Function to start client
def start_client():
    info('*** Starting streaming client\n')
    subprocess.run(['docker', 'exec', '-it', 'streaming_client', 'bash', '-c', 'cd /home && python3 get_video_streamed.py'])

# Function to start iperf server
def start_iperf_server(host, port=5001):
    info(f'*** Starting iperf server on {host.name}\n')
    host.cmd(f'iperf -s -p {port} -u &')  # Use UDP for more disruptive traffic

# Function to start iperf client with specific bandwidth
def start_iperf_client(host, server_ip, port=5001, bandwidth='10K', duration=10):
    info(f'*** Starting iperf client on {host.name} to {server_ip} with bandwidth {bandwidth}\n')
    host.cmd(f'iperf -c {server_ip} -p {port} -u -b {bandwidth} -t {duration} &')  # Use UDP with specified bandwidth

# Function to stop iperf client
def stop_iperf_client(host):
    info(f'*** Stopping iperf on {host.name}\n')
    host.cmd('pkill iperf')

# New function to create traffic spike
def create_traffic_spike(source_host, target_ip, port=5001, base_bw='5M', spike_bw='80M', spike_duration=5, base_duration=10):
    """Create a traffic spike pattern with base and spike traffic levels"""
    info(f'*** Creating traffic spike from {source_host.name} to {target_ip}\n')
    # Start with base bandwidth
    start_iperf_client(source_host, target_ip, port, bandwidth=base_bw, duration=base_duration)
    time.sleep(base_duration)
    
    # Create a spike
    start_iperf_client(source_host, target_ip, port, bandwidth=spike_bw, duration=spike_duration)
    time.sleep(spike_duration)
    
    # Return to base bandwidth
    start_iperf_client(source_host, target_ip, port, bandwidth=base_bw, duration=base_duration)
    time.sleep(base_duration)

# New function to manage multiple spikes with a traffic pattern
def create_traffic_pattern(hosts_pairs, duration=60):
    """Create a pattern with exactly 2 traffic spikes"""
    info('*** Starting traffic pattern generation\n')
    
    start_time = time.time()
    end_time = start_time + duration
    
    # Define spike points - just 2 spikes, each 5 seconds long
    spike_points = [
        {'time': 15, 'duration': 5, 'bw': '90M'},  # First spike at 15 seconds
        {'time': 40, 'duration': 5, 'bw': '90M'},  # Second spike at 40 seconds
    ]
    
    # Start base traffic - low level background traffic
    for src_host, dest_ip, port in hosts_pairs:
        start_iperf_client(src_host, dest_ip, port, bandwidth='8M', duration=duration)
    
    # Wait and create the two spikes at the appropriate times
    for spike in spike_points:
        # Calculate how long to wait until this spike
        wait_time = spike['time'] - (time.time() - start_time)
        if wait_time > 0:
            time.sleep(wait_time)
        
        # Choose a host pair for this spike
        host_pair = hosts_pairs[0]  # Use the first pair consistently
        src_host, dest_ip, port = host_pair
        
        # Create spike
        info(f'*** Creating spike: {spike["bw"]} for {spike["duration"]}s\n')
        
        # Stop current traffic
        stop_iperf_client(src_host)
        time.sleep(0.5)
        
        # Start spike traffic
        start_iperf_client(src_host, dest_ip, port, bandwidth=spike['bw'], duration=spike['duration'])
        
        # Wait for spike duration
        time.sleep(spike['duration'])
        
        # Return to baseline traffic
        stop_iperf_client(src_host)
        time.sleep(0.5)
        start_iperf_client(src_host, dest_ip, port, bandwidth='8M', duration=duration)
    
    # Wait until the end of the total duration
    remaining_time = end_time - time.time()
    if remaining_time > 0:
        time.sleep(remaining_time)

# Function to capture traffic on a specific link
def capture_traffic(interface, pcap_file):
    info(f'*** Starting tcpdump capture on {interface} to {pcap_file}\n')
    # Create a more generic filter to capture all traffic on the interface
    # We can process and filter the pcap file later if needed
    # Using -s 1500 to capture full packets (MTU size)
    tcpdump_process = subprocess.Popen(['tcpdump', '-i', interface, '-s', '1500', '-w', pcap_file],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return tcpdump_process

# Main execution starts here
if __name__ == '__main__':
    # Setting up command-line argument parsing
    parser = argparse.ArgumentParser(description='Audio streaming application.')
    parser.add_argument('--autotest', dest='autotest', action='store_const', const=True, default=False,
                        help='Enables automatic testing of the topology and closes the streaming application.')
    parser.add_argument('--bandwidth', dest='bandwidth', type=int, default=100,
                        help='Bandwidth in Mbps for the middle link. Default is 100.')
    parser.add_argument('--delay', dest='delay', type=int, default=5,
                        help='Delay in milliseconds for the middle link. Default is 5.')
    parser.add_argument('--duration', dest='duration', type=int, default=60,
                        help='Duration of traffic pattern in seconds. Default is 60.')
    args = parser.parse_args()

    # Setting values for bandwidth and delay
    bandwidth = args.bandwidth  # bandwidth in Mbps
    delay = args.delay         # delay in milliseconds
    duration = args.duration   # duration in seconds
    autotest = args.autotest

    # Preparing a shared folder to store the pcap files
    script_directory = os.path.abspath(os.path.dirname(__file__))
    shared_directory = os.path.join(script_directory, 'pcap')

    # Creating the shared directory if it doesn't exist
    if not os.path.exists(shared_directory):
        os.makedirs(shared_directory)

    # Configuring the logging level
    setLogLevel('info')

    # Creating a network with Containernet (a Docker-compatible Mininet fork) and a virtual network function manager
    net = Containernet(controller=Controller, link=TCLink, xterms=False)
    mgr = VNFManager(net)

    # Adding a controller to the network
    info('*** Add controller\n')
    net.addController('c0')

    # Setting up Docker hosts as network nodes
    info('*** Creating hosts\n')
    server = net.addDockerHost(
        'server', dimage='dev_test', ip='10.0.0.1', docker_args={'hostname': 'server'}
    )
    client = net.addDockerHost(
        'client', dimage='dev_test', ip='10.0.0.2', docker_args={'hostname': 'client'}
    )

    # Adding normal hosts
    h1 = net.addHost('h1', ip='10.0.0.3')
    h2 = net.addHost('h2', ip='10.0.0.4')
    h3 = net.addHost('h3', ip='10.0.0.5')
    h6 = net.addHost('h6', ip='10.0.0.6')
    h4 = net.addHost('h4', ip='10.0.0.7')
    h5 = net.addHost('h5', ip='10.0.0.8')

    # Adding switches and links to the network
    info('*** Adding switches and links\n')
    switch1 = net.addSwitch('s1')
    switch2 = net.addSwitch('s2')

    # Add links with specific names to make identification easier
    net.addLink(switch1, server)
    net.addLink(switch1, h1)
    # Increase middle link capacity to handle traffic spikes
    middle_link = net.addLink(switch1, switch2, bw=bandwidth, delay=f'{delay}ms')
    net.addLink(switch2, client)
    net.addLink(switch2, h2)
    net.addLink(switch1, h3)
    net.addLink(switch2, h6)
    net.addLink(switch1, h4)
    net.addLink(switch2, h5)

    # Store the interface names for the middle link
    s1_middle_interface = middle_link.intf1.name
    s2_middle_interface = middle_link.intf2.name
    
    info(f'*** Middle link interfaces: {s1_middle_interface} <-> {s2_middle_interface}\n')

    # Starting the network
    info('\n*** Starting network\n')
    net.start()

    # Testing connectivity by pinging server from client
    info("*** Client host pings the server to test for connectivity: \n")
    reply = client.cmd("ping -c 5 10.0.0.1")
    print(reply)

    # Adding containers
    streaming_server = add_streaming_container(mgr, 'streaming_server', 'server', 'streaming_server_image', shared_directory)
    streaming_client = add_streaming_container(mgr, 'streaming_client', 'client', 'streaming_client_image', shared_directory)

    # Path to save the pcap file
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    pcap_file = os.path.join(shared_directory, f'audio_capture_{timestamp}.pcap')

    # Start capturing traffic on the middle link
    tcpdump_process = capture_traffic(s1_middle_interface, pcap_file)

    # Start iperf servers on multiple hosts
    start_iperf_server(h6, port=5001)
    start_iperf_server(h5, port=5002)
    start_iperf_server(h2, port=5003)

    # Define host pairs for traffic generation
    host_pairs = [
        (h3, '10.0.0.6', 5001),
        (h4, '10.0.0.8', 5002),
        (h1, '10.0.0.4', 5003)
    ]

    # Use a thread to create traffic pattern
    def run_traffic_pattern():
        time.sleep(2)  # Short delay before starting traffic
        create_traffic_pattern(host_pairs, duration=duration)

    traffic_thread = threading.Thread(target=run_traffic_pattern)
    traffic_thread.daemon = True
    traffic_thread.start()

    # Creating threads to run the server and client
    server_thread = threading.Thread(target=start_server)
    client_thread = threading.Thread(target=start_client)

    # Starting the threads
    server_thread.start()
    client_thread.start()

    try:
        # If not in autotest mode, start an interactive CLI
        if not autotest:
            CLI(net)
        else:
            # Wait for specified duration in autotest mode
            info(f"\n*** Running traffic pattern for {duration} seconds\n")
            time.sleep(duration + 5)  # Add extra time for cleanup
    except KeyboardInterrupt:
        info("\n*** Caught keyboard interrupt, stopping experiment\n")
    finally:
        # Stop tcpdump capture
        if tcpdump_process:
            info("\n*** Stopping tcpdump capture\n")
            tcpdump_process.send_signal(signal.SIGINT)
            tcpdump_process.wait()
            info(f"*** Traffic capture saved to {pcap_file}\n")

        # Stop all iperf clients
        for host in [h1, h3, h4]:
            stop_iperf_client(host)

        # Cleanup: removing containers and stopping the network and VNF manager
        info('\n*** Cleaning up\n')
        mgr.removeContainer('streaming_server')
        mgr.removeContainer('streaming_client')
        net.stop()
        mgr.stop()
