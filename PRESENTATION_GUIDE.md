# 展示流程指南 (Presentation Guide)

**展示时间**: 5分钟
**重点**: 展示你做了什么，以及演示你做了什么

---

## 准备工作

```bash
# 进入项目目录
cd /home/ouyangzl/network-communication-project

# 确保环境可用
python3 --version
```

---

## Level 1: 点对点通信 (30分)

### 任务 1.1: 比特流传输过程 (录屏)

**运行命令**:
```bash
python3 -c "
from physical_layer import *
from cable import Cable

print('=== 比特流传输演示 ===')
print()

# 1. 字符串转比特流
message = 'Hello'
bits = string_to_bits(message)
print(f'原始消息: \"{message}\"')
print(f'比特流: {bits}')
print(f'比特数: {len(bits)} bits (每字符8位)')
print()

# 2. 调制 (比特→模拟信号)
signal = modulate_ook(bits)
print(f'OOK调制后: {len(signal)} 个采样点 (每bit 100个采样)')
print(f'信号范围: [{signal.min():.1f}, {signal.max():.1f}]')
print()

# 3. 通过Cable传输
cable = Cable(length=100, attenuation=0.1, noise_level=0.01)
received_signal = cable.transmit(signal)
print(f'通过Cable传输 (噪声={cable.noise_level})')
print(f'接收信号范围: [{received_signal.min():.2f}, {received_signal.max():.2f}]')
print()

# 4. 解调 (模拟信号→比特)
received_bits = demodulate_ook(received_signal)
print(f'解调后比特: {received_bits}')
print()

# 5. 比特转字符串
received_message = bits_to_string(received_bits)
print(f'恢复消息: \"{received_message}\"')
print(f'传输成功: {message == received_message}')
"
```

**讲解要点**:
1. `string_to_bits()` - 将ASCII字符转为8位二进制
2. `modulate_ook()` - OOK调制，1=高电平，0=低电平
3. `cable.transmit()` - 模拟物理信道传输（衰减+噪声）
4. `demodulate_ook()` - 自适应阈值解调
5. `bits_to_string()` - 恢复原始数据

---

### 任务 1.2: 消息分片传输 (录屏)

**运行命令**:
```bash
python3 -c "
from data_link_layer import *
from physical_layer import PhysicalLink
from cable import Cable

print('=== 消息分片传输演示 ===')
print()

# 创建长消息
long_message = b'A' * 200 + b'B' * 100
print(f'原始消息长度: {len(long_message)} 字节')
print()

# 分片
slicer = PacketSlicer(max_payload_size=64)
slices = slicer.slice(long_message)
print(f'分片数量: {len(slices)}')
for i, s in enumerate(slices):
    print(f'  分片 {i}: {len(s)} 字节')
print()

# 通过物理层传输每个分片
cable = Cable(length=100, attenuation=0.1, noise_level=0)
link = PhysicalLink(cable)
dll = DataLinkLayer(link, max_payload_size=64)

print('传输分片...')
received_data, success = dll.transmit_and_receive(long_message)
print(f'接收长度: {len(received_data)} 字节')
print(f'传输成功: {success}')
print(f'数据匹配: {long_message == received_data}')
print()

# 显示帧格式
print('帧格式:')
print('┌──────────┬────────┬──────────┬──────────┬──────────┐')
print('│ Preamble │ Length │ Payload  │ Checksum │ Postamble│')
print('│  8 bits  │ 16 bits│ variable │  8 bits  │  8 bits  │')
print('└──────────┴────────┴──────────┴──────────┴──────────┘')
"
```

**讲解要点**:
1. `PacketSlicer` - 将大消息分成多个小帧
2. 每帧包含序列号用于重组
3. 帧格式：前导码+长度+载荷+校验和+后缀

---

### 任务 1.3: 噪声环境测试 (录屏)

**重要说明**: 系统使用每bit 100个采样点平均，有效降低噪声10倍。需要较高噪声(>1.0)才能看到误码。

