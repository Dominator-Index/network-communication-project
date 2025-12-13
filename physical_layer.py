"""
Physical Layer Implementation
Level 1: Point-to-Point Communication

This module handles:
- String/Bits conversion
- OOK (On-Off Keying) modulation/demodulation
- Physical link transmission using Cable class
"""

import numpy as np
from typing import List, Tuple, Optional
from cable import Cable


# =============================================================================
# Constants
# =============================================================================

SAMPLES_PER_BIT = 100  # Number of samples per bit period
DEFAULT_AMPLITUDE = 1.0  # Default signal amplitude


# =============================================================================
# Bit Conversion Functions
# =============================================================================

def string_to_bits(text: str) -> List[int]:
    """
    Convert ASCII string to list of bits (8 bits per character).

    Args:
        text: Input string to convert

    Returns:
        List of bits (0s and 1s)

    Example:
        >>> string_to_bits("Hi")
        [0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1]
    """
    bits = []
    for char in text:
        # Get ASCII value and convert to 8-bit binary
        ascii_val = ord(char)
        for i in range(7, -1, -1):  # MSB first
            bits.append((ascii_val >> i) & 1)
    return bits


def bits_to_string(bits: List[int]) -> str:
    """
    Convert list of bits back to ASCII string.

    Args:
        bits: List of bits (must be multiple of 8)

    Returns:
        Decoded string

    Example:
        >>> bits_to_string([0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0, 1])
        'Hi'
    """
    if len(bits) % 8 != 0:
        # Pad with zeros if not multiple of 8
        bits = bits + [0] * (8 - len(bits) % 8)

    text = []
    for i in range(0, len(bits), 8):
        byte = bits[i:i+8]
        # Convert 8 bits to ASCII value
        ascii_val = 0
        for bit in byte:
            ascii_val = (ascii_val << 1) | bit
        if ascii_val > 0:  # Skip null characters
            text.append(chr(ascii_val))
    return ''.join(text)


def bytes_to_bits(data: bytes) -> List[int]:
    """
    Convert bytes to list of bits.

    Args:
        data: Input bytes

    Returns:
        List of bits
    """
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def bits_to_bytes(bits: List[int]) -> bytes:
    """
    Convert list of bits to bytes.

    Args:
        bits: List of bits (will be padded to multiple of 8)

    Returns:
        Bytes object
    """
    # Pad to multiple of 8
    if len(bits) % 8 != 0:
        bits = bits + [0] * (8 - len(bits) % 8)

    byte_list = []
    for i in range(0, len(bits), 8):
        byte_val = 0
        for bit in bits[i:i+8]:
            byte_val = (byte_val << 1) | bit
        byte_list.append(byte_val)
    return bytes(byte_list)


def int_to_bits(value: int, num_bits: int) -> List[int]:
    """
    Convert integer to fixed-length bit list.

    Args:
        value: Integer value to convert
        num_bits: Number of bits in output

    Returns:
        List of bits (MSB first)
    """
    bits = []
    for i in range(num_bits - 1, -1, -1):
        bits.append((value >> i) & 1)
    return bits


def bits_to_int(bits: List[int]) -> int:
    """
    Convert bit list to integer.

    Args:
        bits: List of bits (MSB first)

    Returns:
        Integer value
    """
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    return value


# =============================================================================
# OOK Modulation/Demodulation
# =============================================================================

def modulate_ook(bits: List[int],
                 samples_per_bit: int = SAMPLES_PER_BIT,
                 amplitude: float = DEFAULT_AMPLITUDE) -> np.ndarray:
    """
    On-Off Keying (OOK) modulation.

    - Bit 1: High amplitude level
    - Bit 0: Zero level

    Args:
        bits: List of bits to modulate
        samples_per_bit: Number of samples per bit period
        amplitude: Signal amplitude for bit 1

    Returns:
        Modulated analog signal as numpy array
    """
    signal = np.zeros(len(bits) * samples_per_bit)

    for i, bit in enumerate(bits):
        start = i * samples_per_bit
        end = (i + 1) * samples_per_bit
        if bit == 1:
            signal[start:end] = amplitude

    return signal


