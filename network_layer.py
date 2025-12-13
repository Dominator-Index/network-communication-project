"""
Network Layer Implementation
Level 2: Multi-Host Communication

This module implements:
- MAC addressing mechanism
- Network frame format with addressing
- Host class with physical layer integration
- Switch class with MAC learning and forwarding
- Star topology support

Frame Format (with addressing):
+----------+--------+--------+--------+------------+---------+----------+
| Preamble | Dst MAC| Src MAC| Length |   Payload  | Checksum| Postamble|
| (8 bits) |(48 bits)|(48 bits)|(16 bits)| (variable)|  (8 bits)| (8 bits) |
+----------+--------+--------+--------+------------+---------+----------+
"""

import re
from typing import List, Dict, Optional, Tuple, Callable
from queue import Queue
import numpy as np

from cable import Cable
from physical_layer import (
    PhysicalLink, bytes_to_bits, bits_to_bytes,
    int_to_bits, bits_to_int, modulate_ook, demodulate_ook,
    calculate_adaptive_threshold, SAMPLES_PER_BIT
)
from data_link_layer import (
    Frame, PREAMBLE, POSTAMBLE, compute_checksum,
    FrameError, ChecksumError, PreambleError
)


# =============================================================================
# Constants
# =============================================================================

MAC_BROADCAST = "FF:FF:FF:FF:FF:FF"


# =============================================================================
# MAC Address
# =============================================================================

class MACAddress:
    """
    Represents a 48-bit MAC address.

    Format: XX:XX:XX:XX:XX:XX (6 bytes, hex notation)
    """

    PATTERN = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')

    def __init__(self, address: str):
        """
        Create MAC address from string.

        Args:
            address: MAC address string (e.g., "00:11:22:33:44:55")

        Raises:
            ValueError: If address format is invalid
        """
        if not self.PATTERN.match(address):
            raise ValueError(f"Invalid MAC address format: {address}")
        self.address = address.upper()

    def to_bits(self) -> List[int]:
        """
        Convert MAC address to 48-bit sequence.

        Returns:
            List of 48 bits (MSB first)
        """
        bits = []
        parts = self.address.split(':')
        for part in parts:
            value = int(part, 16)
            for i in range(7, -1, -1):
                bits.append((value >> i) & 1)
        return bits

    def to_bytes(self) -> bytes:
        """Convert MAC address to 6 bytes."""
        parts = self.address.split(':')
        return bytes(int(p, 16) for p in parts)

    @classmethod
    def from_bits(cls, bits: List[int]) -> 'MACAddress':
        """
        Reconstruct MAC from 48-bit sequence.

        Args:
            bits: List of 48 bits

        Returns:
            MACAddress object
        """
        if len(bits) < 48:
            raise ValueError("Need 48 bits for MAC address")

        parts = []
        for i in range(0, 48, 8):
            byte_bits = bits[i:i+8]
            value = 0
            for bit in byte_bits:
                value = (value << 1) | bit
            parts.append(f"{value:02X}")

        return cls(':'.join(parts))

    @classmethod
    def from_bytes(cls, data: bytes) -> 'MACAddress':
        """Create MAC from 6 bytes."""
        if len(data) < 6:
            raise ValueError("Need 6 bytes for MAC address")
        parts = [f"{b:02X}" for b in data[:6]]
        return cls(':'.join(parts))

    def is_broadcast(self) -> bool:
        """Check if this is a broadcast address."""
        return self.address == MAC_BROADCAST

    def __eq__(self, other):
        if isinstance(other, MACAddress):
            return self.address == other.address
        elif isinstance(other, str):
            return self.address == other.upper()
        return False

    def __hash__(self):
        return hash(self.address)

    def __str__(self):
        return self.address

    def __repr__(self):
        return f"MACAddress('{self.address}')"


# =============================================================================
# Network Frame
# =============================================================================

