# Network Communication Project - Usage Guide

## Environment Setup

```bash
# Activate conda environment
conda activate shelm

# Or use python3 directly if conda activate doesn't work:
python3 <script_name>.py
```

## Project Structure

```
network-communication-project/
├── cable.py                 # Physical layer simulation (provided)
├── physical_layer.py        # Level 1: Modulation/demodulation
├── data_link_layer.py       # Level 1: Frame formatting, error detection
├── network_layer.py         # Level 2: MAC addressing, switching
├── transport_layer.py       # Level 3: Reliable transport (ARQ)
├── channel_coding.py        # Level 3: Hamming code, CRC
├── application_layer.py     # Level 3: HTTP-like protocol
├── modulation_schemes.py    # Level 3: OOK, ASK, FSK, BPSK
├── concurrency.py           # Level 3: Multi-threaded network
├── demo_level1.py           # Level 1 demonstration
├── demo_level2.py           # Level 2 demonstration
├── demo_level3.py           # Level 3 demonstration
├── run_tests.py             # Test runner
└── USAGE.md                 # This file
```

---

## Running Tests

### Run All Tests
```bash
python3 run_tests.py
```

### Run Tests by Level
```bash
python3 run_tests.py level1    # Level 1 tests only
python3 run_tests.py level2    # Level 2 tests only
python3 run_tests.py level3    # Level 3 tests only
```

Expected output:
```
============================================================
FINAL SUMMARY
============================================================
  Level 1: PASS
  Level 2: PASS
  Level 3: PASS

All tests passed!
```

---

## Level 1: Point-to-Point Communication (30 points)

### Features
- String to bits conversion (ASCII encoding)
- OOK (On-Off Keying) modulation/demodulation
- Frame formatting with preamble, checksum, postamble
- Packet slicing for long messages
- Error detection using XOR checksum

### Run Demo
```bash
python3 demo_level1.py
```

### Key Components

```python
from physical_layer import PhysicalLink, string_to_bits, bits_to_string
from data_link_layer import Frame, PacketSlicer, DataLinkLayer
from cable import Cable

# Basic transmission
cable = Cable(noise_level=0.01, attenuation=0.1)
link = PhysicalLink(cable)
received = link.transmit_data("Hello World")

# Frame transmission with error detection
dll = DataLinkLayer(link)
data, success = dll.transmit_and_receive(b"Test message")
```

### Demo Output
The demo shows:
1. Basic string transmission through noisy channel
2. Long message slicing and reassembly
3. Shannon capacity comparison
4. Waveform visualization (saves `level1_waveform.png`)

---

## Level 2: Multi-Host Communication (30 points)

### Features
- MAC address handling (48-bit, format XX:XX:XX:XX:XX:XX)
- Star topology with central switch
- MAC learning and forwarding table
- Broadcast support (FF:FF:FF:FF:FF:FF)

### Run Demo
```bash
python3 demo_level2.py
```

### Key Components

```python
from network_layer import StarTopology, Host, Switch, MACAddress

# Create star topology with 4 hosts
topology = StarTopology(num_hosts=4)

# Get hosts by MAC address
host1 = topology.get_host("00:00:00:00:00:01")
host2 = topology.get_host("00:00:00:00:00:02")

# Send message
host1.send_string("00:00:00:00:00:02", "Hello Host2")

# Receive message
frame = host2.get_received()
print(frame.payload)  # b"Hello Host2"

# Broadcast to all hosts
host1.send_string("FF:FF:FF:FF:FF:FF", "Broadcast message")
```

### Demo Output
The demo shows:
1. Network topology creation
2. Point-to-point communication between hosts
3. MAC learning process
4. Broadcast functionality
5. Topology diagram (saves `level2_topology.png`)

---

## Level 3: Extension Features (40 points)

### 3.1 Transport Layer (15 points)

**Features:**
- Stop-and-Wait ARQ protocol
- ACK/NACK mechanism
- Timeout and retransmission
- Sequence number tracking

```python
from network_layer import StarTopology
from transport_layer import ReliableTransport

topology = StarTopology(num_hosts=2)
host1 = topology.get_host("00:00:00:00:00:01")
host2 = topology.get_host("00:00:00:00:00:02")

transport1 = ReliableTransport(host1, timeout=0.5)
transport2 = ReliableTransport(host2, timeout=0.5)

# Set receive callback
transport2.on_receive = lambda data, src: print(f"Received: {data}")

# Send with reliability
success = transport1.send_string("00:00:00:00:00:02", "Hello")
```

### 3.2 Channel Coding (15 points)

**Features:**
- Hamming(7,4) code for single-bit error correction
- CRC-8 for error detection
- Performance comparison with/without coding

```python
from channel_coding import HammingCode, CRC, CodedPhysicalLink
from cable import Cable

# Hamming code
hamming = HammingCode()
data = [1, 0, 1, 1]
encoded = hamming.encode(data)
# Introduce error
encoded[3] ^= 1
decoded = hamming.decode(encoded)  # Error corrected

# CRC
crc = CRC()
checksum = crc.compute(b"Test data")
valid = crc.verify(b"Test data", checksum)

# Coded physical link
cable = Cable(noise_level=0.1)
coded_link = CodedPhysicalLink(cable)
received = coded_link.transmit_data("Hello")
```

### 3.3 Application Layer (10 points)

**Features:**
- HTTP-like request/response protocol
- GET/POST methods
- Path-based routing
- Built-in file and JSON API servers

```python
from application_layer import HTTPServer, HTTPClient, HTTPRequest, HTTPResponse

# Create server
server = HTTPServer()

@server.route("/hello")
def hello_handler(request):
    return HTTPResponse.ok(f"Hello, {request.path}")

# Process request
request = HTTPRequest(method="GET", path="/hello")
response = server.handle(request)
print(response.body)  # "Hello, /hello"
```

