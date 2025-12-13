"""
Concurrency Implementation
Level 3: Multi-threaded Network Processing

This module implements:
- ThreadedHost: Host with concurrent send/receive threads
- ThreadedSwitch: Switch with thread pool for multi-port processing
- Thread-safe message queues
- Non-blocking I/O mode

Features:
- Concurrent message handling
- No blocking between hosts
- Scalable to high traffic volumes
"""

import threading
import time
from typing import Dict, List, Optional, Callable
from queue import Queue, Empty
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from cable import Cable
from physical_layer import (
    PhysicalLink, modulate_ook, demodulate_ook,
    calculate_adaptive_threshold, SAMPLES_PER_BIT
)
from network_layer import (
    Host, Switch, MACAddress, NetworkFrame,
    PREAMBLE, POSTAMBLE
)
from data_link_layer import FrameError, ChecksumError


# =============================================================================
# Thread-safe Queue Wrapper
# =============================================================================

class SafeQueue:
    """Thread-safe queue with additional utilities."""

    def __init__(self, maxsize: int = 0):
        self.queue = Queue(maxsize=maxsize)
        self.lock = threading.Lock()

    def put(self, item, timeout: float = None):
        """Put item in queue."""
        try:
            self.queue.put(item, timeout=timeout)
            return True
        except:
            return False

    def get(self, timeout: float = None):
        """Get item from queue."""
        try:
            return self.queue.get(timeout=timeout)
        except Empty:
            return None

    def get_nowait(self):
        """Get item without waiting."""
        try:
            return self.queue.get_nowait()
        except Empty:
            return None

    def empty(self) -> bool:
        """Check if queue is empty."""
        return self.queue.empty()

    def size(self) -> int:
        """Get queue size."""
        return self.queue.qsize()


# =============================================================================
# Threaded Host
# =============================================================================

class ThreadedHost:
    """
    Network host with concurrent send/receive threads.

    Features:
    - Separate send and receive threads
    - Non-blocking operations
    - Thread-safe message queues
    """

    def __init__(self, mac: str, name: str = None):
        """
        Create threaded host.

        Args:
            mac: MAC address
            name: Optional host name
        """
        self.mac = MACAddress(mac)
        self.name = name or f"THost-{mac[-5:]}"

        # Queues
        self.send_queue = SafeQueue(maxsize=100)
        self.receive_queue = SafeQueue(maxsize=100)

        # Connection
        self.cable: Optional[Cable] = None
        self.physical_link: Optional[PhysicalLink] = None
        self.switch: Optional['ThreadedSwitch'] = None
        self.port_id: Optional[int] = None

        # Threads
        self.send_thread: Optional[threading.Thread] = None
        self.receive_thread: Optional[threading.Thread] = None
        self._running = False

        # Callbacks
        self.on_receive: Optional[Callable[[NetworkFrame], None]] = None

        # Statistics
        self.stats = {
            'frames_sent': 0,
            'frames_received': 0,
            'send_queue_full': 0,
            'receive_errors': 0
        }
        self.stats_lock = threading.Lock()

    def connect_to_switch(self, switch: 'ThreadedSwitch', port_id: int,
                          cable_params: dict = None):
        """Connect host to switch."""
        self.switch = switch
        self.port_id = port_id

        params = cable_params or {
            'length': 10,
            'attenuation': 0.05,
            'noise_level': 0.01,
            'debug_mode': False
        }
        self.cable = Cable(**params)
        self.physical_link = PhysicalLink(self.cable)

        switch._register_host(self, port_id)

    def start(self):
        """Start send/receive threads."""
        if self._running:
            return

        self._running = True

        self.send_thread = threading.Thread(
            target=self._send_loop,
            name=f"{self.name}-send",
            daemon=True
        )
        self.receive_thread = threading.Thread(
            target=self._receive_loop,
            name=f"{self.name}-receive",
            daemon=True
        )

        self.send_thread.start()
        self.receive_thread.start()

    def stop(self):
        """Stop threads."""
        self._running = False
        if self.send_thread:
            self.send_thread.join(timeout=1.0)
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)

    def send(self, dst_mac: str, payload: bytes) -> bool:
        """
        Queue data for sending (non-blocking).

        Args:
            dst_mac: Destination MAC
            payload: Data to send

        Returns:
            True if queued successfully
        """
        frame = NetworkFrame(self.mac.address, dst_mac, payload)

        if self.send_queue.put(frame, timeout=0.1):
            return True
        else:
            with self.stats_lock:
                self.stats['send_queue_full'] += 1
            return False

    def send_string(self, dst_mac: str, message: str) -> bool:
        """Send string message."""
        return self.send(dst_mac, message.encode('utf-8'))

    def receive(self, timeout: float = None) -> Optional[NetworkFrame]:
        """
        Get received frame (blocking or non-blocking).

        Args:
            timeout: Wait timeout (None for non-blocking)

        Returns:
            Received frame or None
        """
        return self.receive_queue.get(timeout=timeout)

    def receive_nowait(self) -> Optional[NetworkFrame]:
        """Get received frame without waiting."""
        return self.receive_queue.get_nowait()

    def _send_loop(self):
        """Send thread main loop."""
        while self._running:
            frame = self.send_queue.get(timeout=0.1)
            if frame:
                self._transmit_frame(frame)

    def _transmit_frame(self, frame: NetworkFrame):
        """Actually transmit frame through physical layer."""
        if not self.switch:
            return

        bits = frame.to_bits()
        signal = modulate_ook(bits)
        received_signal = self.cable.transmit(signal)

        # Send to switch
        self.switch._queue_signal(self.port_id, received_signal)

        with self.stats_lock:
            self.stats['frames_sent'] += 1

    def _receive_loop(self):
        """Receive thread main loop."""
        # This thread is mainly for processing callbacks
        # Actual receiving is done via _receive_signal called by switch
        while self._running:
            time.sleep(0.01)

    def _receive_signal(self, signal: np.ndarray):
        """
        Receive signal from switch (called by switch thread).

        Args:
            signal: Received analog signal
        """
        try:
            threshold = calculate_adaptive_threshold(signal)
            bits = demodulate_ook(signal, threshold=threshold)
            frame = NetworkFrame.from_bits(bits)

            if frame.dst_mac == self.mac or frame.dst_mac.is_broadcast():
                self.receive_queue.put(frame)

                with self.stats_lock:
                    self.stats['frames_received'] += 1

                if self.on_receive:
                    self.on_receive(frame)

        except (FrameError, ChecksumError):
            with self.stats_lock:
                self.stats['receive_errors'] += 1

    def get_stats(self) -> dict:
        """Get host statistics."""
        with self.stats_lock:
            return self.stats.copy()

    def __repr__(self):
        return f"ThreadedHost({self.name}, MAC={self.mac})"