class NetworkFrame:
    """
    Network layer frame with MAC addressing.

    Extends basic frame with source and destination MAC addresses.
    """

    def __init__(self, src_mac: str, dst_mac: str, payload: bytes):
        """
        Create network frame.

        Args:
            src_mac: Source MAC address
            dst_mac: Destination MAC address
            payload: Frame payload
        """
        self.src_mac = MACAddress(src_mac) if isinstance(src_mac, str) else src_mac
        self.dst_mac = MACAddress(dst_mac) if isinstance(dst_mac, str) else dst_mac
        self.payload = payload
        self.checksum = compute_checksum(payload)

    def to_bits(self) -> List[int]:
        """
        Serialize frame to bit sequence.

        Format:
        [Preamble][Dst MAC][Src MAC][Length][Payload][Checksum][Postamble]
        """
        payload_bits = bytes_to_bits(self.payload)
        length_bits = int_to_bits(len(payload_bits), 16)
        checksum_bits = int_to_bits(self.checksum, 8)

        frame_bits = (
            PREAMBLE +                      # 8 bits
            self.dst_mac.to_bits() +        # 48 bits
            self.src_mac.to_bits() +        # 48 bits
            length_bits +                   # 16 bits
            payload_bits +                  # variable
            checksum_bits +                 # 8 bits
            POSTAMBLE                       # 8 bits
        )

        return frame_bits

    def to_bytes(self) -> bytes:
        """Serialize frame to bytes (for higher layer use)."""
        return (
            self.dst_mac.to_bytes() +
            self.src_mac.to_bytes() +
            len(self.payload).to_bytes(2, 'big') +
            self.payload +
            bytes([self.checksum])
        )

    @classmethod
    def from_bits(cls, bits: List[int], verify: bool = True) -> 'NetworkFrame':
        """
        Deserialize frame from bit sequence.

        Args:
            bits: Received bit sequence
            verify: Whether to verify checksum

        Returns:
            NetworkFrame object

        Raises:
            FrameError: If frame parsing fails
            ChecksumError: If checksum verification fails
        """
        # Find preamble
        preamble_idx = cls._find_preamble(bits)
        if preamble_idx < 0:
            raise PreambleError("Preamble not found")

        pos = preamble_idx + len(PREAMBLE)

        # Extract destination MAC (48 bits)
        if pos + 48 > len(bits):
            raise FrameError("Frame too short for destination MAC")
        dst_mac = MACAddress.from_bits(bits[pos:pos+48])
        pos += 48

        # Extract source MAC (48 bits)
        if pos + 48 > len(bits):
            raise FrameError("Frame too short for source MAC")
        src_mac = MACAddress.from_bits(bits[pos:pos+48])
        pos += 48

        # Extract length (16 bits)
        if pos + 16 > len(bits):
            raise FrameError("Frame too short for length field")
        payload_length = bits_to_int(bits[pos:pos+16])
        pos += 16

        # Extract payload
        if pos + payload_length > len(bits):
            raise FrameError("Frame too short for payload")
        payload_bits = bits[pos:pos+payload_length]
        pos += payload_length

        # Extract checksum (8 bits)
        if pos + 8 > len(bits):
            raise FrameError("Frame too short for checksum")
        received_checksum = bits_to_int(bits[pos:pos+8])
        pos += 8

        # Convert payload to bytes
        payload = bits_to_bytes(payload_bits)

        # Verify checksum
        if verify:
            computed = compute_checksum(payload)
            if computed != received_checksum:
                raise ChecksumError(
                    f"Checksum mismatch: computed={computed}, received={received_checksum}"
                )

        frame = cls(src_mac.address, dst_mac.address, payload)
        frame.checksum = received_checksum
        return frame

    @staticmethod
    def _find_preamble(bits: List[int]) -> int:
        """Find preamble position in bit sequence."""
        for i in range(len(bits) - len(PREAMBLE) + 1):
            if bits[i:i+len(PREAMBLE)] == PREAMBLE:
                return i
        return -1

    def __repr__(self):
        return (f"NetworkFrame(src={self.src_mac}, dst={self.dst_mac}, "
                f"len={len(self.payload)})")


# =============================================================================
# Host
# =============================================================================

