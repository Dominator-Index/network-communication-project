"""
Modulation Schemes Implementation
Level 3: Performance Optimization

This module implements multiple modulation schemes:
- OOK (On-Off Keying) - Simplest
- ASK (Amplitude Shift Keying)
- FSK (Frequency Shift Keying)
- BPSK (Binary Phase Shift Keying)
- QPSK (Quadrature Phase Shift Keying)

For comparison of performance under different noise conditions.
"""

import numpy as np
from typing import List, Tuple, Dict
from abc import ABC, abstractmethod
from cable import Cable


# =============================================================================
# Base Modulation Scheme
# =============================================================================

class ModulationScheme(ABC):
    """Abstract base class for modulation schemes."""

    def __init__(self, samples_per_bit: int = 100, carrier_freq: float = 10.0):
        """
        Initialize modulation scheme.

        Args:
            samples_per_bit: Number of samples per bit
            carrier_freq: Carrier frequency for modulated schemes
        """
        self.samples_per_bit = samples_per_bit
        self.carrier_freq = carrier_freq
        self.name = self.__class__.__name__

    @abstractmethod
    def modulate(self, bits: List[int]) -> np.ndarray:
        """
        Modulate bit sequence to analog signal.

        Args:
            bits: List of bits (0s and 1s)

        Returns:
            Modulated signal as numpy array
        """
        pass

    @abstractmethod
    def demodulate(self, signal: np.ndarray) -> List[int]:
        """
        Demodulate analog signal to bit sequence.

        Args:
            signal: Received analog signal

        Returns:
            Demodulated bit list
        """
        pass

    def get_bandwidth_efficiency(self) -> float:
        """
        Get bandwidth efficiency in bits per sample.

        Returns:
            Efficiency value
        """
        return 1.0 / self.samples_per_bit


# =============================================================================
# OOK - On-Off Keying
# =============================================================================

