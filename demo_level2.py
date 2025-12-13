"""
Level 2 Demonstration: Multi-Host Communication
================================================

This demo shows:
1. Star topology network creation
2. MAC addressing mechanism
3. Switch MAC learning and forwarding
4. Multi-host communication
5. Broadcast handling
6. Routing verification

Requirements:
- Distinguish different hosts (15 points)
- Correctly route to target host (15 points)
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from network_layer import (
    Host, Switch, MACAddress, NetworkFrame,
    StarTopology, MAC_BROADCAST
)


def demo_star_topology():
    """
    Demo 1: Star topology network creation
    Shows how to create a network with multiple hosts connected to a switch.
    """
    print("=" * 70)
    print("Demo 1: Star Topology Network Creation")
    print("=" * 70)

    # Create switch
    switch = Switch(num_ports=8, name="MainSwitch")
    print(f"\nCreated switch: {switch}")
    print(f"  Number of ports: {switch.num_ports}")

    # Create and connect hosts
    hosts = []
    for i in range(4):
        mac = f"00:00:00:00:00:{i+1:02X}"
        host = Host(mac, name=f"PC{i+1}")
        host.connect_to_switch(switch, port_id=i)
        hosts.append(host)
        print(f"\n  Connected {host.name}:")
        print(f"    MAC Address: {host.mac}")
        print(f"    Port: {host.port_id}")

    print(f"\nNetwork topology:")
    print("""
                    [MainSwitch]
                   /  |   |   \\
                  /   |   |    \\
               PC1  PC2  PC3   PC4
    """)

    # Create visualization
    create_topology_visualization(switch, hosts)
    print("\n  Topology visualization saved to: demo_level2_topology.png")


def demo_mac_addressing():
    """
    Demo 2: MAC addressing mechanism
    Shows how hosts are distinguished by their MAC addresses.
    """
    print("\n" + "=" * 70)
    print("Demo 2: MAC Addressing Mechanism (15 points)")
    print("=" * 70)

    # Create network
    topology = StarTopology(num_hosts=4)

    print("\nHost identification by MAC address:")
    print("-" * 50)
    print(f"{'Host Name':<12} {'MAC Address':<20} {'Port':<6}")
    print("-" * 50)

    for mac, host in topology.hosts.items():
        print(f"{host.name:<12} {mac:<20} {host.port_id:<6}")

    # Test MAC address validation
    print("\n\nMAC Address Validation:")
    test_macs = [
        "00:11:22:33:44:55",  # Valid
        "AA:BB:CC:DD:EE:FF",  # Valid
        "invalid",            # Invalid
        "00:11:22:33:44",     # Invalid (too short)
        "00:11:22:33:44:55:66",  # Invalid (too long)
    ]

    for mac in test_macs:
        try:
            addr = MACAddress(mac)
            print(f"  '{mac}' -> Valid ({addr})")
        except ValueError as e:
            print(f"  '{mac}' -> Invalid")

    # Test broadcast address
    print(f"\n  Broadcast address: {MAC_BROADCAST}")
    broadcast = MACAddress(MAC_BROADCAST)
    print(f"  Is broadcast: {broadcast.is_broadcast()}")


def demo_mac_learning():
    """
    Demo 3: Switch MAC learning and forwarding
    Shows how the switch learns MAC addresses and builds its forwarding table.
    """
    print("\n" + "=" * 70)
    print("Demo 3: Switch MAC Learning Process")
    print("=" * 70)

    # Create network with 4 hosts
    topology = StarTopology(num_hosts=4)
    switch = topology.switch

    # Clear logs for clean output
    switch.clear_logs()

    print("\nInitial MAC table (empty):")
    switch.print_mac_table()

    # Host 1 sends to Host 2 (destination unknown, will broadcast)
    print("\nStep 1: Host1 sends to Host2")
    print("  (Destination unknown - switch will broadcast)")
    host1 = topology.get_host("00:00:00:00:00:01")
    host1.send_string("00:00:00:00:00:02", "Message 1")

    print("\nMAC table after Step 1:")
    switch.print_mac_table()

    # Host 2 replies to Host 1 (now Host 1's MAC is known)
    print("\nStep 2: Host2 replies to Host1")
    print("  (Host1 MAC is now known - switch will forward directly)")
    host2 = topology.get_host("00:00:00:00:00:02")
    host2.send_string("00:00:00:00:00:01", "Reply from Host2")

    print("\nMAC table after Step 2:")
    switch.print_mac_table()

    # Host 3 sends to Host 4
    print("\nStep 3: Host3 sends to Host4")
    host3 = topology.get_host("00:00:00:00:00:03")
    host3.send_string("00:00:00:00:00:04", "Hello Host4")

    # Host 4 replies
    print("\nStep 4: Host4 replies to Host3")
    host4 = topology.get_host("00:00:00:00:00:04")
    host4.send_string("00:00:00:00:00:03", "Hello Host3")

    print("\nFinal MAC table (all hosts learned):")
    switch.print_mac_table()

    # Show switch logs
    print("\nSwitch Learning Log:")
    print("-" * 50)
    for log in switch.get_logs():
        print(f"  {log}")


def demo_multihost_communication():
    """
    Demo 4: Multi-host communication
    Shows message exchange between multiple hosts.
    """
    print("\n" + "=" * 70)
    print("Demo 4: Multi-Host Communication (15 points)")
    print("=" * 70)

    # Create network
    topology = StarTopology(num_hosts=5)

    print("\nNetwork setup:")
    for mac, host in topology.hosts.items():
        print(f"  {host.name}: {mac}")

    # Communication scenarios
    print("\n" + "-" * 50)
    print("Communication Scenarios:")
    print("-" * 50)

    # Scenario 1: One-to-one
    print("\n[Scenario 1] One-to-One Communication:")
    host1 = topology.get_host("00:00:00:00:00:01")
    host2 = topology.get_host("00:00:00:00:00:02")

    host1.send_string("00:00:00:00:00:02", "Hello Host2, this is Host1!")

    received = host2.get_all_received()
    print(f"  Host1 -> Host2: 'Hello Host2, this is Host1!'")
    for frame in received:
        print(f"  Host2 received from {frame.src_mac}: '{frame.payload.decode()}'")

    # Scenario 2: Multiple destinations
    print("\n[Scenario 2] One-to-Many Communication:")
    host3 = topology.get_host("00:00:00:00:00:03")

    targets = ["00:00:00:00:00:01", "00:00:00:00:00:02", "00:00:00:00:00:04"]
    for i, target in enumerate(targets):
        host3.send_string(target, f"Message {i+1} from Host3")
        print(f"  Host3 -> {target}")

    # Check received messages
    for mac, host in topology.hosts.items():
        received = host.get_all_received()
        if received:
            for frame in received:
                print(f"  {host.name} received: '{frame.payload.decode()}'")

    # Scenario 3: Bidirectional communication
    print("\n[Scenario 3] Bidirectional Communication:")
    host4 = topology.get_host("00:00:00:00:00:04")
    host5 = topology.get_host("00:00:00:00:00:05")

    # Exchange messages
    host4.send_string("00:00:00:00:00:05", "Hello from Host4")
    host5.send_string("00:00:00:00:00:04", "Hello from Host5")

    print("  Host4 <-> Host5 message exchange:")
    for host in [host4, host5]:
        received = host.get_all_received()
        for frame in received:
            print(f"    {host.name} received from {frame.src_mac}: '{frame.payload.decode()}'")


def demo_broadcast():
    """
    Demo 5: Broadcast handling
    Shows how broadcast messages reach all hosts.
    """
    print("\n" + "=" * 70)
    print("Demo 5: Broadcast Handling")
    print("=" * 70)

    # Create network
    topology = StarTopology(num_hosts=4)

    print("\nBroadcast message from Host1 to all hosts:")
    host1 = topology.get_host("00:00:00:00:00:01")

    # Send broadcast
    host1.send_string(MAC_BROADCAST, "Broadcast: Hello everyone!")
    print(f"  Host1 -> {MAC_BROADCAST}: 'Broadcast: Hello everyone!'")

    # Check all hosts
    print("\nReceipt status:")
    for mac, host in topology.hosts.items():
        received = host.get_all_received()
        if received:
            for frame in received:
                print(f"  {host.name} ({mac}): Received broadcast")
        else:
            if host == host1:
                print(f"  {host.name} ({mac}): Sender (did not receive own broadcast)")


def demo_routing_verification():
    """
    Demo 6: Routing verification
    Verifies that frames are correctly routed to destinations.
    """
    print("\n" + "=" * 70)
    print("Demo 6: Routing Verification")
    print("=" * 70)

    # Create network
    topology = StarTopology(num_hosts=5)
    switch = topology.switch

    # First, populate MAC table by having all hosts send once
    print("\nPopulating MAC table...")
    for mac, host in topology.hosts.items():
        # Send to a known destination to learn all MACs
        host.send_string("00:00:00:00:00:01", "Init")

    # Clear receive buffers
    for mac, host in topology.hosts.items():
        host.get_all_received()

    switch.clear_logs()

    print("\nMAC table fully populated:")
    switch.print_mac_table()

    # Now test precise routing
    print("\nRouting Test: Host1 sends different messages to each host")
    print("-" * 50)

    host1 = topology.get_host("00:00:00:00:00:01")
    messages_sent = {}

    for i in range(2, 6):
        dst_mac = f"00:00:00:00:00:{i:02X}"
        message = f"Unique message for Host{i}"
        host1.send_string(dst_mac, message)
        messages_sent[dst_mac] = message
        print(f"  Sent to {dst_mac}: '{message}'")

    print("\nVerification:")
    all_correct = True
    for mac, host in topology.hosts.items():
        if mac == "00:00:00:00:00:01":
            continue

        received = host.get_all_received()
        expected = messages_sent.get(mac)

        if received:
            actual = received[0].payload.decode()
            correct = actual == expected
            status = "CORRECT" if correct else "WRONG"
            print(f"  {host.name} ({mac}): {status}")
            if not correct:
                print(f"    Expected: '{expected}'")
                print(f"    Got: '{actual}'")
                all_correct = False
        else:
            print(f"  {host.name} ({mac}): NOT RECEIVED")
            all_correct = False

    print(f"\nRouting verification: {'PASSED' if all_correct else 'FAILED'}")

    # Show statistics
    print("\nSwitch Statistics:")
    stats = switch.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")


def demo_statistics():
    """
    Demo 7: Network statistics
    Shows detailed statistics for network operation.
    """
    print("\n" + "=" * 70)
    print("Demo 7: Network Statistics")
    print("=" * 70)

    # Create network and generate traffic
    topology = StarTopology(num_hosts=4)

    # Generate some traffic
    for i in range(10):
        src_idx = i % 4 + 1
        dst_idx = (i + 1) % 4 + 1
        src_mac = f"00:00:00:00:00:{src_idx:02X}"
        dst_mac = f"00:00:00:00:00:{dst_idx:02X}"

        host = topology.get_host(src_mac)
        if host:
            host.send_string(dst_mac, f"Test message {i}")

    # Clear receive buffers
    for mac, host in topology.hosts.items():
        host.get_all_received()

    print("\nSwitch Statistics:")
    print("-" * 40)
    stats = topology.switch.get_stats()
    print(f"  Frames received:    {stats['frames_received']}")
    print(f"  Frames forwarded:   {stats['frames_forwarded']}")
    print(f"  Frames broadcast:   {stats['frames_broadcast']}")
    print(f"  MAC table updates:  {stats['mac_table_updates']}")

    print("\nHost Statistics:")
    print("-" * 50)
    print(f"{'Host':<10} {'Sent':<8} {'Received':<10} {'TX Bytes':<10} {'RX Bytes':<10}")
    print("-" * 50)
    for mac, host in topology.hosts.items():
        stats = host.get_stats()
        print(f"{host.name:<10} {stats['frames_sent']:<8} {stats['frames_received']:<10} "
              f"{stats['bytes_sent']:<10} {stats['bytes_received']:<10}")


def create_topology_visualization(switch, hosts):
    """Create visualization of star topology."""
    fig, ax = plt.subplots(figsize=(10, 8))

    # Switch position
    switch_x, switch_y = 0.5, 0.5

    # Draw switch
    switch_rect = mpatches.FancyBboxPatch(
        (switch_x - 0.1, switch_y - 0.05), 0.2, 0.1,
        boxstyle="round,pad=0.02",
        facecolor='lightblue',
        edgecolor='blue',
        linewidth=2
    )
    ax.add_patch(switch_rect)
    ax.text(switch_x, switch_y, switch.name, ha='center', va='center',
            fontsize=10, fontweight='bold')

    # Host positions in a circle around switch
    num_hosts = len(hosts)
    import math
    radius = 0.35

    for i, host in enumerate(hosts):
        angle = 2 * math.pi * i / num_hosts - math.pi / 2
        hx = switch_x + radius * math.cos(angle)
        hy = switch_y + radius * math.sin(angle)

        # Draw host
        host_rect = mpatches.FancyBboxPatch(
            (hx - 0.08, hy - 0.06), 0.16, 0.12,
            boxstyle="round,pad=0.02",
            facecolor='lightgreen',
            edgecolor='green',
            linewidth=2
        )
        ax.add_patch(host_rect)

        # Host label
        ax.text(hx, hy + 0.02, host.name, ha='center', va='center',
                fontsize=9, fontweight='bold')
        ax.text(hx, hy - 0.02, str(host.mac)[-8:], ha='center', va='center',
                fontsize=7)

        # Draw connection line
        ax.plot([switch_x, hx], [switch_y, hy], 'k-', linewidth=1.5, alpha=0.6)

        # Port label
        mid_x = (switch_x + hx) / 2
        mid_y = (switch_y + hy) / 2
        ax.text(mid_x, mid_y, f"P{host.port_id}", fontsize=7,
                ha='center', va='center',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title('Star Topology Network', fontsize=14, fontweight='bold')

    plt.tight_layout()
    plt.savefig('demo_level2_topology.png', dpi=150, bbox_inches='tight')
    plt.close()


def main():
    """Run all Level 2 demonstrations."""
    print("\n" + "=" * 70)
    print(" LEVEL 2: MULTI-HOST COMMUNICATION DEMONSTRATION")
    print(" Total: 30 points")
    print("=" * 70 + "\n")

    demo_star_topology()
    demo_mac_addressing()
    demo_mac_learning()
    demo_multihost_communication()
    demo_broadcast()
    demo_routing_verification()
    demo_statistics()

    print("\n" + "=" * 70)
    print(" LEVEL 2 DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\nGenerated files:")
    print("  - demo_level2_topology.png")
    print()


if __name__ == "__main__":
    main()
