"""
Channel Coding Implementation
Level 3: Error Correction Codes

This module implements:
- Hamming(7,4) code for single-bit error correction
- CRC-8 for error detection
- Performance testing utilities

Hamming(7,4):
- Input: 4 data bits
- Output: 7 bits (4 data + 3 parity)
- Can correct 1-bit errors
- Can detect 2-bit errors
"""

import numpy as np
from typing import List, Tuple, Optional
from cable import Cable
from physical_layer import PhysicalLink, modulate_ook, demodulate_ook


# =============================================================================
# Hamming Code (7,4)
# =============================================================================

class HammingCode:
    """
    Hamming(7,4) error correction code.

    Encodes 4 data bits into 7 bits:
    - Positions 1, 2, 4 are parity bits (p1, p2, p4)
    - Positions 3, 5, 6, 7 are data bits (d1, d2, d3, d4)

    Layout: [p1, p2, d1, p4, d2, d3, d4]

    Parity equations:
    - p1 = d1 XOR d2 XOR d4 (covers positions 1,3,5,7)
    - p2 = d1 XOR d3 XOR d4 (covers positions 2,3,6,7)
    - p4 = d2 XOR d3 XOR d4 (covers positions 4,5,6,7)
    """

    # Generator matrix G (4x7): data * G = codeword
    G = np.array([
        [1, 1, 1, 0, 0, 0, 0],  # d1
        [1, 0, 0, 1, 1, 0, 0],  # d2
        [0, 1, 0, 1, 0, 1, 0],  # d3
        [1, 1, 0, 1, 0, 0, 1],  # d4
    ], dtype=np.int8)

    # Parity check matrix H (3x7): H * codeword^T = syndrome
    H = np.array([
        [1, 0, 1, 0, 1, 0, 1],  # Check p1
        [0, 1, 1, 0, 0, 1, 1],  # Check p2
        [0, 0, 0, 1, 1, 1, 1],  # Check p4
    ], dtype=np.int8)

    def __init__(self):
        """Initialize Hamming code encoder/decoder."""
        self.stats = {
            'blocks_encoded': 0,
            'blocks_decoded': 0,
            'errors_corrected': 0,
            'errors_detected': 0
        }

    def encode(self, data_bits: List[int]) -> List[int]:
        """
        Encode data bits using Hamming(7,4).

        Args:
            data_bits: List of data bits (must be multiple of 4)

        Returns:
            Encoded bit list (7 bits for every 4 data bits)
        """
        # Pad to multiple of 4
        if len(data_bits) % 4 != 0:
            padding = 4 - (len(data_bits) % 4)
            data_bits = list(data_bits) + [0] * padding

        encoded = []

        for i in range(0, len(data_bits), 4):
            block = np.array(data_bits[i:i+4], dtype=np.int8)
            codeword = np.dot(block, self.G) % 2
            encoded.extend(codeword.tolist())
            self.stats['blocks_encoded'] += 1

        return encoded

    def decode(self, received_bits: List[int]) -> List[int]:
        """
        Decode received bits and correct single-bit errors.

        Args:
            received_bits: List of received bits (must be multiple of 7)

        Returns:
            Decoded data bits (4 bits for every 7 received)
        """
        # Ensure multiple of 7
        if len(received_bits) % 7 != 0:
            # Truncate to valid length
            received_bits = received_bits[:len(received_bits) // 7 * 7]

        decoded = []

        for i in range(0, len(received_bits), 7):
            block = np.array(received_bits[i:i+7], dtype=np.int8)

            # Compute syndrome
            syndrome = np.dot(self.H, block) % 2
            syndrome_value = syndrome[0] + 2 * syndrome[1] + 4 * syndrome[2]

            if syndrome_value != 0:
                # Error detected at position syndrome_value
                error_pos = syndrome_value - 1
                if 0 <= error_pos < 7:
                    block[error_pos] ^= 1  # Correct the error
                    self.stats['errors_corrected'] += 1
                else:
                    self.stats['errors_detected'] += 1

            # Extract data bits (positions 2, 4, 5, 6 in 0-indexed)
            # In our encoding: positions 3, 5, 6, 7 contain d1, d2, d3, d4
            data = [block[2], block[4], block[5], block[6]]
            decoded.extend(data)
            self.stats['blocks_decoded'] += 1

        return decoded

    def encode_bytes(self, data: bytes) -> List[int]:
        """Encode bytes to Hamming-encoded bits."""
        bits = []
        for byte in data:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        return self.encode(bits)

    def decode_bytes(self, bits: List[int]) -> bytes:
        """Decode Hamming-encoded bits to bytes."""
        decoded = self.decode(bits)

        # Pad to multiple of 8
        if len(decoded) % 8 != 0:
            decoded = decoded + [0] * (8 - len(decoded) % 8)

        byte_list = []
        for i in range(0, len(decoded), 8):
            byte_val = 0
            for bit in decoded[i:i+8]:
                byte_val = (byte_val << 1) | bit
            byte_list.append(byte_val)
        return bytes(byte_list)

    def get_stats(self) -> dict:
        """Get coding statistics."""
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics."""
        for key in self.stats:
            self.stats[key] = 0


# =============================================================================
# CRC (Cyclic Redundancy Check)
# =============================================================================

class CRC:
    """
    CRC-8 error detection.

    Uses polynomial: x^8 + x^2 + x + 1 (0x07)
    """

    POLYNOMIAL = 0x07  # CRC-8 standard polynomial

    def __init__(self, polynomial: int = None):
        """
        Initialize CRC.

        Args:
            polynomial: CRC polynomial (default: CRC-8)
        """
        self.polynomial = polynomial or self.POLYNOMIAL

        # Build lookup table for faster computation
        self.table = self._build_table()

        self.stats = {
            'checksums_computed': 0,
            'errors_detected': 0
        }

    def _build_table(self) -> List[int]:
        """Build CRC lookup table."""
        table = []
        for i in range(256):
            crc = i
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ self.polynomial) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF
            table.append(crc)
        return table

    def compute(self, data: bytes) -> int:
        """
        Compute CRC-8 checksum.

        Args:
            data: Input data bytes

        Returns:
            8-bit CRC checksum
        """
        crc = 0
        for byte in data:
            crc = self.table[crc ^ byte]
        self.stats['checksums_computed'] += 1
        return crc

    def verify(self, data: bytes, checksum: int) -> bool:
        """
        Verify CRC checksum.

        Args:
            data: Data bytes
            checksum: Expected checksum

        Returns:
            True if checksum matches
        """
        computed = self.compute(data)
        if computed != checksum:
            self.stats['errors_detected'] += 1
            return False
        return True

    def append_crc(self, data: bytes) -> bytes:
        """Append CRC to data."""
        crc = self.compute(data)
        return data + bytes([crc])

    def check_and_strip(self, data: bytes) -> Tuple[bytes, bool]:
        """
        Check CRC and remove it from data.

        Returns:
            Tuple of (data without CRC, is_valid)
        """
        if len(data) < 1:
            return data, False

        payload = data[:-1]
        received_crc = data[-1]
        is_valid = self.verify(payload, received_crc)
        return payload, is_valid

    def get_stats(self) -> dict:
        """Get CRC statistics."""
        return self.stats.copy()


# =============================================================================
# Coded Physical Link
# =============================================================================

class CodedPhysicalLink:
    """
    Physical link with channel coding.

    Combines Hamming code and CRC for robust transmission.
    """

    def __init__(self, cable: Cable, use_hamming: bool = True, use_crc: bool = True):
        """
        Initialize coded physical link.

        Args:
            cable: Cable for transmission
            use_hamming: Enable Hamming code
            use_crc: Enable CRC
        """
        self.cable = cable
        self.physical_link = PhysicalLink(cable)
        self.use_hamming = use_hamming
        self.use_crc = use_crc

        self.hamming = HammingCode() if use_hamming else None
        self.crc = CRC() if use_crc else None

        self.stats = {
            'transmissions': 0,
            'successful': 0,
            'failed': 0,
            'hamming_corrections': 0
        }

    def transmit(self, data: bytes) -> Tuple[Optional[bytes], bool]:
        """
        Transmit data with channel coding.

        Args:
            data: Data to transmit

        Returns:
            Tuple of (received_data, success)
        """
        self.stats['transmissions'] += 1

        # Step 1: Add CRC
        if self.use_crc:
            data = self.crc.append_crc(data)

        # Step 2: Hamming encode
        if self.use_hamming:
            bits = self.hamming.encode_bytes(data)
        else:
            bits = []
            for byte in data:
                for i in range(7, -1, -1):
                    bits.append((byte >> i) & 1)

        # Step 3: Modulate and transmit
        signal = modulate_ook(bits)
        received_signal = self.cable.transmit(signal)

        # Step 4: Demodulate
        received_bits = demodulate_ook(received_signal)

        # Step 5: Hamming decode
        if self.use_hamming:
            prev_corrections = self.hamming.stats['errors_corrected']
            decoded = self.hamming.decode_bytes(received_bits)
            new_corrections = self.hamming.stats['errors_corrected'] - prev_corrections
            self.stats['hamming_corrections'] += new_corrections
        else:
            # Direct conversion
            if len(received_bits) % 8 != 0:
                received_bits = received_bits + [0] * (8 - len(received_bits) % 8)
            byte_list = []
            for i in range(0, len(received_bits), 8):
                byte_val = 0
                for bit in received_bits[i:i+8]:
                    byte_val = (byte_val << 1) | bit
                byte_list.append(byte_val)
            decoded = bytes(byte_list)

        # Step 6: Verify CRC
        if self.use_crc:
            payload, is_valid = self.crc.check_and_strip(decoded)
            if is_valid:
                self.stats['successful'] += 1
                return payload, True
            else:
                self.stats['failed'] += 1
                return None, False
        else:
            self.stats['successful'] += 1
            return decoded, True

    def transmit_string(self, message: str) -> Tuple[Optional[str], bool]:
        """Transmit string with coding."""
        data, success = self.transmit(message.encode('utf-8'))
        if success and data:
            return data.decode('utf-8', errors='replace'), True
        return None, False

    def get_stats(self) -> dict:
        """Get combined statistics."""
        stats = self.stats.copy()
        if self.hamming:
            stats['hamming'] = self.hamming.get_stats()
        if self.crc:
            stats['crc'] = self.crc.get_stats()
        return stats


# =============================================================================
# Performance Testing
# =============================================================================

def test_error_correction_performance(noise_levels: List[float],
                                       num_trials: int = 100,
                                       message_length: int = 50) -> dict:
    """
    Test error correction performance at different noise levels.

    Args:
        noise_levels: List of noise levels to test
        num_trials: Number of trials per noise level
        message_length: Test message length

    Returns:
        Dictionary with performance results
    """
    import random
    import string

    results = {
        'noise_levels': noise_levels,
        'uncoded': {'success_rate': [], 'ber': []},
        'hamming_only': {'success_rate': [], 'corrections': []},
        'crc_only': {'success_rate': [], 'detections': []},
        'hamming_crc': {'success_rate': [], 'corrections': []}
    }

    for noise in noise_levels:
        print(f"Testing noise level: {noise}")

        # Test each configuration
        for config, use_hamming, use_crc in [
            ('uncoded', False, False),
            ('hamming_only', True, False),
            ('crc_only', False, True),
            ('hamming_crc', True, True)
        ]:
            cable = Cable(length=100, attenuation=0.1, noise_level=noise)
            link = CodedPhysicalLink(cable, use_hamming=use_hamming, use_crc=use_crc)

            successes = 0
            total_corrections = 0
            total_detections = 0

            for _ in range(num_trials):
                # Generate random message
                message = ''.join(random.choices(string.ascii_letters, k=message_length))

                received, success = link.transmit_string(message)

                if success and received == message:
                    successes += 1

                if use_hamming and link.hamming:
                    total_corrections += link.hamming.stats.get('errors_corrected', 0)
                    link.hamming.reset_stats()

                if use_crc and link.crc:
                    total_detections += link.crc.stats.get('errors_detected', 0)

            success_rate = successes / num_trials
            results[config]['success_rate'].append(success_rate)

            if config in ['hamming_only', 'hamming_crc']:
                results[config]['corrections'].append(total_corrections / num_trials)
            if config in ['crc_only']:
                results[config]['detections'].append(total_detections / num_trials)

    return results


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Channel Coding Demo - Level 3: Error Correction")
    print("=" * 70)

    # Test Hamming Code
    print("\n1. Hamming(7,4) Code Test:")
    hamming = HammingCode()

    # Test encoding
    data_bits = [1, 0, 1, 1]
    encoded = hamming.encode(data_bits)
    print(f"   Data bits:    {data_bits}")
    print(f"   Encoded:      {encoded}")

    # Test decoding without errors
    decoded = hamming.decode(encoded)
    print(f"   Decoded:      {decoded[:4]}")
    print(f"   Match: {data_bits == decoded[:4]}")

    # Test error correction
    print("\n2. Single-Bit Error Correction:")
    corrupted = encoded.copy()
    corrupted[3] ^= 1  # Flip one bit
    print(f"   Corrupted:    {corrupted}")

    corrected = hamming.decode(corrupted)
    print(f"   Corrected:    {corrected[:4]}")
    print(f"   Match: {data_bits == corrected[:4]}")
    print(f"   Errors corrected: {hamming.stats['errors_corrected']}")

    # Test CRC
    print("\n3. CRC-8 Test:")
    crc = CRC()

    test_data = b"Test data for CRC"
    checksum = crc.compute(test_data)
    print(f"   Data: {test_data}")
    print(f"   CRC-8: {checksum} (0x{checksum:02X})")

    # Verify
    is_valid = crc.verify(test_data, checksum)
    print(f"   Verification: {'PASS' if is_valid else 'FAIL'}")

    # Test with corruption
    corrupted_data = bytearray(test_data)
    corrupted_data[5] ^= 0x01
    is_valid = crc.verify(bytes(corrupted_data), checksum)
    print(f"   Corrupted verification: {'PASS' if is_valid else 'FAIL (detected)'}")

    # Test coded physical link
    print("\n4. Coded Physical Link Test (Low Noise):")
    cable = Cable(length=100, attenuation=0.1, noise_level=0.05)
    coded_link = CodedPhysicalLink(cable, use_hamming=True, use_crc=True)

    message = "Hello, Channel Coding!"
    received, success = coded_link.transmit_string(message)
    print(f"   Sent: '{message}'")
    print(f"   Received: '{received}'")
    print(f"   Success: {success}")
    print(f"   Stats: {coded_link.get_stats()}")

    # Test with higher noise
    print("\n5. Coded Physical Link Test (Higher Noise):")
    cable_noisy = Cable(length=100, attenuation=0.1, noise_level=0.15)
    coded_link_noisy = CodedPhysicalLink(cable_noisy, use_hamming=True, use_crc=True)

    for i in range(5):
        message = f"Test message {i+1}"
        received, success = coded_link_noisy.transmit_string(message)
        status = "OK" if success and received == message else "CORRECTED" if success else "FAILED"
        print(f"   Message {i+1}: {status}")

    print(f"   Final stats: {coded_link_noisy.get_stats()}")

    # Performance comparison
    print("\n6. Performance Comparison:")
    print("   Testing with/without channel coding...")

    noise_levels = [0.05, 0.1, 0.15, 0.2]
    results = test_error_correction_performance(noise_levels, num_trials=50, message_length=20)

    print("\n   Results:")
    print(f"   {'Noise':<8} {'Uncoded':<12} {'Hamming':<12} {'CRC':<12} {'Both':<12}")
    print("   " + "-" * 56)
    for i, noise in enumerate(noise_levels):
        uncoded = results['uncoded']['success_rate'][i]
        hamming = results['hamming_only']['success_rate'][i]
        crc = results['crc_only']['success_rate'][i]
        both = results['hamming_crc']['success_rate'][i]
        print(f"   {noise:<8} {uncoded:<12.1%} {hamming:<12.1%} {crc:<12.1%} {both:<12.1%}")

    print("\n" + "=" * 70)
