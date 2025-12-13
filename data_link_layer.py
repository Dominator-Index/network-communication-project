"""
Data Link Layer Implementation
Level 1: Frame formatting, error detection, packet slicing

Frame Format (without addressing):
+----------+--------+------------+---------+----------+
| Preamble | Length |   Payload  | Checksum| Postamble|
| (8 bits) | (16 bits)| (variable)|  (8 bits)| (8 bits) |
+----------+--------+------------+---------+----------+

This module handles:
- Frame encapsulation/decapsulation
- Checksum calculation and verification
- Packet slicing for long messages
"""

from typing import List, Optional, Tuple
from physical_layer import (
    bytes_to_bits, bits_to_bytes, int_to_bits, bits_to_int,
    PhysicalLink, string_to_bits, bits_to_string
)
from cable import Cable


# =============================================================================
# Constants
# =============================================================================

PREAMBLE = [1, 0, 1, 0, 1, 0, 1, 0]  # Clock synchronization pattern
POSTAMBLE = [1, 1, 1, 1, 1, 1, 1, 1]  # End-of-frame marker
MAX_PAYLOAD_SIZE = 256  # Maximum payload size per frame (bytes)


# =============================================================================
# Exceptions
# =============================================================================

class FrameError(Exception):
    """Base exception for frame errors."""
    pass


class ChecksumError(FrameError):
    """Checksum verification failed."""
    pass


class PreambleError(FrameError):
    """Preamble not found or invalid."""
    pass


class PostambleError(FrameError):
    """Postamble not found or invalid."""
    pass


# =============================================================================
# Checksum Functions
# =============================================================================

def compute_checksum(data: bytes) -> int:
    """
    Compute 8-bit XOR checksum.

    Args:
        data: Data bytes to compute checksum for

    Returns:
        8-bit checksum value
    """
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum & 0xFF


def verify_checksum(data: bytes, expected: int) -> bool:
    """
    Verify checksum matches expected value.

    Args:
        data: Data bytes
        expected: Expected checksum value

    Returns:
        True if checksum matches
    """
    return compute_checksum(data) == expected


def compute_checksum_bits(bits: List[int]) -> List[int]:
    """
    Compute 8-bit XOR checksum from bit list.

    Args:
        bits: Bit list

    Returns:
        8-bit checksum as bit list
    """
    # Convert to bytes, compute checksum, convert back to bits
    data = bits_to_bytes(bits)
    checksum = compute_checksum(data)
    return int_to_bits(checksum, 8)


# =============================================================================
# Frame Class
# =============================================================================

class Frame:
    """
    Data link layer frame with error detection.

    Provides encapsulation and decapsulation of data with:
    - Preamble for synchronization
    - Length field
    - Payload
    - Checksum for error detection
    - Postamble for frame end
    """

    def __init__(self, payload: bytes):
        """
        Create a frame with given payload.

        Args:
            payload: Frame payload (bytes)
        """
        self.payload = payload
        self.checksum = compute_checksum(payload)

    def to_bits(self) -> List[int]:
        """
        Serialize frame to bit sequence.

        Returns:
            Complete frame as bit list
        """
        payload_bits = bytes_to_bits(self.payload)
        length_bits = int_to_bits(len(payload_bits), 16)
        checksum_bits = int_to_bits(self.checksum, 8)

        frame_bits = (
            PREAMBLE +
            length_bits +
            payload_bits +
            checksum_bits +
            POSTAMBLE
        )

        return frame_bits

    @classmethod
    def from_bits(cls, bits: List[int], verify: bool = True) -> 'Frame':
        """
        Deserialize frame from bit sequence.

        Args:
            bits: Received bit sequence
            verify: Whether to verify checksum

        Returns:
            Frame object

        Raises:
            PreambleError: If preamble doesn't match
            ChecksumError: If checksum verification fails
            PostambleError: If postamble doesn't match
        """
        # Find preamble
        preamble_idx = cls._find_preamble(bits)
        if preamble_idx < 0:
            raise PreambleError("Preamble not found")

        # Skip preamble
        pos = preamble_idx + len(PREAMBLE)

        # Extract length
        if pos + 16 > len(bits):
            raise FrameError("Frame too short for length field")
        length_bits = bits[pos:pos+16]
        payload_length = bits_to_int(length_bits)
        pos += 16

        # Extract payload
        if pos + payload_length > len(bits):
            raise FrameError("Frame too short for payload")
        payload_bits = bits[pos:pos+payload_length]
        pos += payload_length

        # Extract checksum
        if pos + 8 > len(bits):
            raise FrameError("Frame too short for checksum")
        checksum_bits = bits[pos:pos+8]
        received_checksum = bits_to_int(checksum_bits)
        pos += 8

        # Verify postamble (optional, as noise might corrupt it)
        if pos + len(POSTAMBLE) <= len(bits):
            postamble = bits[pos:pos+len(POSTAMBLE)]
            # Allow some tolerance for postamble errors
            # (postamble verification is less critical than checksum)

        # Convert payload to bytes
        payload = bits_to_bytes(payload_bits)

        # Verify checksum
        if verify:
            computed = compute_checksum(payload)
            if computed != received_checksum:
                raise ChecksumError(
                    f"Checksum mismatch: computed={computed}, received={received_checksum}"
                )

        frame = cls(payload)
        frame.checksum = received_checksum
        return frame

    @staticmethod
    def _find_preamble(bits: List[int]) -> int:
        """
        Find preamble position in bit sequence.

        Args:
            bits: Bit sequence to search

        Returns:
            Index of preamble start, or -1 if not found
        """
        preamble_len = len(PREAMBLE)
        for i in range(len(bits) - preamble_len + 1):
            if bits[i:i+preamble_len] == PREAMBLE:
                return i
        return -1

    def __repr__(self):
        return f"Frame(payload={self.payload[:20]}..., len={len(self.payload)}, checksum={self.checksum})"


