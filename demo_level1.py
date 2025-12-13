"""
Level 1 Demonstration: Point-to-Point Communication
===================================================

This demo shows:
1. Basic string transmission through physical layer
2. Bit stream transmission with OOK modulation
3. Packet slicing for long messages
4. Error detection mechanism
5. Performance under different noise levels
6. Comparison with Shannon capacity formula

Requirements:
- Successfully transmit simple strings (15 points)
- Handle longer messages with slicing (5 points)
- Basic error detection mechanism (10 points)
"""

import numpy as np
import matplotlib.pyplot as plt
from cable import Cable
from physical_layer import (
    PhysicalLink, string_to_bits, bits_to_string,
    modulate_ook, demodulate_ook,
    calculate_shannon_capacity, measure_throughput,
    SAMPLES_PER_BIT
)
from data_link_layer import (
    Frame, DataLinkLayer, PacketSlicer,
    compute_checksum, ChecksumError
)


def demo_basic_transmission():
    """
    Demo 1: Basic string transmission
    Shows the complete process of point-to-point communication.
    """
    print("=" * 70)
    print("Demo 1: Basic String Transmission (15 points)")
    print("=" * 70)

    # Create cable with low noise
    cable = Cable(length=100, attenuation=0.1, noise_level=0.01, debug_mode=False)
    link = PhysicalLink(cable)

    # Test messages
    test_messages = [
        "Hello",
        "Hello, World!",
        "Data Communication Networks",
        "12345"
    ]

    print("\nTransmitting strings through physical layer:")
    print("-" * 50)

    for msg in test_messages:
        # Convert to bits
        tx_bits = string_to_bits(msg)

        # Transmit through physical link
        rx_bits = link.transmit_bits(tx_bits)

        # Convert back to string
        received = bits_to_string(rx_bits)

        # Calculate BER
        errors = sum(1 for t, r in zip(tx_bits, rx_bits) if t != r)
        ber = errors / len(tx_bits) if tx_bits else 0

        status = "OK" if msg == received else "FAILED"
        print(f"  Sent: '{msg}' ({len(tx_bits)} bits)")
        print(f"  Received: '{received}'")
        print(f"  BER: {ber:.4%}, Status: [{status}]")
        print()

    # Show signal statistics
    stats = cable.get_signal_stats()
    print(f"Signal Statistics:")
    print(f"  SNR: {stats.get('snr_db', 0):.2f} dB")
    print()


def demo_bit_stream():
    """
    Demo 2: Bit stream transmission with visualization
    Shows the modulation and demodulation process.
    """
    print("=" * 70)
    print("Demo 2: Bit Stream Transmission & Visualization")
    print("=" * 70)

    # Create cable with debug mode
    cable = Cable(length=100, attenuation=0.1, noise_level=0.02, debug_mode=False)

    # Simple bit pattern
    test_bits = [1, 0, 1, 1, 0, 0, 1, 0]
    print(f"\nTransmitting bit pattern: {test_bits}")

    # Modulate
    signal = modulate_ook(test_bits)
    print(f"  Modulated signal: {len(signal)} samples ({SAMPLES_PER_BIT} samples/bit)")

    # Transmit through cable
    received_signal = cable.transmit(signal)

    # Demodulate
    received_bits = demodulate_ook(received_signal)
    print(f"  Received bits: {received_bits}")
    print(f"  Match: {test_bits == received_bits}")

    # Create visualization
    fig, axes = plt.subplots(3, 1, figsize=(12, 8))

    # Original bits
    bit_signal = np.repeat(test_bits, SAMPLES_PER_BIT)
    axes[0].plot(bit_signal, 'b-', linewidth=2)
    axes[0].set_title('Original Bits')
    axes[0].set_ylabel('Bit Value')
    axes[0].set_ylim(-0.2, 1.2)
    axes[0].grid(True, alpha=0.3)

    # Transmitted signal
    axes[1].plot(signal, 'g-', linewidth=1)
    axes[1].set_title('Transmitted Signal (After OOK Modulation)')
    axes[1].set_ylabel('Amplitude')
    axes[1].grid(True, alpha=0.3)

    # Received signal
    axes[2].plot(received_signal, 'r-', linewidth=1)
    axes[2].set_title('Received Signal (After Cable Transmission)')
    axes[2].set_xlabel('Sample')
    axes[2].set_ylabel('Amplitude')
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('demo_level1_signals.png', dpi=150)
    print(f"\n  Signal visualization saved to: demo_level1_signals.png")
    plt.close()