# =============================================================================
# Threaded Switch
# =============================================================================

class ThreadedSwitch:
    """
    Multi-threaded switch with concurrent port processing.

    Features:
    - Thread pool for parallel port processing
    - Non-blocking frame forwarding
    - Concurrent MAC table updates
    """

    def __init__(self, num_ports: int = 8, num_workers: int = 4,
                 name: str = "TSwitch"):
        """
        Create threaded switch.

        Args:
            num_ports: Number of switch ports
            num_workers: Number of worker threads
            name: Switch name
        """
        self.num_ports = num_ports
        self.num_workers = num_workers
        self.name = name

        # Port management
        self.hosts: Dict[int, ThreadedHost] = {}
        self.port_cables: Dict[int, Cable] = {}

        # Signal queue for incoming frames
        self.signal_queue = SafeQueue(maxsize=1000)

        # MAC table with lock
        self.mac_table: Dict[str, int] = {}
        self.mac_table_lock = threading.RLock()

        # Thread pool
        self.executor: Optional[ThreadPoolExecutor] = None
        self.process_thread: Optional[threading.Thread] = None
        self._running = False

        # Statistics
        self.stats = {
            'frames_received': 0,
            'frames_forwarded': 0,
            'frames_broadcast': 0,
            'queue_overflows': 0
        }
        self.stats_lock = threading.Lock()

    def _register_host(self, host: ThreadedHost, port_id: int):
        """Register host on port."""
        if port_id >= self.num_ports:
            raise ValueError(f"Invalid port ID: {port_id}")

        self.hosts[port_id] = host
        self.port_cables[port_id] = Cable(
            length=10,
            attenuation=0.05,
            noise_level=0.01,
            debug_mode=False
        )

    def start(self):
        """Start switch processing."""
        if self._running:
            return

        self._running = True

        # Create thread pool
        self.executor = ThreadPoolExecutor(max_workers=self.num_workers)

        # Start processing thread
        self.process_thread = threading.Thread(
            target=self._process_loop,
            name=f"{self.name}-process",
            daemon=True
        )
        self.process_thread.start()

    def stop(self):
        """Stop switch processing."""
        self._running = False

        if self.process_thread:
            self.process_thread.join(timeout=1.0)

        if self.executor:
            self.executor.shutdown(wait=False)

    def _queue_signal(self, src_port: int, signal: np.ndarray):
        """Queue incoming signal for processing."""
        if not self.signal_queue.put((src_port, signal), timeout=0.1):
            with self.stats_lock:
                self.stats['queue_overflows'] += 1

    def _process_loop(self):
        """Main processing loop."""
        while self._running:
            item = self.signal_queue.get(timeout=0.1)
            if item:
                src_port, signal = item
                # Submit to thread pool
                self.executor.submit(self._process_signal, src_port, signal)

    def _process_signal(self, src_port: int, signal: np.ndarray):
        """Process incoming signal (runs in worker thread)."""
        try:
            # Demodulate
            threshold = calculate_adaptive_threshold(signal)
            bits = demodulate_ook(signal, threshold=threshold)
            frame = NetworkFrame.from_bits(bits)

            self._handle_frame(frame, src_port)

        except (FrameError, ChecksumError):
            pass

    def _handle_frame(self, frame: NetworkFrame, src_port: int):
        """Handle frame (thread-safe)."""
        with self.stats_lock:
            self.stats['frames_received'] += 1

        # Update MAC table
        src_mac = str(frame.src_mac)
        with self.mac_table_lock:
            self.mac_table[src_mac] = src_port

        # Determine forwarding
        dst_mac = str(frame.dst_mac)

        if frame.dst_mac.is_broadcast():
            self._broadcast(frame, exclude_port=src_port)
        else:
            with self.mac_table_lock:
                dst_port = self.mac_table.get(dst_mac)

            if dst_port is not None:
                self._forward_to_port(frame, dst_port)
            else:
                self._broadcast(frame, exclude_port=src_port)

    def _forward_to_port(self, frame: NetworkFrame, port_id: int):
        """Forward frame to specific port."""
        if port_id not in self.hosts:
            return

        host = self.hosts[port_id]
        cable = self.port_cables[port_id]

        # Transmit
        bits = frame.to_bits()
        signal = modulate_ook(bits)
        received_signal = cable.transmit(signal)

        # Deliver to host
        host._receive_signal(received_signal)

        with self.stats_lock:
            self.stats['frames_forwarded'] += 1

    def _broadcast(self, frame: NetworkFrame, exclude_port: int):
        """Broadcast to all ports except source."""
        for port_id in self.hosts:
            if port_id != exclude_port:
                self._forward_to_port(frame, port_id)

        with self.stats_lock:
            self.stats['frames_broadcast'] += 1

    def get_mac_table(self) -> Dict[str, int]:
        """Get MAC table (thread-safe)."""
        with self.mac_table_lock:
            return self.mac_table.copy()

    def get_stats(self) -> dict:
        """Get switch statistics."""
        with self.stats_lock:
            return self.stats.copy()

    def print_mac_table(self):
        """Print MAC table."""
        print(f"\n{self.name} MAC Table:")
        print("-" * 40)
        table = self.get_mac_table()
        if not table:
            print("  (empty)")
        else:
            for mac, port in table.items():
                host = self.hosts.get(port)
                host_name = host.name if host else "Unknown"
                print(f"  {mac} -> Port {port} ({host_name})")
        print("-" * 40)