**运行命令**:
```bash
python3 -c "
from physical_layer import *
from cable import Cable

print('=== 不同噪声水平测试 ===')
print()
print('注意: 每bit使用100采样点平均，有效噪声=实际噪声/10')
print()

message = 'Hello World'
bits = string_to_bits(message)

print(f'测试消息: \"{message}\"')
print(f'噪声σ   有效σ   接收结果          误码率')
print('-' * 55)

# 使用更高噪声范围来展示效果
for noise in [0.5, 1.0, 1.2, 1.5, 1.8, 2.0]:
    cable = Cable(length=100, attenuation=0.1, noise_level=noise)
    link = PhysicalLink(cable)

    # 多次测试取平均
    errors = 0
    trials = 10
    for _ in range(trials):
        rx_bits = link.transmit_bits(bits.copy())
        errors += sum(1 for t, r in zip(bits, rx_bits) if t != r)

    ber = errors / (len(bits) * trials)
    result = link.transmit_data(message)
    status = 'OK' if result == message else 'ERROR'
    effective = noise / 10

    print(f'{noise:.1f}     {effective:.2f}    {result[:15]:<17} {ber:.2%} [{status}]')
"
```

---

### 任务 1.4: Shannon公式比较 (录屏)

**运行命令**:
```bash
python3 -c "
import numpy as np
from physical_layer import *
from cable import Cable

print('=== Shannon容量对比 ===')
print()
print('Shannon公式: C = B × log2(1 + SNR)')
print()
print('噪声水平 | SNR (dB) | Shannon容量 | 实际容量 | 效率')
print('-' * 60)

for noise in [0.01, 0.05, 0.1, 0.15, 0.2]:
    cable = Cable(length=100, attenuation=0.1, noise_level=noise)
    link = PhysicalLink(cable)

    # 测试传输
    bits = string_to_bits('Test message for capacity analysis')
    rx_bits = link.transmit_bits(bits)

    # 获取SNR
    snr_db = link.get_snr()

    # Shannon容量
    shannon = calculate_shannon_capacity(snr_db)

    # 实际成功率 (简化为1-BER)
    ber = sum(1 for t, r in zip(bits, rx_bits) if t != r) / len(bits)
    actual = 1.0 - ber

    efficiency = (actual / shannon * 100) if shannon > 0 else 0

    print(f'  {noise:.2f}    | {snr_db:7.1f}  | {shannon:11.2f} | {actual:10.2f} | {efficiency:5.1f}%')
"
```

---

## Level 2: 多主机通信 (30分)

### 任务 2.1: 多主机通信过程 (录屏)

**运行命令**:
```bash
python3 -c "
from network_layer import *

print('=== 多主机通信演示 ===')
print()

# 创建星型拓扑
print('1. 创建星型拓扑网络')
topology = StarTopology(num_hosts=4)
print(f'   交换机: {topology.switch.name}')
print(f'   主机数: {len(topology.hosts)}')
print()

# 显示主机信息
print('2. 网络中的主机:')
for mac, host in topology.hosts.items():
    print(f'   {host.name}: MAC={mac}, Port={host.port_id}')
print()

# 主机通信
print('3. Host1 发送消息给 Host2')
host1 = topology.get_host('00:00:00:00:00:01')
host2 = topology.get_host('00:00:00:00:00:02')

host1.send_string('00:00:00:00:00:02', 'Hello from Host1!')
print('   发送: \"Hello from Host1!\"')
print('   源MAC: 00:00:00:00:00:01')
print('   目标MAC: 00:00:00:00:00:02')
print()

# 检查接收
frame = host2.get_received()
if frame:
    print(f'4. Host2 接收到:')
    print(f'   内容: \"{frame.payload.decode()}\"')
    print(f'   来源: {frame.src_mac}')
print()

# 显示MAC学习
print('5. 交换机MAC表 (自动学习):')
topology.switch.print_mac_table()
"
```

---

### 任务 2.2: 寻址机制讲解

**运行命令**:
```bash
python3 -c "
from network_layer import *

print('=== 寻址机制讲解 ===')
print()

# MAC地址格式
print('1. MAC地址格式: XX:XX:XX:XX:XX:XX (48位)')
mac = MACAddress('00:11:22:33:44:55')
print(f'   示例: {mac}')
bits = mac.to_bits()
print(f'   比特表示: {bits[:16]}... (共48位)')
print()

# 网络帧格式
print('2. 网络帧格式 (带寻址):')
print('┌──────────┬────────┬────────┬────────┬──────────┬──────────┬──────────┐')
print('│ Preamble │Dst MAC │Src MAC │ Length │ Payload  │ Checksum │Postamble │')
print('│  8 bits  │ 48 bits│ 48 bits│ 16 bits│ variable │  8 bits  │  8 bits  │')
print('└──────────┴────────┴────────┴────────┴──────────┴──────────┴──────────┘')
print()

# 创建帧示例
frame = NetworkFrame(
    src_mac='00:00:00:00:00:01',
    dst_mac='00:00:00:00:00:02',
    payload=b'Test'
)
print('3. 示例帧:')
print(f'   源MAC: {frame.src_mac}')
print(f'   目标MAC: {frame.dst_mac}')
print(f'   载荷: {frame.payload}')
print(f'   校验和: {frame.checksum}')
bits = frame.to_bits()
print(f'   总长度: {len(bits)} bits')
"
```

