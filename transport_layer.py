"""
Transport Layer Implementation
Level 3: Reliable Transport

This module implements:
- Transport segment format with sequence numbers
- ACK/NACK mechanism
- Timeout retransmission
- Flow control (Stop-and-Wait ARQ)
- Sliding window protocol (Go-Back-N)

Segment Format:
+----------+----------+--------+--------+------------+
| Seq Num  | Ack Num  | Flags  | Length |   Payload  |
| (16 bits)| (16 bits)| (8 bits)|(16 bits)| (variable)|
+----------+----------+--------+--------+------------+

Flags:
- ACK (0x01): Acknowledgment
- NACK (0x02): Negative acknowledgment
- SYN (0x04): Synchronize
- FIN (0x08): Finish
- DATA (0x10): Data segment
"""

import struct
import time
import threading
from typing import List, Optional, Dict, Tuple, Callable
from queue import Queue, Empty
from dataclasses import dataclass

from network_layer import Host, NetworkFrame, StarTopology


# =============================================================================
# Constants
# =============================================================================

# Flags
FLAG_ACK = 0x01
FLAG_NACK = 0x02
FLAG_SYN = 0x04
FLAG_FIN = 0x08
FLAG_DATA = 0x10

# Default parameters
DEFAULT_TIMEOUT = 1.0  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_WINDOW_SIZE = 4


# =============================================================================
# Transport Segment
# =============================================================================

@dataclass
class TransportSegment:
    """
    Transport layer segment with reliability features.

    Header format (7 bytes total):
    - Sequence number: 2 bytes (0-65535)
    - Acknowledgment number: 2 bytes (0-65535)
    - Flags: 1 byte
    - Payload length: 2 bytes
    - Payload: variable
    """
    seq_num: int
    ack_num: int
    flags: int
    payload: bytes

    HEADER_SIZE = 7

    def to_bytes(self) -> bytes:
        """Serialize segment to bytes."""
        header = struct.pack('>HHBH',
                            self.seq_num,
                            self.ack_num,
                            self.flags,
                            len(self.payload))
        return header + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> 'TransportSegment':
        """Deserialize segment from bytes."""
        if len(data) < cls.HEADER_SIZE:
            raise ValueError("Segment too short")

        seq_num, ack_num, flags, length = struct.unpack('>HHBH', data[:cls.HEADER_SIZE])
        payload = data[cls.HEADER_SIZE:cls.HEADER_SIZE + length]

        return cls(seq_num=seq_num, ack_num=ack_num, flags=flags, payload=payload)

    def is_ack(self) -> bool:
        return bool(self.flags & FLAG_ACK)

    def is_nack(self) -> bool:
        return bool(self.flags & FLAG_NACK)

    def is_syn(self) -> bool:
        return bool(self.flags & FLAG_SYN)

    def is_fin(self) -> bool:
        return bool(self.flags & FLAG_FIN)

    def is_data(self) -> bool:
        return bool(self.flags & FLAG_DATA)

    def __repr__(self):
        flags_str = []
        if self.is_ack(): flags_str.append('ACK')
        if self.is_nack(): flags_str.append('NACK')
        if self.is_syn(): flags_str.append('SYN')
        if self.is_fin(): flags_str.append('FIN')
        if self.is_data(): flags_str.append('DATA')
        return (f"Segment(seq={self.seq_num}, ack={self.ack_num}, "
                f"flags=[{','.join(flags_str)}], len={len(self.payload)})")


# =============================================================================
# Reliable Transport (Stop-and-Wait ARQ)
# =============================================================================

