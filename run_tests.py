"""
Test Runner for Network Communication Project
==============================================

Run all tests for Level 1, Level 2, and Level 3 features.

Usage:
    python run_tests.py           # Run all tests
    python run_tests.py level1    # Run Level 1 tests only
    python run_tests.py level2    # Run Level 2 tests only
    python run_tests.py level3    # Run Level 3 tests only
"""

import sys
import time
from typing import Callable, List, Tuple

# Import all modules
from cable import Cable
from physical_layer import (
    string_to_bits, bits_to_string, bytes_to_bits, bits_to_bytes,
    modulate_ook, demodulate_ook, PhysicalLink
)
from data_link_layer import (
    Frame, PacketSlicer, DataLinkLayer, compute_checksum,
    ChecksumError
)
from network_layer import (
    MACAddress, NetworkFrame, Host, Switch, StarTopology
)
from transport_layer import (
    TransportSegment, ReliableTransport, FLAG_ACK, FLAG_DATA
)
from channel_coding import HammingCode, CRC, CodedPhysicalLink
from application_layer import HTTPRequest, HTTPResponse, HTTPServer
from modulation_schemes import OOK, ASK, FSK, BPSK
from concurrency import ThreadedHost, ThreadedSwitch, ConcurrentNetwork


# =============================================================================
# Test Framework
# =============================================================================

class TestResult:
    """Test result container."""
    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message


class TestRunner:
    """Simple test runner."""

    def __init__(self):
        self.results: List[TestResult] = []

    def run_test(self, name: str, test_func: Callable) -> TestResult:
        """Run a single test."""
        try:
            test_func()
            result = TestResult(name, True)
        except AssertionError as e:
            result = TestResult(name, False, str(e))
        except Exception as e:
            result = TestResult(name, False, f"Exception: {e}")

        self.results.append(result)
        return result

    def print_summary(self, level: str = "All"):
        """Print test summary."""
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)

        print("\n" + "=" * 60)
        print(f"Test Summary - {level}")
        print("=" * 60)
        print(f"Passed: {passed}/{total} ({passed/total*100:.1f}%)")
        print()

        if any(not r.passed for r in self.results):
            print("Failed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")

        return passed == total


# =============================================================================
# Level 1 Tests
# =============================================================================

def test_string_to_bits():
    """Test string to bits conversion."""
    bits = string_to_bits("Hi")
    assert len(bits) == 16, f"Expected 16 bits, got {len(bits)}"
    recovered = bits_to_string(bits)
    assert recovered == "Hi", f"Expected 'Hi', got '{recovered}'"


def test_bytes_to_bits():
    """Test bytes to bits conversion."""
    data = b"\x00\xFF"
    bits = bytes_to_bits(data)
    assert len(bits) == 16
    assert bits[:8] == [0, 0, 0, 0, 0, 0, 0, 0]
    assert bits[8:] == [1, 1, 1, 1, 1, 1, 1, 1]


def test_ook_modulation_no_noise():
    """Test OOK modulation without noise."""
    cable = Cable(noise_level=0, attenuation=0)
    link = PhysicalLink(cable)

    bits = [1, 0, 1, 1, 0, 0, 1, 0]
    received = link.transmit_bits(bits)
    assert bits == received, f"Expected {bits}, got {received}"


def test_ook_string_transmission():
    """Test string transmission through physical layer."""
    cable = Cable(noise_level=0.01, attenuation=0.1)
    link = PhysicalLink(cable)

    message = "Hello"
    received = link.transmit_data(message)
    assert message == received, f"Expected '{message}', got '{received}'"


def test_frame_creation():
    """Test frame creation and parsing."""
    payload = b"Test payload"
    frame = Frame(payload)
    bits = frame.to_bits()

    parsed = Frame.from_bits(bits)
    assert parsed.payload == payload


def test_checksum_detection():
    """Test checksum error detection."""
    frame = Frame(b"Test data")
    bits = frame.to_bits()

    # Corrupt a bit
    bits[30] ^= 1

    try:
        Frame.from_bits(bits)
        assert False, "Should have raised ChecksumError"
    except ChecksumError:
        pass  # Expected


def test_packet_slicing():
    """Test packet slicing and reassembly."""
    slicer = PacketSlicer(max_payload_size=50)
    data = b"A" * 200

    slices = slicer.slice(data)
    assert len(slices) > 1

    reassembled = slicer.reassemble(slices)
    assert data == reassembled


def test_data_link_transmission():
    """Test complete data link layer transmission."""
    cable = Cable(noise_level=0, attenuation=0.1)
    link = PhysicalLink(cable)
    dll = DataLinkLayer(link)

    data = b"Test message"
    received, success = dll.transmit_and_receive(data)
    assert success
    assert data == received