# =============================================================================
# Concurrent Network
# =============================================================================

class ConcurrentNetwork:
    """
    High-level abstraction for concurrent network.

    Manages multiple threaded hosts connected to a threaded switch.
    """

    def __init__(self, num_hosts: int = 4, num_workers: int = 4):
        """
        Create concurrent network.

        Args:
            num_hosts: Number of hosts
            num_workers: Worker threads for switch
        """
        self.switch = ThreadedSwitch(
            num_ports=max(8, num_hosts),
            num_workers=num_workers,
            name="CSwitch"
        )
        self.hosts: Dict[str, ThreadedHost] = {}

        # Create hosts
        for i in range(num_hosts):
            mac = f"00:00:00:00:00:{i+1:02X}"
            host = ThreadedHost(mac, name=f"CHost{i+1}")
            host.connect_to_switch(self.switch, port_id=i)
            self.hosts[mac] = host

    def start(self):
        """Start all components."""
        self.switch.start()
        for host in self.hosts.values():
            host.start()

    def stop(self):
        """Stop all components."""
        for host in self.hosts.values():
            host.stop()
        self.switch.stop()

    def get_host(self, mac: str) -> Optional[ThreadedHost]:
        """Get host by MAC."""
        return self.hosts.get(mac.upper())

    def broadcast_message(self, src_mac: str, message: str):
        """Broadcast message from a host to all others."""
        host = self.get_host(src_mac)
        if host:
            host.send_string("FF:FF:FF:FF:FF:FF", message)

    def get_all_stats(self) -> dict:
        """Get statistics from all components."""
        stats = {
            'switch': self.switch.get_stats(),
            'hosts': {}
        }
        for mac, host in self.hosts.items():
            stats['hosts'][host.name] = host.get_stats()
        return stats