def demodulate_ook(signal: np.ndarray,
                   samples_per_bit: int = SAMPLES_PER_BIT,
                   threshold: Optional[float] = None) -> List[int]:
    """
    Demodulate OOK signal using threshold detection.

    Uses adaptive threshold if not specified (based on signal statistics).

    Args:
        signal: Received analog signal
        samples_per_bit: Number of samples per bit period
        threshold: Decision threshold (adaptive if None)

    Returns:
        Demodulated bit list
    """
    num_bits = len(signal) // samples_per_bit

    # Calculate adaptive threshold if not provided
    if threshold is None:
        # Use mean of absolute values as adaptive threshold
        threshold = np.mean(np.abs(signal)) * 0.5

    bits = []
    for i in range(num_bits):
        start = i * samples_per_bit
        end = (i + 1) * samples_per_bit
        segment = signal[start:end]

        # Average the segment and compare to threshold
        avg = np.mean(segment)
        bits.append(1 if avg > threshold else 0)

    return bits


def calculate_adaptive_threshold(signal: np.ndarray,
                                  samples_per_bit: int = SAMPLES_PER_BIT) -> float:
    """
    Calculate optimal threshold based on signal statistics.

    Uses the midpoint between estimated high and low levels.

    Args:
        signal: Received signal
        samples_per_bit: Samples per bit

    Returns:
        Optimal threshold value
    """
    num_bits = len(signal) // samples_per_bit

    # Collect average values for each bit period
    averages = []
    for i in range(num_bits):
        start = i * samples_per_bit
        end = (i + 1) * samples_per_bit
        averages.append(np.mean(signal[start:end]))

    if len(averages) == 0:
        return 0.5

    # Estimate high and low levels using clustering
    averages = np.array(averages)
    sorted_avg = np.sort(averages)

    # Use median split
    mid_idx = len(sorted_avg) // 2
    low_estimate = np.mean(sorted_avg[:max(1, mid_idx)])
    high_estimate = np.mean(sorted_avg[mid_idx:])

    # Threshold is midpoint
    return (low_estimate + high_estimate) / 2


# =============================================================================
# Physical Link Class
# =============================================================================

class PhysicalLink:
    """
    Represents a point-to-point physical connection using Cable.

    Handles modulation, transmission, and demodulation.
    """

    def __init__(self, cable: Cable, samples_per_bit: int = SAMPLES_PER_BIT):
        """
        Initialize physical link.

        Args:
            cable: Cable instance for transmission
            samples_per_bit: Samples per bit period
        """
        self.cable = cable
        self.samples_per_bit = samples_per_bit
        self.last_tx_signal = None
        self.last_rx_signal = None

    def transmit_bits(self, bits: List[int]) -> List[int]:
        """
        Transmit bits through the physical link.

        Process: bits -> modulate -> cable -> demodulate -> bits

        Args:
            bits: Bits to transmit

        Returns:
            Received bits after transmission
        """
        # Modulate
        signal = modulate_ook(bits, self.samples_per_bit)
        self.last_tx_signal = signal.copy()

        # Transmit through cable
        received_signal = self.cable.transmit(signal)
        self.last_rx_signal = received_signal.copy()

        # Calculate adaptive threshold
        threshold = calculate_adaptive_threshold(received_signal, self.samples_per_bit)

        # Demodulate
        received_bits = demodulate_ook(received_signal, self.samples_per_bit, threshold)

        return received_bits

    def transmit_data(self, data: str) -> str:
        """
        Transmit string data through the physical link.

        Args:
            data: String to transmit

        Returns:
            Received string after transmission
        """
        bits = string_to_bits(data)
        received_bits = self.transmit_bits(bits)
        return bits_to_string(received_bits)

    def transmit_bytes(self, data: bytes) -> bytes:
        """
        Transmit bytes through the physical link.

        Args:
            data: Bytes to transmit

        Returns:
            Received bytes after transmission
        """
        bits = bytes_to_bits(data)
        received_bits = self.transmit_bits(bits)
        return bits_to_bytes(received_bits)

    def get_bit_error_rate(self, tx_bits: List[int], rx_bits: List[int]) -> float:
        """
        Calculate bit error rate.

        Args:
            tx_bits: Transmitted bits
            rx_bits: Received bits

        Returns:
            Bit error rate (0.0 to 1.0)
        """
        if len(tx_bits) != len(rx_bits):
            min_len = min(len(tx_bits), len(rx_bits))
            tx_bits = tx_bits[:min_len]
            rx_bits = rx_bits[:min_len]

        if len(tx_bits) == 0:
            return 0.0

        errors = sum(1 for t, r in zip(tx_bits, rx_bits) if t != r)
        return errors / len(tx_bits)

    def get_snr(self) -> float:
        """
        Get SNR from last transmission.

        Returns:
            SNR in dB
        """
        stats = self.cable.get_signal_stats()
        return stats.get('snr_db', 0.0)