### 3.4 Modulation Schemes (10 points)

**Features:**
- OOK (On-Off Keying)
- ASK (Amplitude Shift Keying)
- FSK (Frequency Shift Keying)
- BPSK (Binary Phase Shift Keying)
- Performance comparison across noise levels

```python
from modulation_schemes import OOK, ASK, FSK, BPSK, ModulationComparator

# Use different modulation schemes
ook = OOK()
ask = ASK()
fsk = FSK()
bpsk = BPSK()

bits = [1, 0, 1, 1, 0, 0, 1, 0]
signal = bpsk.modulate(bits)
decoded = bpsk.demodulate(signal)

# Compare performance
comparator = ModulationComparator()
results = comparator.compare_ber([0.05, 0.1, 0.15, 0.2])
```

### 3.5 Concurrency (10 points)

**Features:**
- Multi-threaded hosts with send/receive threads
- Thread-safe switch with worker pool
- Non-blocking I/O

```python
from concurrency import ConcurrentNetwork

# Create concurrent network
network = ConcurrentNetwork(num_hosts=3)
network.start()

# Get hosts
host1 = network.get_host("00:00:00:00:00:01")
host2 = network.get_host("00:00:00:00:00:02")

# Send message (non-blocking)
host1.send_string("00:00:00:00:00:02", "Hello")

# Receive (with timeout)
frame = host2.receive(timeout=1.0)

# Cleanup
network.stop()
```

### Run Level 3 Demo
```bash
python3 demo_level3.py
```

The demo shows:
1. Reliable transport with ACK/retransmission
2. Hamming code error correction
3. HTTP server/client communication
4. Modulation scheme comparison (saves `modulation_comparison.png`)
5. Concurrent network communication

---

## Output Files

Running the demos generates these visualization files:

| File | Description |
|------|-------------|
| `level1_waveform.png` | OOK modulation waveform |
| `level2_topology.png` | Star topology diagram |
| `modulation_comparison.png` | BER comparison of modulation schemes |

---

## API Reference

### Physical Layer (`physical_layer.py`)

| Function/Class | Description |
|----------------|-------------|
| `string_to_bits(text)` | Convert string to bit list |
| `bits_to_string(bits)` | Convert bit list to string |
| `bytes_to_bits(data)` | Convert bytes to bit list |
| `bits_to_bytes(bits)` | Convert bit list to bytes |
| `modulate_ook(bits)` | OOK modulation |
| `demodulate_ook(signal)` | OOK demodulation |
| `PhysicalLink` | Physical layer transmission |

### Data Link Layer (`data_link_layer.py`)

| Class | Description |
|-------|-------------|
| `Frame` | Frame with preamble/checksum/postamble |
| `PacketSlicer` | Slice large packets into frames |
| `DataLinkLayer` | Complete data link layer |

### Network Layer (`network_layer.py`)

| Class | Description |
|-------|-------------|
| `MACAddress` | MAC address handling |
| `NetworkFrame` | Frame with MAC addressing |
| `Host` | Network host |
| `Switch` | Network switch with MAC learning |
| `StarTopology` | Helper for star topology |

### Transport Layer (`transport_layer.py`)

| Class | Description |
|-------|-------------|
| `TransportSegment` | Transport layer segment |
| `ReliableTransport` | Stop-and-Wait ARQ |
| `SlidingWindowTransport` | Go-Back-N protocol |

### Channel Coding (`channel_coding.py`)

| Class | Description |
|-------|-------------|
| `HammingCode` | Hamming(7,4) encoding |
| `CRC` | CRC-8 checksum |
| `CodedPhysicalLink` | Physical link with coding |

### Application Layer (`application_layer.py`)

| Class | Description |
|-------|-------------|
| `HTTPRequest` | HTTP request |
| `HTTPResponse` | HTTP response |
| `HTTPServer` | HTTP server with routing |
| `HTTPClient` | HTTP client |

### Modulation (`modulation_schemes.py`)

| Class | Description |
|-------|-------------|
| `OOK` | On-Off Keying |
| `ASK` | Amplitude Shift Keying |
| `FSK` | Frequency Shift Keying |
| `BPSK` | Binary Phase Shift Keying |
| `ModulationComparator` | Compare modulation schemes |

### Concurrency (`concurrency.py`)

| Class | Description |
|-------|-------------|
| `ThreadedHost` | Multi-threaded host |
| `ThreadedSwitch` | Multi-threaded switch |
| `ConcurrentNetwork` | Complete concurrent network |

---

## Troubleshooting

### Conda activation error
```
CondaError: Run 'conda init' before 'conda activate'
```
**Solution:** Use `python3` directly instead of activating conda:
```bash
python3 run_tests.py
```

### Import errors
Ensure all files are in the same directory and run from the project root:
```bash
cd /home/ouyangzl/network-communication-project
python3 run_tests.py
```

### Matplotlib display issues
If running in a headless environment, the demos will save plots to files instead of displaying them. Check for `*.png` files in the project directory.

---

## Score Summary

| Level | Feature | Points |
|-------|---------|--------|
| 1 | Point-to-Point Communication | 30 |
| 2 | Multi-Host Communication | 30 |
| 3 | Transport Layer | 15 |
| 3 | Channel Coding | 15 |
| 3 | Application Layer | 10 |
| 3 | Modulation Comparison | 10 |
| 3 | Concurrency | 10 |
| **Total** | | **120** |

Note: Maximum score is typically 100 points. Level 3 features are extension features.