def demo_packet_slicing():
    """
    Demo 3: Packet slicing for long messages (5 points)
    Shows how long messages are split and reassembled.
    """
    print("=" * 70)
    print("Demo 3: Packet Slicing for Long Messages (5 points)")
    print("=" * 70)

    # Create cable and link
    cable = Cable(length=100, attenuation=0.1, noise_level=0.01, debug_mode=False)
    link = PhysicalLink(cable)
    dll = DataLinkLayer(link, max_payload_size=64)  # Small size for demo

    # Long message
    long_message = "This is a very long message that demonstrates the packet slicing " \
                   "capability of our network protocol. The message will be automatically " \
                   "split into multiple frames and reassembled at the receiver."

    print(f"\nOriginal message ({len(long_message)} bytes):")
    print(f"  '{long_message[:50]}...'")
    print()

    # Show slicing
    slicer = PacketSlicer(max_payload_size=64)
    slices = slicer.slice(long_message.encode('utf-8'))
    print(f"Sliced into {len(slices)} packets:")
    for i, s in enumerate(slices):
        print(f"  Packet {i}: {len(s)} bytes")

    # Transmit and receive
    print("\nTransmitting through data link layer...")
    data = long_message.encode('utf-8')
    received, success = dll.transmit_and_receive(data)

    print(f"\nReception Results:")
    print(f"  Original length: {len(data)} bytes")
    print(f"  Received length: {len(received) if received else 0} bytes")
    print(f"  Success: {success}")
    print(f"  Match: {data == received}")

    if received:
        print(f"\nReceived message:")
        print(f"  '{received.decode('utf-8')[:50]}...'")

    stats = dll.get_stats()
    print(f"\nTransmission Statistics:")
    print(f"  Frames sent: {stats['frames_sent']}")
    print(f"  Frames received: {stats['frames_received']}")
    print(f"  Checksum errors: {stats['checksum_errors']}")
    print()


def demo_error_detection():
    """
    Demo 4: Error detection mechanism (10 points)
    Shows checksum-based error detection.
    """
    print("=" * 70)
    print("Demo 4: Error Detection Mechanism (10 points)")
    print("=" * 70)

    # Test checksum
    print("\n1. Checksum Calculation:")
    test_data = b"Test data for checksum"
    checksum = compute_checksum(test_data)
    print(f"   Data: {test_data}")
    print(f"   Checksum: {checksum} (0x{checksum:02X})")

    # Create frame
    print("\n2. Frame with Error Detection:")
    frame = Frame(test_data)
    bits = frame.to_bits()
    print(f"   Frame size: {len(bits)} bits")
    print(f"   Frame checksum: {frame.checksum}")

    # Parse valid frame
    print("\n3. Valid Frame Parsing:")
    parsed = Frame.from_bits(bits)
    print(f"   Parsed successfully: {parsed.payload == test_data}")

    # Introduce error and detect
    print("\n4. Error Detection (corrupted frame):")
    corrupted = bits.copy()

    # Corrupt a bit in the payload
    corrupted[40] ^= 1
    try:
        Frame.from_bits(corrupted)
        print("   ERROR: Should have detected corruption!")
    except ChecksumError as e:
        print(f"   Correctly detected error!")
        print(f"   Error message: {e}")

    # Test with noisy channel
    print("\n5. Error Detection with Noisy Channel:")
    print("   (使用更高噪声来展示误码)")
    noise_levels = [0.5, 1.0, 1.5, 2.0]  # 更高噪声以展示效果

    for noise in noise_levels:
        cable = Cable(length=100, attenuation=0.1, noise_level=noise, debug_mode=False)
        link = PhysicalLink(cable)
        dll = DataLinkLayer(link)

        # Send multiple messages
        successes = 0
        errors = 0
        trials = 20

        for _ in range(trials):
            data = b"Error detection test message"
            received, success = dll.transmit_and_receive(data)
            if success and received == data:
                successes += 1
            else:
                errors += 1

        print(f"   Noise {noise:.2f}: Success rate = {successes/trials:.1%}, "
              f"Detected errors = {errors}")
    print()