---

### 任务 2.3: 路由与转发讲解

**运行命令**:
```bash
python3 -c "
from network_layer import *

print('=== 交换机路由与转发 ===')
print()

# 创建网络
topology = StarTopology(num_hosts=3)
host1 = topology.get_host('00:00:00:00:00:01')
host2 = topology.get_host('00:00:00:00:00:02')
host3 = topology.get_host('00:00:00:00:00:03')

print('1. 初始状态 - MAC表为空')
print(f'   MAC表: {topology.switch.mac_table}')
print()

# 第一次通信 - 触发广播和学习
print('2. Host1 发送给 Host2 (首次)')
host1.send_string('00:00:00:00:00:02', 'First message')
print('   -> 交换机学习 Host1 的 MAC (来源端口)')
print('   -> Host2 未知，广播到所有端口')
print(f'   MAC表: {topology.switch.mac_table}')
print()

# Host2 回复
print('3. Host2 回复 Host1')
host2.send_string('00:00:00:00:00:01', 'Reply')
print('   -> 交换机学习 Host2 的 MAC')
print('   -> Host1 已知，直接转发到端口 0')
print(f'   MAC表: {topology.switch.mac_table}')
print()

# 广播地址
print('4. 广播消息 (FF:FF:FF:FF:FF:FF)')
host1.send_string('FF:FF:FF:FF:FF:FF', 'Broadcast!')

# 检查所有主机
print('   Host2 收到:', host2.get_received() is not None)
print('   Host3 收到:', host3.get_received() is not None)
print()

print('5. 转发流程:')
print('   ┌─────────┐')
print('   │ 收到帧  │')
print('   └────┬────┘')
print('        ↓')
print('   ┌─────────────────┐')
print('   │ 学习源MAC→端口  │')
print('   └────────┬────────┘')
print('            ↓')
print('   ┌─────────────────┐')
print('   │ 查询目标MAC     │')
print('   └────────┬────────┘')
print('        ↓        ↓')
print('   [已知]     [未知/广播]')
print('      ↓            ↓')
print('  单播转发     广播所有端口')
"
```

---

## Level 3: 扩展功能 (现场演示)

### 任务 3.1: 传输层演示 (15分)

**运行命令**:
```bash
python3 -c "
from network_layer import StarTopology
from transport_layer import *

print('=== 传输层 - 可靠传输演示 ===')
print()

# 创建网络
topology = StarTopology(num_hosts=2)
host1 = topology.get_host('00:00:00:00:00:01')
host2 = topology.get_host('00:00:00:00:00:02')

# 创建传输层
transport1 = ReliableTransport(host1, timeout=0.5)
transport2 = ReliableTransport(host2, timeout=0.5)

received = []
transport2.on_receive = lambda data, src: received.append(data.decode())

print('Stop-and-Wait ARQ 协议:')
print('  1. 发送数据段 (带序列号)')
print('  2. 等待ACK')
print('  3. 超时则重传')
print()

# 显示段格式
print('传输段格式:')
print('┌──────────┬──────────┬────────┬────────┬──────────┐')
print('│ Seq Num  │ Ack Num  │ Flags  │ Length │ Payload  │')
print('│ 16 bits  │ 16 bits  │ 8 bits │ 16 bits│ variable │')
print('└──────────┴──────────┴────────┴────────┴──────────┘')
print()

# 发送消息
print('发送3条消息:')
for i in range(3):
    msg = f'Message {i+1}'
    success = transport1.send_string('00:00:00:00:00:02', msg)

    # 处理帧
    for _ in range(5):
        frame = host2.get_received()
        if frame: transport2._handle_receive(frame)
        frame = host1.get_received()
        if frame: transport1._handle_receive(frame)

    status = 'ACKed' if success else 'Failed'
    print(f'  [{status}] \"{msg}\" (seq={i})')

print()
print(f'统计: 发送={transport1.stats[\"segments_sent\"]}, ACK收到={transport1.stats[\"acks_received\"]}')
"
```