class OOK(ModulationScheme):
    """
    On-Off Keying modulation.

    Simplest modulation scheme:
    - Bit 1: High amplitude
    - Bit 0: Zero amplitude
    """

    def __init__(self, amplitude: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self.amplitude = amplitude

    def modulate(self, bits: List[int]) -> np.ndarray:
        signal = np.zeros(len(bits) * self.samples_per_bit)
        for i, bit in enumerate(bits):
            start = i * self.samples_per_bit
            end = (i + 1) * self.samples_per_bit
            if bit == 1:
                signal[start:end] = self.amplitude
        return signal

    def demodulate(self, signal: np.ndarray) -> List[int]:
        num_bits = len(signal) // self.samples_per_bit
        threshold = np.mean(np.abs(signal)) * 0.5

        bits = []
        for i in range(num_bits):
            start = i * self.samples_per_bit
            end = (i + 1) * self.samples_per_bit
            avg = np.mean(signal[start:end])
            bits.append(1 if avg > threshold else 0)

        return bits


# =============================================================================
# ASK - Amplitude Shift Keying
# =============================================================================

class ASK(ModulationScheme):
    """
    Amplitude Shift Keying modulation.

    Uses carrier wave with different amplitudes:
    - Bit 1: Full amplitude carrier
    - Bit 0: Zero or reduced amplitude
    """

    def __init__(self, amplitude_1: float = 1.0, amplitude_0: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        self.amplitude_1 = amplitude_1
        self.amplitude_0 = amplitude_0

    def modulate(self, bits: List[int]) -> np.ndarray:
        signal = np.zeros(len(bits) * self.samples_per_bit)
        t = np.arange(self.samples_per_bit) / self.samples_per_bit

        for i, bit in enumerate(bits):
            start = i * self.samples_per_bit
            end = (i + 1) * self.samples_per_bit
            amplitude = self.amplitude_1 if bit == 1 else self.amplitude_0
            signal[start:end] = amplitude * np.sin(2 * np.pi * self.carrier_freq * t)

        return signal

    def demodulate(self, signal: np.ndarray) -> List[int]:
        num_bits = len(signal) // self.samples_per_bit

        # Energy detection
        bits = []
        energies = []

        for i in range(num_bits):
            start = i * self.samples_per_bit
            end = (i + 1) * self.samples_per_bit
            segment = signal[start:end]
            energy = np.sum(segment ** 2)
            energies.append(energy)

        # Adaptive threshold
        threshold = np.mean(energies) * 0.5

        for energy in energies:
            bits.append(1 if energy > threshold else 0)

        return bits


# =============================================================================
# FSK - Frequency Shift Keying
# =============================================================================

class FSK(ModulationScheme):
    """
    Frequency Shift Keying modulation.

    Uses different frequencies:
    - Bit 1: High frequency
    - Bit 0: Low frequency
    """

    def __init__(self, freq_1: float = 15.0, freq_0: float = 5.0, **kwargs):
        super().__init__(**kwargs)
        self.freq_1 = freq_1
        self.freq_0 = freq_0

    def modulate(self, bits: List[int]) -> np.ndarray:
        signal = np.zeros(len(bits) * self.samples_per_bit)
        t = np.arange(self.samples_per_bit) / self.samples_per_bit

        for i, bit in enumerate(bits):
            start = i * self.samples_per_bit
            end = (i + 1) * self.samples_per_bit
            freq = self.freq_1 if bit == 1 else self.freq_0
            signal[start:end] = np.sin(2 * np.pi * freq * t)

        return signal

    def demodulate(self, signal: np.ndarray) -> List[int]:
        num_bits = len(signal) // self.samples_per_bit
        t = np.arange(self.samples_per_bit) / self.samples_per_bit

        # Reference signals for correlation
        ref_1 = np.sin(2 * np.pi * self.freq_1 * t)
        ref_0 = np.sin(2 * np.pi * self.freq_0 * t)

        bits = []
        for i in range(num_bits):
            start = i * self.samples_per_bit
            end = (i + 1) * self.samples_per_bit
            segment = signal[start:end]

            # Correlation with reference signals
            corr_1 = np.abs(np.sum(segment * ref_1))
            corr_0 = np.abs(np.sum(segment * ref_0))

            bits.append(1 if corr_1 > corr_0 else 0)

        return bits


# =============================================================================
# BPSK - Binary Phase Shift Keying
# =============================================================================

class BPSK(ModulationScheme):
    """
    Binary Phase Shift Keying modulation.

    Uses phase shifts:
    - Bit 1: 0 degrees phase
    - Bit 0: 180 degrees phase
    """

    def modulate(self, bits: List[int]) -> np.ndarray:
        signal = np.zeros(len(bits) * self.samples_per_bit)
        t = np.arange(self.samples_per_bit) / self.samples_per_bit

        for i, bit in enumerate(bits):
            start = i * self.samples_per_bit
            end = (i + 1) * self.samples_per_bit
            phase = 0 if bit == 1 else np.pi
            signal[start:end] = np.sin(2 * np.pi * self.carrier_freq * t + phase)

        return signal

    def demodulate(self, signal: np.ndarray) -> List[int]:
        num_bits = len(signal) // self.samples_per_bit
        t = np.arange(self.samples_per_bit) / self.samples_per_bit

        # Reference signal (0 phase)
        reference = np.sin(2 * np.pi * self.carrier_freq * t)

        bits = []
        for i in range(num_bits):
            start = i * self.samples_per_bit
            end = (i + 1) * self.samples_per_bit
            segment = signal[start:end]

            # Correlation with reference
            correlation = np.sum(segment * reference)
            bits.append(1 if correlation > 0 else 0)

        return bits


# =============================================================================
# QPSK - Quadrature Phase Shift Keying
# =============================================================================

class QPSK(ModulationScheme):
    """
    Quadrature Phase Shift Keying modulation.

    Encodes 2 bits per symbol using 4 phases:
    - 00: 45 degrees
    - 01: 135 degrees
    - 10: 225 degrees
    - 11: 315 degrees
    """

    PHASE_MAP = {
        (0, 0): np.pi/4,      # 45 degrees
        (0, 1): 3*np.pi/4,    # 135 degrees
        (1, 0): 5*np.pi/4,    # 225 degrees
        (1, 1): 7*np.pi/4,    # 315 degrees
    }

    def modulate(self, bits: List[int]) -> np.ndarray:
        # Pad to even length
        if len(bits) % 2 != 0:
            bits = list(bits) + [0]

        num_symbols = len(bits) // 2
        signal = np.zeros(num_symbols * self.samples_per_bit)
        t = np.arange(self.samples_per_bit) / self.samples_per_bit

        for i in range(num_symbols):
            bit_pair = (bits[2*i], bits[2*i + 1])
            phase = self.PHASE_MAP[bit_pair]

            start = i * self.samples_per_bit
            end = (i + 1) * self.samples_per_bit
            signal[start:end] = np.sin(2 * np.pi * self.carrier_freq * t + phase)

        return signal

    def demodulate(self, signal: np.ndarray) -> List[int]:
        num_symbols = len(signal) // self.samples_per_bit
        t = np.arange(self.samples_per_bit) / self.samples_per_bit

        # In-phase and quadrature references
        cos_ref = np.cos(2 * np.pi * self.carrier_freq * t)
        sin_ref = np.sin(2 * np.pi * self.carrier_freq * t)

        bits = []
        for i in range(num_symbols):
            start = i * self.samples_per_bit
            end = (i + 1) * self.samples_per_bit
            segment = signal[start:end]

            # Correlate with I and Q
            I = np.sum(segment * cos_ref)
            Q = np.sum(segment * sin_ref)

            # Decision based on quadrant
            if I >= 0 and Q >= 0:
                bits.extend([0, 0])
            elif I < 0 and Q >= 0:
                bits.extend([0, 1])
            elif I < 0 and Q < 0:
                bits.extend([1, 0])
            else:
                bits.extend([1, 1])

        return bits

    def get_bandwidth_efficiency(self) -> float:
        # QPSK encodes 2 bits per symbol
        return 2.0 / self.samples_per_bit


# =============================================================================
# Modulation Comparator
# =============================================================================

class ModulationComparator:
    """
    Compare performance of different modulation schemes.
    """

    def __init__(self, schemes: List[ModulationScheme] = None):
        """
        Initialize comparator.

        Args:
            schemes: List of modulation schemes to compare
        """
        self.schemes = schemes or [
            OOK(),
            ASK(),
            FSK(),
            BPSK(),
            QPSK()
        ]

    def compare_ber(self, noise_levels: List[float],
                    num_trials: int = 100,
                    bits_per_trial: int = 100) -> Dict[str, List[float]]:
        """
        Compare Bit Error Rate across noise levels.

        Args:
            noise_levels: List of noise levels to test
            num_trials: Number of trials per level
            bits_per_trial: Bits per trial

        Returns:
            Dictionary mapping scheme name to BER list
        """
        results = {scheme.name: [] for scheme in self.schemes}

        for noise in noise_levels:
            cable = Cable(length=100, attenuation=0.1, noise_level=noise)

            for scheme in self.schemes:
                total_errors = 0
                total_bits = 0

                for _ in range(num_trials):
                    # Generate random bits
                    tx_bits = list(np.random.randint(0, 2, bits_per_trial))

                    # Modulate
                    signal = scheme.modulate(tx_bits)

                    # Transmit through cable
                    received = cable.transmit(signal)

                    # Demodulate
                    rx_bits = scheme.demodulate(received)

                    # Count errors
                    min_len = min(len(tx_bits), len(rx_bits))
                    errors = sum(1 for t, r in zip(tx_bits[:min_len], rx_bits[:min_len]) if t != r)
                    total_errors += errors
                    total_bits += min_len

                ber = total_errors / total_bits if total_bits > 0 else 0
                results[scheme.name].append(ber)

        return results

    def compare_throughput(self, message: str,
                           noise_levels: List[float],
                           num_trials: int = 50) -> Dict[str, List[float]]:
        """
        Compare successful transmission rate.

        Args:
            message: Test message
            noise_levels: Noise levels to test
            num_trials: Trials per level

        Returns:
            Dictionary mapping scheme name to success rates
        """
        from physical_layer import string_to_bits, bits_to_string

        results = {scheme.name: [] for scheme in self.schemes}
        tx_bits = string_to_bits(message)

        for noise in noise_levels:
            cable = Cable(length=100, attenuation=0.1, noise_level=noise)

            for scheme in self.schemes:
                successes = 0

                for _ in range(num_trials):
                    # Transmit
                    signal = scheme.modulate(tx_bits)
                    received = cable.transmit(signal)
                    rx_bits = scheme.demodulate(received)

                    # Check match
                    if rx_bits[:len(tx_bits)] == tx_bits:
                        successes += 1

                success_rate = successes / num_trials
                results[scheme.name].append(success_rate)

        return results

    def plot_comparison(self, noise_levels: List[float],
                        num_trials: int = 100,
                        bits_per_trial: int = 100,
                        output_file: str = "modulation_comparison.png"):
        """
        Create comparison plot.

        Args:
            noise_levels: Noise levels to test
            num_trials: Trials per level
            bits_per_trial: Bits per trial
            output_file: Output file path
        """
        import matplotlib.pyplot as plt

        # Get BER data
        ber_results = self.compare_ber(noise_levels, num_trials, bits_per_trial)

        # Create plot
        fig, ax = plt.subplots(figsize=(10, 6))

        markers = ['o', 's', '^', 'D', 'v']
        colors = ['blue', 'green', 'red', 'purple', 'orange']

        for i, (scheme_name, ber_list) in enumerate(ber_results.items()):
            # Add small value to avoid log(0)
            ber_list = [max(b, 1e-6) for b in ber_list]
            ax.semilogy(noise_levels, ber_list,
                       marker=markers[i % len(markers)],
                       color=colors[i % len(colors)],
                       linewidth=2, markersize=8,
                       label=scheme_name)

        ax.set_xlabel('Noise Level', fontsize=12)
        ax.set_ylabel('Bit Error Rate (log scale)', fontsize=12)
        ax.set_title('Modulation Scheme Comparison', fontsize=14)
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_file, dpi=150)
        plt.close()

        return output_file


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Modulation Schemes Demo - Level 3: Performance")
    print("=" * 70)

    # Test each modulation scheme
    test_bits = [1, 0, 1, 1, 0, 0, 1, 0]
    print(f"\nTest bits: {test_bits}")

    schemes = [
        OOK(),
        ASK(),
        FSK(),
        BPSK(),
        QPSK()
    ]

    print("\n1. Basic Modulation/Demodulation Test (No Noise):")
    print("-" * 50)

    for scheme in schemes:
        signal = scheme.modulate(test_bits)
        recovered = scheme.demodulate(signal)

        # For QPSK, compare only the bits we sent
        compare_len = len(test_bits)
        match = recovered[:compare_len] == test_bits

        print(f"  {scheme.name:8s}: Signal length={len(signal):4d}, "
              f"Recovered={recovered[:compare_len]}, Match={match}")

    # Test with noise
    print("\n2. Performance with Noise:")
    print("-" * 50)

    noise_levels = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3]

    print(f"{'Scheme':<10} ", end="")
    for noise in noise_levels:
        print(f"{noise:>8.2f} ", end="")
    print()
    print("-" * 60)

    comparator = ModulationComparator(schemes)
    ber_results = comparator.compare_ber(noise_levels, num_trials=100, bits_per_trial=50)

    for scheme_name, ber_list in ber_results.items():
        print(f"{scheme_name:<10} ", end="")
        for ber in ber_list:
            print(f"{ber:>8.2%} ", end="")
        print()

    # Throughput comparison
    print("\n3. Message Transmission Success Rate:")
    print("-" * 50)

    throughput_results = comparator.compare_throughput(
        "Hello World",
        noise_levels[:4],
        num_trials=50
    )

    print(f"{'Scheme':<10} ", end="")
    for noise in noise_levels[:4]:
        print(f"{noise:>8.2f} ", end="")
    print()
    print("-" * 50)

    for scheme_name, success_list in throughput_results.items():
        print(f"{scheme_name:<10} ", end="")
        for success in success_list:
            print(f"{success:>8.1%} ", end="")
        print()

    # Generate plot
    print("\n4. Generating comparison plot...")
    plot_file = comparator.plot_comparison(
        noise_levels,
        num_trials=100,
        bits_per_trial=100,
        output_file="modulation_comparison.png"
    )
    print(f"   Plot saved to: {plot_file}")

    # Bandwidth efficiency
    print("\n5. Bandwidth Efficiency:")
    print("-" * 50)
    for scheme in schemes:
        efficiency = scheme.get_bandwidth_efficiency()
        print(f"  {scheme.name:<10}: {efficiency:.4f} bits/sample")

    print("\n" + "=" * 70)