def demo_noise_performance():
    """
    Demo 5: Performance under different noise levels
    Compares actual throughput with Shannon capacity.

    NOTE: Our system uses 100 samples per bit with averaging, which reduces
    effective noise by sqrt(100)=10x. This is a common noise reduction technique.
    To see actual errors, we need noise_level > 1.0
    """
    print("=" * 70)
    print("Demo 5: Performance vs Shannon Capacity")
    print("=" * 70)

    print("\n[NOTE] 每个bit使用100个采样点平均，有效降低噪声10倍")
    print("       这是通信系统常用的降噪技术")
    print("       要看到明显误码，需要 noise > 1.0\n")

    # 使用更大范围的噪声来展示效果
    noise_levels = [0.1, 0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0]
    results = []

    print("\nTesting different noise levels:")
    print("-" * 60)
    print(f"{'Noise':>8} {'SNR (dB)':>10} {'BER':>10} {'Shannon Cap':>12} {'Success':>10}")
    print("-" * 60)

    for noise in noise_levels:
        cable = Cable(length=100, attenuation=0.1, noise_level=noise, debug_mode=False)
        link = PhysicalLink(cable)

        # Measure throughput
        success_rate, ber = measure_throughput(link, num_trials=50, message_length=50)

        # Get SNR
        stats = cable.get_signal_stats()
        snr_db = stats.get('snr_db', 0)

        # Calculate Shannon capacity
        shannon_cap = calculate_shannon_capacity(snr_db)

        results.append({
            'noise': noise,
            'snr_db': snr_db,
            'ber': ber,
            'shannon_cap': shannon_cap,
            'success_rate': success_rate
        })

        print(f"{noise:>8.2f} {snr_db:>10.2f} {ber:>10.4%} {shannon_cap:>12.2f} {success_rate:>10.1%}")

    # Create visualization
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    noise_arr = [r['noise'] for r in results]
    snr_arr = [r['snr_db'] for r in results]
    ber_arr = [r['ber'] for r in results]
    shannon_arr = [r['shannon_cap'] for r in results]
    success_arr = [r['success_rate'] for r in results]

    # SNR vs Noise
    axes[0, 0].plot(noise_arr, snr_arr, 'bo-', linewidth=2, markersize=8)
    axes[0, 0].set_xlabel('Noise Level')
    axes[0, 0].set_ylabel('SNR (dB)')
    axes[0, 0].set_title('SNR vs Noise Level')
    axes[0, 0].grid(True, alpha=0.3)

    # BER vs Noise
    axes[0, 1].semilogy(noise_arr, [max(b, 1e-6) for b in ber_arr], 'ro-', linewidth=2, markersize=8)
    axes[0, 1].set_xlabel('Noise Level')
    axes[0, 1].set_ylabel('Bit Error Rate (log scale)')
    axes[0, 1].set_title('BER vs Noise Level')
    axes[0, 1].grid(True, alpha=0.3)

    # Shannon Capacity vs SNR
    axes[1, 0].plot(snr_arr, shannon_arr, 'go-', linewidth=2, markersize=8)
    axes[1, 0].set_xlabel('SNR (dB)')
    axes[1, 0].set_ylabel('Shannon Capacity (bits/symbol)')
    axes[1, 0].set_title('Shannon Capacity: C = B*log2(1+SNR)')
    axes[1, 0].grid(True, alpha=0.3)

    # Success Rate vs Noise
    axes[1, 1].plot(noise_arr, success_arr, 'mo-', linewidth=2, markersize=8)
    axes[1, 1].set_xlabel('Noise Level')
    axes[1, 1].set_ylabel('Success Rate')
    axes[1, 1].set_title('Transmission Success Rate')
    axes[1, 1].set_ylim(0, 1.1)
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('demo_level1_performance.png', dpi=150)
    print(f"\nPerformance visualization saved to: demo_level1_performance.png")
    plt.close()