# =============================================================================
# Load Test
# =============================================================================

def run_load_test(num_hosts: int = 4, messages_per_host: int = 10,
                  message_size: int = 50) -> dict:
    """
    Run concurrent load test.

    Args:
        num_hosts: Number of hosts
        messages_per_host: Messages each host sends
        message_size: Size of each message

    Returns:
        Test results
    """
    import string
    import random

    network = ConcurrentNetwork(num_hosts=num_hosts)
    network.start()

    # Give time to start
    time.sleep(0.1)

    hosts = list(network.hosts.values())
    start_time = time.time()

    # Send messages concurrently
    def send_messages(host: ThreadedHost):
        for i in range(messages_per_host):
            # Pick random destination
            dst_host = random.choice([h for h in hosts if h != host])
            message = ''.join(random.choices(string.ascii_letters, k=message_size))
            host.send_string(str(dst_host.mac), message)
            time.sleep(0.01)  # Small delay

    threads = []
    for host in hosts:
        t = threading.Thread(target=send_messages, args=(host,))
        threads.append(t)
        t.start()

    # Wait for all senders
    for t in threads:
        t.join()

    # Wait for processing
    time.sleep(0.5)

    end_time = time.time()
    elapsed = end_time - start_time

    # Collect stats
    stats = network.get_all_stats()
    network.stop()

    # Calculate metrics
    total_sent = sum(h['frames_sent'] for h in stats['hosts'].values())
    total_received = sum(h['frames_received'] for h in stats['hosts'].values())

    results = {
        'num_hosts': num_hosts,
        'messages_per_host': messages_per_host,
        'total_messages': num_hosts * messages_per_host,
        'total_sent': total_sent,
        'total_received': total_received,
        'elapsed_time': elapsed,
        'throughput': total_sent / elapsed if elapsed > 0 else 0,
        'switch_stats': stats['switch'],
        'host_stats': stats['hosts']
    }

    return results


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Concurrency Demo - Level 3: Multi-threaded Processing")
    print("=" * 70)

    # Basic threaded network test
    print("\n1. Basic Threaded Network Test:")
    network = ConcurrentNetwork(num_hosts=4)
    network.start()

    # Wait for startup
    time.sleep(0.1)

    host1 = network.get_host("00:00:00:00:00:01")
    host2 = network.get_host("00:00:00:00:00:02")
    host3 = network.get_host("00:00:00:00:00:03")
    host4 = network.get_host("00:00:00:00:00:04")

    # Send messages concurrently
    print("   Sending messages concurrently...")
    host1.send_string("00:00:00:00:00:02", "Hello from Host1 to Host2")
    host2.send_string("00:00:00:00:00:03", "Hello from Host2 to Host3")
    host3.send_string("00:00:00:00:00:04", "Hello from Host3 to Host4")
    host4.send_string("00:00:00:00:00:01", "Hello from Host4 to Host1")

    # Wait for processing
    time.sleep(0.5)

    # Check received
    print("\n   Received messages:")
    for host in [host1, host2, host3, host4]:
        while True:
            frame = host.receive_nowait()
            if frame:
                print(f"   {host.name}: '{frame.payload.decode()[:30]}...' from {frame.src_mac}")
            else:
                break

    # Show stats
    print("\n   Statistics:")
    stats = network.get_all_stats()
    print(f"   Switch: {stats['switch']}")
    for name, host_stats in stats['hosts'].items():
        print(f"   {name}: {host_stats}")

    network.stop()

    # Load test
    print("\n2. Load Test (4 hosts, 20 messages each):")
    results = run_load_test(num_hosts=4, messages_per_host=20, message_size=50)

    print(f"   Total messages: {results['total_messages']}")
    print(f"   Total sent: {results['total_sent']}")
    print(f"   Total received: {results['total_received']}")
    print(f"   Elapsed time: {results['elapsed_time']:.3f}s")
    print(f"   Throughput: {results['throughput']:.1f} frames/s")
    print(f"   Switch frames received: {results['switch_stats']['frames_received']}")
    print(f"   Switch frames forwarded: {results['switch_stats']['frames_forwarded']}")

    # Scalability test
    print("\n3. Scalability Test:")
    print("   Hosts | Messages | Sent | Received | Time(s) | Throughput")
    print("   " + "-" * 60)

    for num_hosts in [2, 4, 6, 8]:
        results = run_load_test(num_hosts=num_hosts, messages_per_host=10, message_size=30)
        print(f"   {num_hosts:5d} | {results['total_messages']:8d} | "
              f"{results['total_sent']:4d} | {results['total_received']:8d} | "
              f"{results['elapsed_time']:7.3f} | {results['throughput']:10.1f}")

    print("\n" + "=" * 70)