class ReliableTransport:
    """
    Stop-and-Wait ARQ protocol implementation.

    Features:
    - Sequence numbers for ordering
    - ACK/NACK for acknowledgment
    - Timeout retransmission
    - Guaranteed delivery
    """

    def __init__(self, host: Host,
                 timeout: float = DEFAULT_TIMEOUT,
                 max_retries: int = DEFAULT_MAX_RETRIES):
        """
        Initialize reliable transport.

        Args:
            host: Network layer host
            timeout: Retransmission timeout in seconds
            max_retries: Maximum retransmission attempts
        """
        self.host = host
        self.timeout = timeout
        self.max_retries = max_retries

        # Sequence numbers
        self.send_seq = 0
        self.recv_seq = 0

        # Statistics
        self.stats = {
            'segments_sent': 0,
            'segments_received': 0,
            'acks_sent': 0,
            'acks_received': 0,
            'retransmissions': 0,
            'timeouts': 0
        }

        # Callbacks
        self.on_receive: Optional[Callable[[bytes, str], None]] = None

        # Install receive handler on host
        self.host.on_receive = self._handle_receive

        # Pending ACKs
        self._pending_ack: Dict[int, threading.Event] = {}
        self._received_ack_num: Optional[int] = None

    def send(self, dst_mac: str, data: bytes) -> bool:
        """
        Send data reliably with acknowledgment.

        Args:
            dst_mac: Destination MAC address
            data: Data to send

        Returns:
            True if acknowledged, False if failed
        """
        # Create data segment
        segment = TransportSegment(
            seq_num=self.send_seq,
            ack_num=0,
            flags=FLAG_DATA,
            payload=data
        )

        # Create event for ACK
        ack_event = threading.Event()
        self._pending_ack[self.send_seq] = ack_event

        for attempt in range(self.max_retries):
            # Send segment
            self._send_segment(dst_mac, segment)
            self.stats['segments_sent'] += 1

            if attempt > 0:
                self.stats['retransmissions'] += 1

            # Wait for ACK with timeout
            if ack_event.wait(timeout=self.timeout):
                # ACK received
                if self._received_ack_num == self.send_seq:
                    self.stats['acks_received'] += 1
                    self.send_seq = (self.send_seq + 1) % 65536
                    del self._pending_ack[segment.seq_num]
                    return True
            else:
                self.stats['timeouts'] += 1

        # Failed after max retries
        if segment.seq_num in self._pending_ack:
            del self._pending_ack[segment.seq_num]
        return False

    def send_string(self, dst_mac: str, message: str) -> bool:
        """Send string message reliably."""
        return self.send(dst_mac, message.encode('utf-8'))

    def _send_segment(self, dst_mac: str, segment: TransportSegment):
        """Send transport segment through network layer."""
        self.host.send(dst_mac, segment.to_bytes())

    def _send_ack(self, dst_mac: str, ack_num: int):
        """Send acknowledgment."""
        ack = TransportSegment(
            seq_num=0,
            ack_num=ack_num,
            flags=FLAG_ACK,
            payload=b''
        )
        self._send_segment(dst_mac, ack)
        self.stats['acks_sent'] += 1

    def _send_nack(self, dst_mac: str, expected_seq: int):
        """Send negative acknowledgment."""
        nack = TransportSegment(
            seq_num=0,
            ack_num=expected_seq,
            flags=FLAG_NACK,
            payload=b''
        )
        self._send_segment(dst_mac, nack)

    def _handle_receive(self, frame: NetworkFrame):
        """Handle received network frame."""
        try:
            segment = TransportSegment.from_bytes(frame.payload)
            src_mac = str(frame.src_mac)

            if segment.is_ack():
                # Process ACK
                self._received_ack_num = segment.ack_num
                if segment.ack_num in self._pending_ack:
                    self._pending_ack[segment.ack_num].set()

            elif segment.is_nack():
                # Process NACK - will trigger retransmission
                pass

            elif segment.is_data():
                # Process data segment
                self.stats['segments_received'] += 1

                if segment.seq_num == self.recv_seq:
                    # Expected sequence - accept and ACK
                    self._send_ack(src_mac, segment.seq_num)
                    self.recv_seq = (self.recv_seq + 1) % 65536

                    # Deliver to application
                    if self.on_receive:
                        self.on_receive(segment.payload, src_mac)
                else:
                    # Out of order - send NACK
                    self._send_nack(src_mac, self.recv_seq)

        except Exception as e:
            pass  # Ignore malformed segments

    def get_stats(self) -> dict:
        """Get transport statistics."""
        return self.stats.copy()


# =============================================================================
# Sliding Window Protocol (Go-Back-N)
# =============================================================================