---

### 任务 3.2: 信道编码演示 (15分)

**运行命令**:
```bash
python3 -c "
from channel_coding import *
from cable import Cable

print('=== 信道编码 - 纠错演示 ===')
print()

# Hamming码演示
print('1. Hamming(7,4) 码:')
hamming = HammingCode()
data = [1, 0, 1, 1]
encoded = hamming.encode(data)
print(f'   原始数据: {data} (4位)')
print(f'   编码后:   {encoded} (7位)')
print()

# 引入错误并纠正
print('2. 单比特错误纠正:')
corrupted = encoded.copy()
corrupted[3] ^= 1  # 翻转第4位
print(f'   损坏数据: {corrupted} (位3翻转)')
decoded = hamming.decode(corrupted)
print(f'   纠正后:   {decoded[:4]}')
print(f'   纠正成功: {data == decoded[:4]}')
print()

# CRC演示
print('3. CRC-8 校验:')
crc = CRC()
test_data = b'Test data'
checksum = crc.compute(test_data)
print(f'   数据: {test_data}')
print(f'   CRC-8: {checksum} (0x{checksum:02X})')
print(f'   验证正确: {crc.verify(test_data, checksum)}')

# 损坏数据
corrupted_data = bytearray(test_data)
corrupted_data[0] ^= 1
print(f'   损坏后验证: {crc.verify(bytes(corrupted_data), checksum)} (检测到错误)')
print()

# 性能对比
print('4. 有无编码性能对比:')
print('   噪声    无编码    有编码')
for noise in [0.1, 0.15, 0.2]:
    cable_uncoded = Cable(noise_level=noise)
    cable_coded = Cable(noise_level=noise)

    coded_link = CodedPhysicalLink(cable_coded, use_hamming=True, use_crc=True)

    # 测试
    msg = 'Test'
    uncoded_ok = 0
    coded_ok = 0
    for _ in range(20):
        # 无编码
        from physical_layer import PhysicalLink
        link = PhysicalLink(Cable(noise_level=noise))
        if link.transmit_data(msg) == msg:
            uncoded_ok += 1
        # 有编码
        result, success = coded_link.transmit_string(msg)
        if success and result == msg:
            coded_ok += 1

    print(f'   {noise:.2f}    {uncoded_ok/20*100:5.0f}%     {coded_ok/20*100:5.0f}%')
"
```

---

### 任务 3.3: 应用层协议演示 (10分)

**运行命令**:
```bash
python3 -c "
from application_layer import *
from network_layer import StarTopology

print('=== 应用层 - HTTP协议演示 ===')
print()

# HTTP请求格式
print('1. HTTP请求格式:')
request = HTTPRequest(method='GET', path='/api/users', headers={'Accept': 'text/html'})
print(request.to_bytes().decode())
print()

# HTTP响应格式
print('2. HTTP响应格式:')
response = HTTPResponse.ok('Hello, World!')
print(response.to_bytes().decode())
print()

# 服务器/客户端演示
print('3. HTTP服务器演示:')
topology = StarTopology(num_hosts=2)
server_host = topology.get_host('00:00:00:00:00:01')
client_host = topology.get_host('00:00:00:00:00:02')

server = HTTPServer(server_host)

@server.route('/hello')
def hello(req):
    return HTTPResponse.ok('Hello from server!')

@server.route('/echo')
def echo(req):
    return HTTPResponse.ok(f'You said: {req.body}')

print('   注册路由: /hello, /echo')
print()

# 处理请求
print('4. 请求处理:')
req = HTTPRequest(method='GET', path='/hello')
resp = server._process_request(req)
print(f'   GET /hello -> {resp.status_code}: {resp.body}')

req = HTTPRequest(method='POST', path='/echo', body='Test message')
resp = server._process_request(req)
print(f'   POST /echo -> {resp.status_code}: {resp.body}')

req = HTTPRequest(method='GET', path='/notfound')
resp = server._process_request(req)
print(f'   GET /notfound -> {resp.status_code}')
"
```

---

### 任务 3.4: 调制方式对比演示 (10分)