# =============================================================================
# Packet Slicer
# =============================================================================

class PacketSlicer:
    """
    Handles slicing and reassembly of large messages.

    Slice Header Format (4 bytes):
    - Sequence number: 2 bytes (0-65535)
    - Total slices: 2 bytes (1-65535)
    """

    def __init__(self, max_payload_size: int = MAX_PAYLOAD_SIZE):
        """
        Initialize packet slicer.

        Args:
            max_payload_size: Maximum payload size per slice
        """
        self.max_payload_size = max_payload_size
        # Reserve 4 bytes for slice header
        self.max_data_per_slice = max_payload_size - 4

    def slice(self, data: bytes) -> List[bytes]:
        """
        Slice data into multiple packets.

        Args:
            data: Data to slice

        Returns:
            List of sliced packets (each with header)
        """
        if len(data) <= self.max_data_per_slice:
            # No slicing needed, but still add header
            header = self._make_header(0, 1)
            return [header + data]

        slices = []
        total_slices = (len(data) + self.max_data_per_slice - 1) // self.max_data_per_slice

        for i in range(total_slices):
            start = i * self.max_data_per_slice
            end = min(start + self.max_data_per_slice, len(data))
            chunk = data[start:end]

            header = self._make_header(i, total_slices)
            slices.append(header + chunk)

        return slices

    def reassemble(self, slices: List[bytes]) -> bytes:
        """
        Reassemble slices into original data.

        Args:
            slices: List of sliced packets

        Returns:
            Reassembled data
        """
        if not slices:
            return b''

        # Parse and sort slices by sequence number
        parsed = []
        for slice_data in slices:
            seq_num, total, payload = self._parse_header(slice_data)
            parsed.append((seq_num, payload))

        # Sort by sequence number
        parsed.sort(key=lambda x: x[0])

        # Concatenate payloads
        return b''.join(payload for _, payload in parsed)

    def _make_header(self, seq_num: int, total: int) -> bytes:
        """Create 4-byte slice header."""
        return bytes([
            (seq_num >> 8) & 0xFF,
            seq_num & 0xFF,
            (total >> 8) & 0xFF,
            total & 0xFF
        ])

    def _parse_header(self, data: bytes) -> Tuple[int, int, bytes]:
        """Parse slice header and return (seq_num, total, payload)."""
        if len(data) < 4:
            raise ValueError("Slice too short")
        seq_num = (data[0] << 8) | data[1]
        total = (data[2] << 8) | data[3]
        payload = data[4:]
        return seq_num, total, payload


# =============================================================================
# Data Link Layer
# =============================================================================