def run_level1_tests() -> bool:
    """Run all Level 1 tests."""
    runner = TestRunner()

    print("\n" + "=" * 60)
    print("LEVEL 1 TESTS: Point-to-Point Communication")
    print("=" * 60)

    tests = [
        ("String to bits conversion", test_string_to_bits),
        ("Bytes to bits conversion", test_bytes_to_bits),
        ("OOK modulation (no noise)", test_ook_modulation_no_noise),
        ("String transmission", test_ook_string_transmission),
        ("Frame creation/parsing", test_frame_creation),
        ("Checksum error detection", test_checksum_detection),
        ("Packet slicing", test_packet_slicing),
        ("Data link transmission", test_data_link_transmission),
    ]

    for name, test_func in tests:
        result = runner.run_test(name, test_func)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {name}")

    return runner.print_summary("Level 1")


# =============================================================================
# Level 2 Tests
# =============================================================================

def test_mac_address():
    """Test MAC address validation and conversion."""
    mac = MACAddress("00:11:22:33:44:55")
    assert str(mac) == "00:11:22:33:44:55"

    bits = mac.to_bits()
    assert len(bits) == 48

    recovered = MACAddress.from_bits(bits)
    assert mac == recovered


def test_mac_validation():
    """Test MAC address validation."""
    try:
        MACAddress("invalid")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_network_frame():
    """Test network frame with addressing."""
    frame = NetworkFrame(
        src_mac="00:00:00:00:00:01",
        dst_mac="00:00:00:00:00:02",
        payload=b"Hello"
    )

    bits = frame.to_bits()
    parsed = NetworkFrame.from_bits(bits)

    assert str(parsed.src_mac) == "00:00:00:00:00:01"
    assert str(parsed.dst_mac) == "00:00:00:00:00:02"
    assert parsed.payload == b"Hello"


def test_star_topology():
    """Test star topology creation."""
    topology = StarTopology(num_hosts=4)
    assert len(topology.hosts) == 4

    for mac, host in topology.hosts.items():
        assert host.switch is not None
        assert host.cable is not None


def test_multihost_communication():
    """Test communication between multiple hosts."""
    topology = StarTopology(num_hosts=3)
    host1 = topology.get_host("00:00:00:00:00:01")
    host2 = topology.get_host("00:00:00:00:00:02")

    host1.send_string("00:00:00:00:00:02", "Hello Host2")

    received = host2.get_all_received()
    assert len(received) == 1
    assert received[0].payload == b"Hello Host2"


def test_mac_learning():
    """Test switch MAC learning."""
    topology = StarTopology(num_hosts=2)
    host1 = topology.get_host("00:00:00:00:00:01")

    # Initially empty
    assert len(topology.switch.mac_table) == 0

    # Send message - should learn source MAC
    host1.send_string("00:00:00:00:00:02", "Test")

    assert "00:00:00:00:00:01" in topology.switch.mac_table


def test_broadcast():
    """Test broadcast addressing."""
    topology = StarTopology(num_hosts=3)
    host1 = topology.get_host("00:00:00:00:00:01")

    host1.send_string("FF:FF:FF:FF:FF:FF", "Broadcast")

    # All other hosts should receive
    for mac, host in topology.hosts.items():
        if mac != "00:00:00:00:00:01":
            received = host.get_all_received()
            assert len(received) >= 1


def run_level2_tests() -> bool:
    """Run all Level 2 tests."""
    runner = TestRunner()

    print("\n" + "=" * 60)
    print("LEVEL 2 TESTS: Multi-Host Communication")
    print("=" * 60)

    tests = [
        ("MAC address creation", test_mac_address),
        ("MAC address validation", test_mac_validation),
        ("Network frame", test_network_frame),
        ("Star topology", test_star_topology),
        ("Multi-host communication", test_multihost_communication),
        ("MAC learning", test_mac_learning),
        ("Broadcast", test_broadcast),
    ]

    for name, test_func in tests:
        result = runner.run_test(name, test_func)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {name}")

    return runner.print_summary("Level 2")


# =============================================================================
# Level 3 Tests
# =============================================================================

def test_transport_segment():
    """Test transport segment serialization."""
    segment = TransportSegment(
        seq_num=42,
        ack_num=10,
        flags=FLAG_DATA,
        payload=b"Test"
    )

    data = segment.to_bytes()
    parsed = TransportSegment.from_bytes(data)

    assert parsed.seq_num == 42
    assert parsed.ack_num == 10
    assert parsed.is_data()
    assert parsed.payload == b"Test"