# =============================================================================
# Shannon Capacity Calculation
# =============================================================================

def calculate_shannon_capacity(snr_db: float, bandwidth: float = 1.0) -> float:
    """
    Calculate theoretical Shannon channel capacity.

    C = B * log2(1 + SNR)

    Args:
        snr_db: Signal-to-noise ratio in dB
        bandwidth: Channel bandwidth (normalized to 1.0)

    Returns:
        Channel capacity in bits per second per Hz
    """
    snr_linear = 10 ** (snr_db / 10)
    return bandwidth * np.log2(1 + snr_linear)


def measure_throughput(link: PhysicalLink, num_trials: int = 100,
                       message_length: int = 100) -> Tuple[float, float]:
    """
    Measure actual throughput of a physical link.

    Args:
        link: PhysicalLink instance
        num_trials: Number of test transmissions
        message_length: Length of test message in characters

    Returns:
        Tuple of (success_rate, bit_error_rate)
    """
    import random
    import string

    total_bits = 0
    error_bits = 0
    successful = 0

    for _ in range(num_trials):
        # Generate random message
        message = ''.join(random.choices(string.ascii_letters + string.digits,
                                         k=message_length))
        tx_bits = string_to_bits(message)
        rx_bits = link.transmit_bits(tx_bits)

        total_bits += len(tx_bits)
        error_bits += sum(1 for t, r in zip(tx_bits, rx_bits) if t != r)

        if tx_bits == rx_bits:
            successful += 1

    success_rate = successful / num_trials
    ber = error_bits / total_bits if total_bits > 0 else 0.0

    return success_rate, ber


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Physical Layer Demo")
    print("=" * 60)

    # Test bit conversion
    print("\n1. Bit Conversion Test:")
    test_string = "Hello"
    bits = string_to_bits(test_string)
    recovered = bits_to_string(bits)
    print(f"   Original: '{test_string}'")
    print(f"   Bits: {bits[:16]}... (first 16 bits)")
    print(f"   Recovered: '{recovered}'")
    print(f"   Match: {test_string == recovered}")

    # Test modulation with no noise
    print("\n2. OOK Modulation Test (No Noise):")
    cable_clean = Cable(length=100, attenuation=0.1, noise_level=0, debug_mode=False)
    link_clean = PhysicalLink(cable_clean)

    message = "Test"
    result = link_clean.transmit_data(message)
    print(f"   Sent: '{message}'")
    print(f"   Received: '{result}'")
    print(f"   Match: {message == result}")

    # Test with noise
    print("\n3. OOK Modulation Test (With Noise):")
    cable_noisy = Cable(length=100, attenuation=0.1, noise_level=0.1, debug_mode=False)
    link_noisy = PhysicalLink(cable_noisy)

    message = "Hello World"
    result = link_noisy.transmit_data(message)
    tx_bits = string_to_bits(message)
    rx_bits = string_to_bits(result)
    ber = link_noisy.get_bit_error_rate(tx_bits, rx_bits[:len(tx_bits)])

    print(f"   Sent: '{message}'")
    print(f"   Received: '{result}'")
    print(f"   Bit Error Rate: {ber:.2%}")
    print(f"   SNR: {link_noisy.get_snr():.2f} dB")

    # Shannon capacity
    print("\n4. Shannon Capacity:")
    snr = link_noisy.get_snr()
    capacity = calculate_shannon_capacity(snr)
    print(f"   SNR: {snr:.2f} dB")
    print(f"   Theoretical Capacity: {capacity:.2f} bits/symbol")

    print("\n" + "=" * 60)