**运行命令**:
```bash
python3 -c "
from modulation_schemes import *
import numpy as np

print('=== 调制方式对比演示 ===')
print()

# 测试各调制方式
bits = [1, 0, 1, 1, 0, 0, 1, 0]
print(f'测试比特: {bits}')
print()

schemes = [OOK(), ASK(), FSK(), BPSK()]

print('1. 无噪声测试:')
for scheme in schemes:
    signal = scheme.modulate(bits)
    recovered = scheme.demodulate(signal)
    match = recovered[:len(bits)] == bits
    print(f'   {scheme.name:6s}: 信号长度={len(signal):4d}, 匹配={match}')
print()

# 噪声下性能
print('2. 不同噪声下的误码率 (BER):')
print('   方案     0.05    0.10    0.15    0.20')
print('   ' + '-' * 45)

from cable import Cable
noise_levels = [0.05, 0.1, 0.15, 0.2]

for scheme in schemes:
    print(f'   {scheme.name:6s}', end='')
    for noise in noise_levels:
        cable = Cable(noise_level=noise)
        total_errors = 0
        total_bits = 0

        for _ in range(50):
            tx_bits = list(np.random.randint(0, 2, 50))
            signal = scheme.modulate(tx_bits)
            received = cable.transmit(signal)
            rx_bits = scheme.demodulate(received)

            min_len = min(len(tx_bits), len(rx_bits))
            total_errors += sum(1 for t, r in zip(tx_bits[:min_len], rx_bits[:min_len]) if t != r)
            total_bits += min_len

        ber = total_errors / total_bits
        print(f'  {ber:6.2%}', end='')
    print()
print()

print('3. 调制方式特点:')
print('   OOK  - 最简单，开关键控')
print('   ASK  - 幅度调制，易受噪声影响')
print('   FSK  - 频率调制，抗噪性好')
print('   BPSK - 相位调制，性能最佳')
"
```

---

### 任务 3.5: 并发处理演示 (10分)

**运行命令**:
```bash
python3 -c "
from concurrency import *
import time

print('=== 并发处理演示 ===')
print()

# 创建并发网络
print('1. 创建多线程网络:')
network = ConcurrentNetwork(num_hosts=4, num_workers=4)
print(f'   主机数: 4')
print(f'   工作线程: 4')
print()

# 启动
network.start()
time.sleep(0.2)

# 获取主机
hosts = [network.get_host(f'00:00:00:00:00:0{i+1}') for i in range(4)]

print('2. 并发发送消息 (所有主机同时发送):')
start = time.time()

# 同时发送
for i, host in enumerate(hosts):
    for j, dst in enumerate(hosts):
        if i != j:
            host.send_string(str(dst.mac), f'Hi from Host{i+1}')

time.sleep(0.5)
elapsed = time.time() - start

print(f'   发送完成，耗时: {elapsed:.3f}秒')
print()

# 收集统计
print('3. 接收统计:')
for host in hosts:
    count = 0
    while True:
        frame = host.receive_nowait()
        if frame:
            count += 1
        else:
            break
    print(f'   {host.name}: 收到 {count} 条消息')
print()

# 交换机统计
stats = network.switch.get_stats()
print('4. 交换机统计:')
print(f'   帧接收: {stats[\"frames_received\"]}')
print(f'   帧转发: {stats[\"frames_forwarded\"]}')
print(f'   广播: {stats[\"frames_broadcast\"]}')

network.stop()
print()
print('5. 多线程架构:')
print('   - 每个Host有独立的发送/接收线程')
print('   - Switch使用ThreadPoolExecutor处理')
print('   - 消息队列实现非阻塞通信')
"
```

---

## 综合演示命令

### 运行所有测试
```bash
python3 run_tests.py
```

### 运行完整演示
```bash
python3 demo_level1.py  # Level 1 完整演示
python3 demo_level2.py  # Level 2 完整演示
python3 demo_level3.py  # Level 3 完整演示
```

---

## 展示时间分配建议 (5分钟)

| 内容 | 时间 | 要点 |
|------|------|------|
| Level 1 | 1.5分钟 | 比特流传输 + 分片 + 噪声测试 |
| Level 2 | 1.5分钟 | 多主机通信 + MAC学习 + 转发机制 |
| Level 3 | 2分钟 | 选择2-3个扩展功能重点演示 |

---

## 生成的可视化文件

运行演示后会生成以下图片：
- `demo_level1_signals.png` - OOK调制波形
- `demo_level2_topology.png` - 星型拓扑图
- `modulation_comparison.png` - 调制方式对比图

可以在展示中使用这些图片辅助讲解。