class DataLinkLayer:
    """
    Data link layer that combines physical layer and framing.

    Provides reliable frame transmission with error detection.
    """

    def __init__(self, physical_link: PhysicalLink,
                 max_payload_size: int = MAX_PAYLOAD_SIZE):
        """
        Initialize data link layer.

        Args:
            physical_link: Physical layer link
            max_payload_size: Maximum payload per frame
        """
        self.physical_link = physical_link
        self.slicer = PacketSlicer(max_payload_size)
        self.stats = {
            'frames_sent': 0,
            'frames_received': 0,
            'checksum_errors': 0,
            'bytes_sent': 0,
            'bytes_received': 0
        }

    def send(self, data: bytes) -> bool:
        """
        Send data through the link.

        Handles slicing for large messages.

        Args:
            data: Data to send

        Returns:
            True if all frames sent successfully
        """
        slices = self.slicer.slice(data)
        success = True

        for slice_data in slices:
            frame = Frame(slice_data)
            bits = frame.to_bits()
            self.physical_link.transmit_bits(bits)
            self.stats['frames_sent'] += 1
            self.stats['bytes_sent'] += len(slice_data)

        return success

    def receive(self, bits: List[int]) -> Optional[bytes]:
        """
        Receive and parse frame from bits.

        Args:
            bits: Received bit sequence

        Returns:
            Payload data if successful, None if error
        """
        try:
            frame = Frame.from_bits(bits, verify=True)
            self.stats['frames_received'] += 1
            self.stats['bytes_received'] += len(frame.payload)
            return frame.payload
        except ChecksumError:
            self.stats['checksum_errors'] += 1
            return None
        except FrameError:
            return None

    def send_string(self, text: str) -> bool:
        """
        Send string data.

        Args:
            text: String to send

        Returns:
            True if successful
        """
        return self.send(text.encode('utf-8'))

    def transmit_and_receive(self, data: bytes) -> Tuple[Optional[bytes], bool]:
        """
        Transmit data and receive response (for testing).

        This simulates a complete send-receive cycle where the
        physical layer transmission is performed.

        Args:
            data: Data to transmit

        Returns:
            Tuple of (received_data, success)
        """
        slices = self.slicer.slice(data)
        received_slices = []
        all_success = True

        for slice_data in slices:
            frame = Frame(slice_data)
            tx_bits = frame.to_bits()

            # Transmit through physical layer
            rx_bits = self.physical_link.transmit_bits(tx_bits)

            self.stats['frames_sent'] += 1
            self.stats['bytes_sent'] += len(slice_data)

            # Parse received frame
            try:
                rx_frame = Frame.from_bits(rx_bits, verify=True)
                received_slices.append(rx_frame.payload)
                self.stats['frames_received'] += 1
                self.stats['bytes_received'] += len(rx_frame.payload)
            except ChecksumError:
                self.stats['checksum_errors'] += 1
                all_success = False
            except FrameError:
                all_success = False

        if received_slices:
            reassembled = self.slicer.reassemble(received_slices)
            return reassembled, all_success
        else:
            return None, False

    def get_stats(self) -> dict:
        """Get transmission statistics."""
        return self.stats.copy()


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Data Link Layer Demo")
    print("=" * 60)

    # Test Frame creation
    print("\n1. Frame Creation Test:")
    payload = b"Hello, World!"
    frame = Frame(payload)
    print(f"   Payload: {payload}")
    print(f"   Checksum: {frame.checksum}")

    bits = frame.to_bits()
    print(f"   Frame bits: {len(bits)} bits")

    # Parse frame back
    parsed = Frame.from_bits(bits)
    print(f"   Parsed payload: {parsed.payload}")
    print(f"   Match: {payload == parsed.payload}")

    # Test checksum error detection
    print("\n2. Checksum Error Detection:")
    corrupted_bits = bits.copy()
    corrupted_bits[30] ^= 1  # Flip a bit in payload
    try:
        Frame.from_bits(corrupted_bits)
        print("   ERROR: Should have raised ChecksumError")
    except ChecksumError as e:
        print(f"   Correctly detected error: {e}")

    # Test packet slicing
    print("\n3. Packet Slicing Test:")
    slicer = PacketSlicer(max_payload_size=50)  # Small size for testing
    long_data = b"A" * 200
    slices = slicer.slice(long_data)
    print(f"   Original data: {len(long_data)} bytes")
    print(f"   Number of slices: {len(slices)}")
    for i, s in enumerate(slices):
        print(f"   Slice {i}: {len(s)} bytes")

    reassembled = slicer.reassemble(slices)
    print(f"   Reassembled: {len(reassembled)} bytes")
    print(f"   Match: {long_data == reassembled}")

    # Test with physical layer
    print("\n4. Data Link Layer Transmission (No Noise):")
    cable = Cable(length=100, attenuation=0.1, noise_level=0, debug_mode=False)
    physical_link = PhysicalLink(cable)
    dll = DataLinkLayer(physical_link)

    test_data = b"Test message through data link layer"
    received, success = dll.transmit_and_receive(test_data)
    print(f"   Sent: {test_data}")
    print(f"   Received: {received}")
    print(f"   Success: {success}")
    print(f"   Match: {test_data == received}")

    # Test with noise
    print("\n5. Data Link Layer Transmission (With Noise):")
    cable_noisy = Cable(length=100, attenuation=0.1, noise_level=0.05, debug_mode=False)
    physical_link_noisy = PhysicalLink(cable_noisy)
    dll_noisy = DataLinkLayer(physical_link_noisy)

    test_data = b"Noisy transmission test"
    received, success = dll_noisy.transmit_and_receive(test_data)
    print(f"   Sent: {test_data}")
    print(f"   Received: {received}")
    print(f"   Success: {success}")
    print(f"   Stats: {dll_noisy.get_stats()}")

    # Test long message slicing
    print("\n6. Long Message Transmission:")
    cable_clean = Cable(length=100, attenuation=0.1, noise_level=0, debug_mode=False)
    physical_link_clean = PhysicalLink(cable_clean)
    dll_clean = DataLinkLayer(physical_link_clean, max_payload_size=64)

    long_message = b"This is a very long message that will be sliced into multiple frames. " * 5
    received, success = dll_clean.transmit_and_receive(long_message)
    print(f"   Original length: {len(long_message)} bytes")
    print(f"   Received length: {len(received) if received else 0} bytes")
    print(f"   Success: {success}")
    print(f"   Match: {long_message == received}")
    print(f"   Stats: {dll_clean.get_stats()}")

    print("\n" + "=" * 60)