class Host:
    """
    Network host with physical layer integration.

    Each host has a unique MAC address and connects to the network
    through a physical cable.
    """

    def __init__(self, mac: str, name: str = None):
        """
        Create a host.

        Args:
            mac: MAC address string
            name: Optional host name for display
        """
        self.mac = MACAddress(mac)
        self.name = name or f"Host-{mac[-5:]}"
        self.receive_buffer = Queue()
        self.cable: Optional[Cable] = None
        self.physical_link: Optional[PhysicalLink] = None
        self.switch: Optional['Switch'] = None
        self.port_id: Optional[int] = None

        # Callbacks
        self.on_receive: Optional[Callable[[NetworkFrame], None]] = None

        # Statistics
        self.stats = {
            'frames_sent': 0,
            'frames_received': 0,
            'bytes_sent': 0,
            'bytes_received': 0
        }

    def connect_to_switch(self, switch: 'Switch', port_id: int,
                          cable_params: dict = None):
        """
        Connect this host to a switch port.

        Args:
            switch: Switch to connect to
            port_id: Port ID on the switch
            cable_params: Optional cable parameters
        """
        self.switch = switch
        self.port_id = port_id

        # Create cable with default or custom parameters
        params = cable_params or {
            'length': 10,
            'attenuation': 0.05,
            'noise_level': 0.01,
            'debug_mode': False
        }
        self.cable = Cable(**params)
        self.physical_link = PhysicalLink(self.cable)

        # Register with switch
        switch._register_host(self, port_id)

    def send(self, dst_mac: str, payload: bytes) -> bool:
        """
        Send data to another host.

        Args:
            dst_mac: Destination MAC address
            payload: Data to send

        Returns:
            True if frame was sent
        """
        if not self.switch:
            print(f"{self.name}: Not connected to network")
            return False

        # Create frame
        frame = NetworkFrame(self.mac.address, dst_mac, payload)

        # Modulate and transmit through cable
        bits = frame.to_bits()
        signal = modulate_ook(bits)
        received_signal = self.cable.transmit(signal)

        # Switch processes the received signal
        self.switch._process_signal_from_port(self.port_id, received_signal)

        self.stats['frames_sent'] += 1
        self.stats['bytes_sent'] += len(payload)

        return True

    def send_string(self, dst_mac: str, message: str) -> bool:
        """Send string message to another host."""
        return self.send(dst_mac, message.encode('utf-8'))

    def receive_frame(self, frame: NetworkFrame):
        """
        Receive a frame (called by switch).

        Args:
            frame: Received network frame
        """
        # Check if frame is for this host or broadcast
        if (frame.dst_mac == self.mac or
            frame.dst_mac.is_broadcast()):
            self.receive_buffer.put(frame)
            self.stats['frames_received'] += 1
            self.stats['bytes_received'] += len(frame.payload)

            # Call receive callback if set
            if self.on_receive:
                self.on_receive(frame)

    def receive_signal(self, signal: np.ndarray) -> Optional[NetworkFrame]:
        """
        Receive and demodulate signal.

        Args:
            signal: Received analog signal

        Returns:
            Parsed frame if successful
        """
        # Demodulate
        threshold = calculate_adaptive_threshold(signal)
        bits = demodulate_ook(signal, threshold=threshold)

        # Parse frame
        try:
            frame = NetworkFrame.from_bits(bits)
            self.receive_frame(frame)
            return frame
        except (FrameError, ChecksumError) as e:
            return None

    def get_received(self, timeout: float = None) -> Optional[NetworkFrame]:
        """
        Get next received frame from buffer.

        Args:
            timeout: Timeout in seconds (None for non-blocking)

        Returns:
            NetworkFrame or None
        """
        try:
            if timeout is None:
                return self.receive_buffer.get_nowait()
            else:
                return self.receive_buffer.get(timeout=timeout)
        except:
            return None

    def get_all_received(self) -> List[NetworkFrame]:
        """Get all received frames from buffer."""
        frames = []
        while not self.receive_buffer.empty():
            try:
                frames.append(self.receive_buffer.get_nowait())
            except:
                break
        return frames

    def get_stats(self) -> dict:
        """Get host statistics."""
        return self.stats.copy()

    def __repr__(self):
        return f"Host({self.name}, MAC={self.mac})"


# =============================================================================
# Switch
# =============================================================================