def demo_waveform_visualization():
    """
    Demo 6: Waveform visualization
    Shows input and output signals through the cable.
    """
    print("=" * 70)
    print("Demo 6: Waveform Visualization")
    print("=" * 70)

    # Create cable with debug mode
    cable = Cable(length=100, attenuation=0.2, noise_level=0.1, debug_mode=False)

    # Create a recognizable pattern
    message = "Hi"
    bits = string_to_bits(message)
    signal = modulate_ook(bits)

    print(f"\nMessage: '{message}'")
    print(f"Bits: {bits}")
    print(f"Signal length: {len(signal)} samples")

    # Transmit
    received = cable.transmit(signal)

    # Get stats
    stats = cable.get_signal_stats()
    print(f"\nTransmission Statistics:")
    print(f"  Input mean: {stats['input_mean']:.4f}")
    print(f"  Output mean: {stats['output_mean']:.4f}")
    print(f"  SNR: {stats['snr_db']:.2f} dB")

    # Create detailed visualization
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))

    # Input signal with bit boundaries
    axes[0].plot(signal, 'b-', linewidth=1, label='Transmitted Signal')
    for i in range(len(bits)):
        axes[0].axvline(x=i*SAMPLES_PER_BIT, color='gray', linestyle='--', alpha=0.5)
        axes[0].text(i*SAMPLES_PER_BIT + SAMPLES_PER_BIT//2, 1.1, str(bits[i]),
                    ha='center', fontsize=10)
    axes[0].set_title(f"Transmitted Signal: '{message}' = {bits}")
    axes[0].set_ylabel('Amplitude')
    axes[0].set_ylim(-0.2, 1.3)
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # Output signal
    axes[1].plot(received, 'r-', linewidth=1, label='Received Signal')
    for i in range(len(bits)):
        axes[1].axvline(x=i*SAMPLES_PER_BIT, color='gray', linestyle='--', alpha=0.5)
    axes[1].axhline(y=np.mean(np.abs(received))*0.5, color='green', linestyle='-',
                   alpha=0.7, label='Decision Threshold')
    axes[1].set_title(f"Received Signal (SNR={stats['snr_db']:.1f}dB)")
    axes[1].set_xlabel('Sample')
    axes[1].set_ylabel('Amplitude')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('demo_level1_waveforms.png', dpi=150)
    print(f"\nWaveform visualization saved to: demo_level1_waveforms.png")
    plt.close()


def main():
    """Run all Level 1 demonstrations."""
    print("\n" + "=" * 70)
    print(" LEVEL 1: POINT-TO-POINT COMMUNICATION DEMONSTRATION")
    print(" Total: 30 points")
    print("=" * 70 + "\n")

    # Run all demos
    demo_basic_transmission()
    print()

    demo_bit_stream()
    print()

    demo_packet_slicing()
    print()

    demo_error_detection()
    print()

    demo_noise_performance()
    print()

    demo_waveform_visualization()

    print("\n" + "=" * 70)
    print(" LEVEL 1 DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\nGenerated files:")
    print("  - demo_level1_signals.png")
    print("  - demo_level1_performance.png")
    print("  - demo_level1_waveforms.png")
    print()


if __name__ == "__main__":
    main()
