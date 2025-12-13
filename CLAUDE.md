# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Data Communication and Networks course project implementing network communication from the physical layer up. The project has three levels:

- **Level 1**: Point-to-point communication (modulation/demodulation, bit stream transmission)
- **Level 2**: Multi-host communication with star topology (addressing, routing/forwarding via switch)
- **Level 3**: Extension features (transport layer, channel coding, application protocols, etc.)

## Running the Code

```bash
# Run the Cable class example (physical layer simulation)
python cable.py

# Run bus topology example
python skeleton_bus.py

# Run switch topology example
python skeleton_switch.py
```

## Architecture

### Physical Layer: `cable.py`
The `Cable` class is the **only course-provided infrastructure** simulating the physical transmission medium. It:
- Transmits analog signals (numpy arrays)
- Applies attenuation using exponential model
- Adds Gaussian white noise
- Provides debug mode for waveform visualization

Key parameters: `length`, `attenuation`, `noise_level`, `debug_mode`

### Network Topologies: `lib.py`

**Bus Topology** (`Bus` class):
- Simple broadcast model where all hosts receive all packets
- Hosts filter packets by destination MAC address

**Switch Topology** (`SwitchFabric` + `Switch` classes):
- MAC address learning on packet arrival
- Forwarding based on MAC table lookup
- Broadcasts to all interfaces when destination is unknown

### Host Implementations

**`skeleton_bus.py`**: Hosts connected via shared bus, using broadcast
**`skeleton_switch.py`**: Hosts connected via switch with interface numbers, using MAC-based forwarding

### Packet Structure
```python
Packet(src=MAC, dst=MAC, payload=data)
```
MAC addresses use standard format: `00:00:00:00:00:01`

## Implementation Notes

- Modulation converts bits to analog signals (numpy arrays); demodulation recovers bits
- Each bit can be represented by multiple sample points in the analog signal
- The Cable class does NOT handle digital-to-analog conversion - you must implement modulation/demodulation
- Error detection/correction mechanisms needed for noisy channels
- Compare throughput with Shannon formula: B * log2(1 + SNR)