def test_reliable_transport():
    """Test reliable transport with ACK."""
    topology = StarTopology(num_hosts=2)
    host1 = topology.get_host("00:00:00:00:00:01")
    host2 = topology.get_host("00:00:00:00:00:02")

    transport1 = ReliableTransport(host1, timeout=0.5)
    transport2 = ReliableTransport(host2, timeout=0.5)

    received = []
    transport2.on_receive = lambda data, src: received.append(data)

    success = transport1.send_string("00:00:00:00:00:02", "Test")

    # Process frames
    for _ in range(10):
        frame = host2.get_received()
        if frame:
            transport2._handle_receive(frame)

    assert success
    assert transport1.stats['acks_received'] > 0


def test_hamming_encode_decode():
    """Test Hamming code encoding/decoding."""
    hamming = HammingCode()
    data = [1, 0, 1, 1]

    encoded = hamming.encode(data)
    decoded = hamming.decode(encoded)

    assert decoded[:4] == data


def test_hamming_error_correction():
    """Test Hamming single-bit error correction."""
    hamming = HammingCode()
    data = [1, 0, 1, 1]

    encoded = hamming.encode(data)
    encoded[3] ^= 1  # Introduce error

    decoded = hamming.decode(encoded)
    assert decoded[:4] == data


def test_crc():
    """Test CRC checksum."""
    crc = CRC()
    data = b"Test data"

    checksum = crc.compute(data)
    assert crc.verify(data, checksum)

    # Corrupted should fail
    corrupted = bytearray(data)
    corrupted[0] ^= 1
    assert not crc.verify(bytes(corrupted), checksum)


def test_http_request():
    """Test HTTP request serialization."""
    request = HTTPRequest(
        method="GET",
        path="/api",
        headers={"Accept": "text/html"}
    )

    data = request.to_bytes()
    parsed = HTTPRequest.from_bytes(data)

    assert parsed.method == "GET"
    assert parsed.path == "/api"


def test_http_response():
    """Test HTTP response serialization."""
    response = HTTPResponse.ok("Hello")

    data = response.to_bytes()
    parsed = HTTPResponse.from_bytes(data)

    assert parsed.status_code == 200
    assert parsed.body == "Hello"


def test_modulation_schemes():
    """Test different modulation schemes."""
    bits = [1, 0, 1, 1, 0, 0, 1, 0]

    for scheme in [OOK(), ASK(), FSK(), BPSK()]:
        signal = scheme.modulate(bits)
        decoded = scheme.demodulate(signal)
        assert decoded[:len(bits)] == bits, f"{scheme.name} failed"


def test_concurrency():
    """Test concurrent network."""
    network = ConcurrentNetwork(num_hosts=2)
    network.start()
    time.sleep(0.1)

    host1 = network.get_host("00:00:00:00:00:01")
    host1.send_string("00:00:00:00:00:02", "Test")

    time.sleep(0.3)

    host2 = network.get_host("00:00:00:00:00:02")
    received = host2.receive_nowait()

    network.stop()

    assert received is not None


def run_level3_tests() -> bool:
    """Run all Level 3 tests."""
    runner = TestRunner()

    print("\n" + "=" * 60)
    print("LEVEL 3 TESTS: Extension Features")
    print("=" * 60)

    tests = [
        ("Transport segment", test_transport_segment),
        ("Reliable transport", test_reliable_transport),
        ("Hamming encode/decode", test_hamming_encode_decode),
        ("Hamming error correction", test_hamming_error_correction),
        ("CRC checksum", test_crc),
        ("HTTP request", test_http_request),
        ("HTTP response", test_http_response),
        ("Modulation schemes", test_modulation_schemes),
        ("Concurrency", test_concurrency),
    ]

    for name, test_func in tests:
        result = runner.run_test(name, test_func)
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {name}")

    return runner.print_summary("Level 3")


# =============================================================================
# Main
# =============================================================================

def main():
    """Run tests based on command line arguments."""
    args = sys.argv[1:] if len(sys.argv) > 1 else ["all"]

    print("\n" + "=" * 60)
    print("Network Communication Project - Test Suite")
    print("=" * 60)

    results = {}

    for arg in args:
        arg = arg.lower()

        if arg in ["all", "level1", "1"]:
            results["Level 1"] = run_level1_tests()

        if arg in ["all", "level2", "2"]:
            results["Level 2"] = run_level2_tests()

        if arg in ["all", "level3", "3"]:
            results["Level 3"] = run_level3_tests()

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)

    all_passed = True
    for level, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {level}: {status}")
        all_passed = all_passed and passed

    print()
    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed!")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