class Switch:
    """
    Layer 2 switch with MAC learning and forwarding.

    Implements:
    - MAC address learning
    - Forwarding based on MAC table
    - Broadcasting for unknown destinations
    - Physical layer transmission using Cable
    """

    def __init__(self, num_ports: int = 8, name: str = "Switch"):
        """
        Create a switch.

        Args:
            num_ports: Number of switch ports
            name: Switch name for display
        """
        self.num_ports = num_ports
        self.name = name

        # Port management
        self.ports: Dict[int, Cable] = {}           # port_id -> Cable
        self.hosts: Dict[int, Host] = {}            # port_id -> Host
        self.port_cables: Dict[int, Cable] = {}     # port_id -> Cable (switch side)

        # MAC table: MAC address -> port_id
        self.mac_table: Dict[str, int] = {}

        # Statistics
        self.stats = {
            'frames_received': 0,
            'frames_forwarded': 0,
            'frames_broadcast': 0,
            'mac_table_updates': 0
        }

        # Logging
        self.log_enabled = True
        self.log_buffer: List[str] = []

    def _register_host(self, host: Host, port_id: int):
        """
        Register a host on a port (internal).

        Args:
            host: Host to register
            port_id: Port ID
        """
        if port_id >= self.num_ports:
            raise ValueError(f"Invalid port ID: {port_id}")

        self.hosts[port_id] = host
        self.ports[port_id] = host.cable

        # Create cable for switch-to-host direction
        self.port_cables[port_id] = Cable(
            length=10,
            attenuation=0.05,
            noise_level=0.01,
            debug_mode=False
        )

        self._log(f"Host {host.name} connected to port {port_id}")

    def _process_signal_from_port(self, src_port: int, signal: np.ndarray):
        """
        Process received signal from a port.

        Args:
            src_port: Source port ID
            signal: Received analog signal
        """
        # Demodulate signal
        threshold = calculate_adaptive_threshold(signal)
        bits = demodulate_ook(signal, threshold=threshold)

        # Parse frame
        try:
            frame = NetworkFrame.from_bits(bits)
            self._handle_frame(frame, src_port)
        except (FrameError, ChecksumError) as e:
            self._log(f"Frame error from port {src_port}: {e}")

    def _handle_frame(self, frame: NetworkFrame, src_port: int):
        """
        Handle received frame.

        Args:
            frame: Received network frame
            src_port: Source port ID
        """
        self.stats['frames_received'] += 1

        # Learn source MAC
        src_mac = str(frame.src_mac)
        if src_mac not in self.mac_table or self.mac_table[src_mac] != src_port:
            self.mac_table[src_mac] = src_port
            self.stats['mac_table_updates'] += 1
            self._log(f"Learned MAC {src_mac} on port {src_port}")

        # Determine forwarding
        dst_mac = str(frame.dst_mac)

        if frame.dst_mac.is_broadcast():
            # Broadcast to all ports except source
            self._broadcast(frame, exclude_port=src_port)
        elif dst_mac in self.mac_table:
            # Forward to known port
            dst_port = self.mac_table[dst_mac]
            self._forward_to_port(frame, dst_port)
        else:
            # Unknown destination - broadcast
            self._log(f"Unknown destination {dst_mac}, broadcasting")
            self._broadcast(frame, exclude_port=src_port)

    def _forward_to_port(self, frame: NetworkFrame, port_id: int):
        """
        Forward frame to specific port.

        Args:
            frame: Frame to forward
            port_id: Destination port ID
        """
        if port_id not in self.hosts:
            self._log(f"Port {port_id} not connected")
            return

        host = self.hosts[port_id]

        # Modulate frame and transmit through switch-side cable
        bits = frame.to_bits()
        signal = modulate_ook(bits)

        # Transmit through cable
        cable = self.port_cables[port_id]
        received_signal = cable.transmit(signal)

        # Host receives signal
        host.receive_signal(received_signal)

        self.stats['frames_forwarded'] += 1
        self._log(f"Forwarded frame to port {port_id} ({host.name})")

    def _broadcast(self, frame: NetworkFrame, exclude_port: int):
        """
        Broadcast frame to all ports except source.

        Args:
            frame: Frame to broadcast
            exclude_port: Port to exclude (source port)
        """
        for port_id in self.hosts:
            if port_id != exclude_port:
                self._forward_to_port(frame, port_id)

        self.stats['frames_broadcast'] += 1

    def _log(self, message: str):
        """Log message if logging is enabled."""
        if self.log_enabled:
            self.log_buffer.append(f"[{self.name}] {message}")

    def get_mac_table(self) -> Dict[str, int]:
        """Get MAC address table."""
        return self.mac_table.copy()

    def get_stats(self) -> dict:
        """Get switch statistics."""
        return self.stats.copy()

    def get_logs(self) -> List[str]:
        """Get log messages."""
        return self.log_buffer.copy()

    def clear_logs(self):
        """Clear log buffer."""
        self.log_buffer.clear()

    def print_mac_table(self):
        """Print MAC table."""
        print(f"\n{self.name} MAC Table:")
        print("-" * 40)
        if not self.mac_table:
            print("  (empty)")
        else:
            for mac, port in self.mac_table.items():
                host = self.hosts.get(port)
                host_name = host.name if host else "Unknown"
                print(f"  {mac} -> Port {port} ({host_name})")
        print("-" * 40)

    def __repr__(self):
        return f"Switch({self.name}, ports={self.num_ports})"


# =============================================================================
# Network Topology Helper
# =============================================================================