class SlidingWindowTransport:
    """
    Go-Back-N sliding window protocol.

    Features:
    - Multiple outstanding segments
    - Cumulative acknowledgments
    - Efficient pipeline transmission
    """

    def __init__(self, host: Host,
                 window_size: int = DEFAULT_WINDOW_SIZE,
                 timeout: float = DEFAULT_TIMEOUT,
                 max_retries: int = DEFAULT_MAX_RETRIES):
        """
        Initialize sliding window transport.

        Args:
            host: Network layer host
            window_size: Window size (max outstanding segments)
            timeout: Retransmission timeout
            max_retries: Maximum retries
        """
        self.host = host
        self.window_size = window_size
        self.timeout = timeout
        self.max_retries = max_retries

        # Sender state
        self.base = 0          # Oldest unacked sequence number
        self.next_seq = 0      # Next sequence number to send
        self.send_buffer: Dict[int, Tuple[TransportSegment, float, str]] = {}

        # Receiver state
        self.expected_seq = 0

        # Lock for thread safety
        self.lock = threading.Lock()

        # Statistics
        self.stats = {
            'segments_sent': 0,
            'segments_received': 0,
            'acks_sent': 0,
            'acks_received': 0,
            'retransmissions': 0,
            'timeouts': 0
        }

        # Callbacks
        self.on_receive: Optional[Callable[[bytes, str], None]] = None

        # Install handler
        self.host.on_receive = self._handle_receive

        # Timer thread
        self._timer_thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        """Start the transport layer."""
        self._running = True
        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()

    def stop(self):
        """Stop the transport layer."""
        self._running = False
        if self._timer_thread:
            self._timer_thread.join(timeout=1.0)

    def send(self, dst_mac: str, data: bytes) -> bool:
        """
        Send data using sliding window.

        Args:
            dst_mac: Destination MAC
            data: Data to send

        Returns:
            True if buffered for sending
        """
        with self.lock:
            # Check if window is full
            if self.next_seq >= self.base + self.window_size:
                return False

            # Create segment
            segment = TransportSegment(
                seq_num=self.next_seq,
                ack_num=0,
                flags=FLAG_DATA,
                payload=data
            )

            # Buffer and send
            self.send_buffer[self.next_seq] = (segment, time.time(), dst_mac)
            self._send_segment(dst_mac, segment)
            self.stats['segments_sent'] += 1
            self.next_seq = (self.next_seq + 1) % 65536

        return True

    def _timer_loop(self):
        """Timer loop for retransmissions."""
        while self._running:
            time.sleep(0.1)  # Check every 100ms

            with self.lock:
                now = time.time()
                for seq_num, (segment, send_time, dst_mac) in list(self.send_buffer.items()):
                    if now - send_time > self.timeout:
                        # Timeout - retransmit from this segment onwards (Go-Back-N)
                        self.stats['timeouts'] += 1
                        self._retransmit_from(seq_num)
                        break

    def _retransmit_from(self, start_seq: int):
        """Retransmit all segments from start_seq (Go-Back-N)."""
        for seq_num in range(start_seq, self.next_seq):
            if seq_num in self.send_buffer:
                segment, _, dst_mac = self.send_buffer[seq_num]
                self._send_segment(dst_mac, segment)
                self.send_buffer[seq_num] = (segment, time.time(), dst_mac)
                self.stats['retransmissions'] += 1

    def _send_segment(self, dst_mac: str, segment: TransportSegment):
        """Send segment through network layer."""
        self.host.send(dst_mac, segment.to_bytes())

    def _send_ack(self, dst_mac: str, ack_num: int):
        """Send cumulative ACK."""
        ack = TransportSegment(
            seq_num=0,
            ack_num=ack_num,
            flags=FLAG_ACK,
            payload=b''
        )
        self._send_segment(dst_mac, ack)
        self.stats['acks_sent'] += 1

    def _handle_receive(self, frame: NetworkFrame):
        """Handle received frame."""
        try:
            segment = TransportSegment.from_bytes(frame.payload)
            src_mac = str(frame.src_mac)

            with self.lock:
                if segment.is_ack():
                    # Cumulative ACK - remove all acked segments
                    self.stats['acks_received'] += 1
                    ack_num = segment.ack_num

                    # Remove all segments up to ack_num
                    to_remove = [s for s in self.send_buffer if s <= ack_num]
                    for s in to_remove:
                        del self.send_buffer[s]

                    # Advance base
                    self.base = (ack_num + 1) % 65536

                elif segment.is_data():
                    self.stats['segments_received'] += 1

                    if segment.seq_num == self.expected_seq:
                        # Expected - deliver and advance
                        if self.on_receive:
                            self.on_receive(segment.payload, src_mac)
                        self.expected_seq = (self.expected_seq + 1) % 65536

                    # Send ACK for last correctly received
                    self._send_ack(src_mac, (self.expected_seq - 1) % 65536)

        except Exception:
            pass

    def get_stats(self) -> dict:
        """Get statistics."""
        return self.stats.copy()


# =============================================================================
# Transport Connection
# =============================================================================