class StarTopology:
    """
    Helper class for creating star topology networks.
    """

    def __init__(self, switch: Switch = None, num_hosts: int = 0):
        """
        Create star topology.

        Args:
            switch: Existing switch or None to create new
            num_hosts: Number of hosts to create automatically
        """
        self.switch = switch or Switch(num_ports=max(8, num_hosts))
        self.hosts: Dict[str, Host] = {}  # MAC -> Host

        if num_hosts > 0:
            self._create_hosts(num_hosts)

    def _create_hosts(self, num_hosts: int):
        """Create and connect hosts."""
        for i in range(num_hosts):
            mac = f"00:00:00:00:00:{i+1:02X}"
            host = Host(mac, name=f"Host{i+1}")
            host.connect_to_switch(self.switch, port_id=i)
            self.hosts[mac] = host

    def add_host(self, mac: str, name: str = None, port_id: int = None) -> Host:
        """
        Add a host to the topology.

        Args:
            mac: MAC address
            name: Optional host name
            port_id: Optional port ID (auto-assigned if None)

        Returns:
            Created Host
        """
        if port_id is None:
            port_id = len(self.hosts)

        host = Host(mac, name=name)
        host.connect_to_switch(self.switch, port_id=port_id)
        self.hosts[mac] = host
        return host

    def get_host(self, mac: str) -> Optional[Host]:
        """Get host by MAC address."""
        return self.hosts.get(mac.upper())

    def get_all_hosts(self) -> List[Host]:
        """Get all hosts."""
        return list(self.hosts.values())

    def send_message(self, src_mac: str, dst_mac: str, message: str) -> bool:
        """
        Send message between hosts.

        Args:
            src_mac: Source MAC
            dst_mac: Destination MAC
            message: Message string

        Returns:
            True if sent
        """
        src_host = self.get_host(src_mac)
        if not src_host:
            print(f"Source host {src_mac} not found")
            return False

        return src_host.send_string(dst_mac, message)


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Network Layer Demo - Level 2: Multi-Host Communication")
    print("=" * 70)

    # Test MAC Address
    print("\n1. MAC Address Test:")
    mac = MACAddress("00:11:22:33:44:55")
    print(f"   MAC: {mac}")
    print(f"   Bits: {mac.to_bits()[:16]}... (first 16 bits)")

    bits = mac.to_bits()
    recovered = MACAddress.from_bits(bits)
    print(f"   Recovered: {recovered}")
    print(f"   Match: {mac == recovered}")

    # Test Network Frame
    print("\n2. Network Frame Test:")
    frame = NetworkFrame(
        src_mac="00:00:00:00:00:01",
        dst_mac="00:00:00:00:00:02",
        payload=b"Hello from Host 1"
    )
    print(f"   Frame: {frame}")

    bits = frame.to_bits()
    print(f"   Frame size: {len(bits)} bits")

    parsed = NetworkFrame.from_bits(bits)
    print(f"   Parsed: {parsed}")
    print(f"   Payload match: {frame.payload == parsed.payload}")

    # Test Star Topology
    print("\n3. Star Topology Test:")
    topology = StarTopology(num_hosts=3)
    print(f"   Created {len(topology.hosts)} hosts connected to switch")

    for mac, host in topology.hosts.items():
        print(f"   - {host.name}: {mac}")

    # Test communication
    print("\n4. Multi-Host Communication Test:")

    host1 = topology.get_host("00:00:00:00:00:01")
    host2 = topology.get_host("00:00:00:00:00:02")
    host3 = topology.get_host("00:00:00:00:00:03")

    # Host 1 sends to Host 2
    print("\n   Host1 -> Host2: 'Hello from Host1'")
    host1.send_string("00:00:00:00:00:02", "Hello from Host1")

    # Check what Host2 received
    received = host2.get_all_received()
    for frame in received:
        print(f"   Host2 received: '{frame.payload.decode()}'")
        print(f"   From: {frame.src_mac}")

    # Host 2 sends to Host 3
    print("\n   Host2 -> Host3: 'Hello from Host2'")
    host2.send_string("00:00:00:00:00:03", "Hello from Host2")

    received = host3.get_all_received()
    for frame in received:
        print(f"   Host3 received: '{frame.payload.decode()}'")

    # Host 3 sends to Host 1
    print("\n   Host3 -> Host1: 'Hello from Host3'")
    host3.send_string("00:00:00:00:00:01", "Hello from Host3")

    received = host1.get_all_received()
    for frame in received:
        print(f"   Host1 received: '{frame.payload.decode()}'")

    # Show MAC table
    topology.switch.print_mac_table()

    # Show statistics
    print("\n5. Statistics:")
    print(f"   Switch stats: {topology.switch.get_stats()}")
    for mac, host in topology.hosts.items():
        print(f"   {host.name} stats: {host.get_stats()}")

    # Show switch logs
    print("\n6. Switch Logs:")
    for log in topology.switch.get_logs()[:10]:
        print(f"   {log}")

    print("\n" + "=" * 70)