class TransportConnection:
    """
    Higher-level connection abstraction.

    Provides stream-like interface over reliable transport.
    """

    def __init__(self, local_host: Host, remote_mac: str,
                 protocol: str = 'stop-and-wait'):
        """
        Create transport connection.

        Args:
            local_host: Local host
            remote_mac: Remote MAC address
            protocol: 'stop-and-wait' or 'sliding-window'
        """
        self.local_host = local_host
        self.remote_mac = remote_mac

        if protocol == 'sliding-window':
            self.transport = SlidingWindowTransport(local_host)
            self.transport.start()
        else:
            self.transport = ReliableTransport(local_host)

        self.receive_queue = Queue()
        self.transport.on_receive = self._on_receive

    def _on_receive(self, data: bytes, src_mac: str):
        """Handle received data."""
        if src_mac == self.remote_mac:
            self.receive_queue.put(data)

    def send(self, data: bytes) -> bool:
        """Send data."""
        return self.transport.send(self.remote_mac, data)

    def send_string(self, message: str) -> bool:
        """Send string."""
        return self.send(message.encode('utf-8'))

    def receive(self, timeout: float = None) -> Optional[bytes]:
        """Receive data."""
        try:
            return self.receive_queue.get(timeout=timeout)
        except Empty:
            return None

    def receive_string(self, timeout: float = None) -> Optional[str]:
        """Receive string."""
        data = self.receive(timeout)
        return data.decode('utf-8') if data else None

    def close(self):
        """Close connection."""
        if isinstance(self.transport, SlidingWindowTransport):
            self.transport.stop()

    def get_stats(self) -> dict:
        """Get statistics."""
        return self.transport.get_stats()


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Transport Layer Demo - Level 3: Reliable Transport")
    print("=" * 70)

    # Test Transport Segment
    print("\n1. Transport Segment Test:")
    segment = TransportSegment(
        seq_num=42,
        ack_num=0,
        flags=FLAG_DATA,
        payload=b"Hello, reliable transport!"
    )
    print(f"   Original: {segment}")

    data = segment.to_bytes()
    print(f"   Serialized: {len(data)} bytes")

    parsed = TransportSegment.from_bytes(data)
    print(f"   Parsed: {parsed}")
    print(f"   Payload match: {segment.payload == parsed.payload}")

    # Test ACK segment
    print("\n2. ACK Segment Test:")
    ack = TransportSegment(
        seq_num=0,
        ack_num=42,
        flags=FLAG_ACK,
        payload=b''
    )
    print(f"   ACK segment: {ack}")
    print(f"   Is ACK: {ack.is_ack()}")
    print(f"   Is DATA: {ack.is_data()}")

    # Test Reliable Transport
    print("\n3. Stop-and-Wait ARQ Test:")
    topology = StarTopology(num_hosts=2)
    host1 = topology.get_host("00:00:00:00:00:01")
    host2 = topology.get_host("00:00:00:00:00:02")

    # Create transport layers
    transport1 = ReliableTransport(host1, timeout=0.5)
    transport2 = ReliableTransport(host2, timeout=0.5)

    received_messages = []

    def on_receive(data: bytes, src_mac: str):
        received_messages.append(data.decode('utf-8'))

    transport2.on_receive = on_receive

    # Send messages
    print("   Sending 3 messages from Host1 to Host2...")
    for i in range(3):
        success = transport1.send_string("00:00:00:00:00:02", f"Message {i+1}")
        print(f"   Message {i+1}: {'Sent and ACKed' if success else 'Failed'}")

    # Process any remaining frames
    for _ in range(10):
        frame = host2.get_received()
        if frame:
            transport2._handle_receive(frame)

    print(f"\n   Received messages: {received_messages}")

    # Statistics
    print("\n4. Transport Statistics:")
    print(f"   Host1 (sender): {transport1.get_stats()}")
    print(f"   Host2 (receiver): {transport2.get_stats()}")

    # Test connection abstraction
    print("\n5. Transport Connection Test:")
    topology2 = StarTopology(num_hosts=2)
    h1 = topology2.get_host("00:00:00:00:00:01")
    h2 = topology2.get_host("00:00:00:00:00:02")

    conn1 = TransportConnection(h1, "00:00:00:00:00:02")
    conn2 = TransportConnection(h2, "00:00:00:00:00:01")

    # Send and receive
    conn1.send_string("Hello from connection 1!")

    # Process
    for _ in range(5):
        frame = h2.get_received()
        if frame:
            conn2.transport._handle_receive(frame)

    # Check received
    msg = conn2.receive(timeout=0.1)
    if msg:
        print(f"   Received via connection: {msg.decode('utf-8')}")

    conn1.close()
    conn2.close()

    print("\n" + "=" * 70)
