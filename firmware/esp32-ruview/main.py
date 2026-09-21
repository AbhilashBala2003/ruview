# RuView ESP32 WiFi Sensing Bridge v4
# MicroPython 1.24 on original ESP32
# Uses MANUAL byte packing (no struct format bugs)
import network, socket, time, math, gc

SSID = "No Internet"
PASS = "abhi2003"
IP   = "192.168.0.101"
PORT = 5005

def le4(v):
    v = int(v) & 0xFFFFFFFF
    return bytes([v&0xFF,(v>>8)&0xFF,(v>>16)&0xFF,(v>>24)&0xFF])

def le2(v):
    v = int(v) & 0xFFFF
    return bytes([v&0xFF,(v>>8)&0xFF])

def f2b(f):
    """float to 4-byte little-endian IEEE 754"""
    import struct
    return struct.pack("<f", f)

def wifi_connect():
    w = network.WLAN(network.STA_IF)
    w.active(False)
    time.sleep_ms(500)
    w.active(True)
    time.sleep_ms(500)
    if w.isconnected():
        print("IP:", w.ifconfig()[0])
        return w
    w.connect(SSID, PASS)
    for _ in range(40):
        if w.isconnected():
            break
        time.sleep_ms(500)
    if w.isconnected():
        print("WiFi OK  IP:", w.ifconfig()[0])
    else:
        print("WiFi FAIL")
    return w

def make_csi(seq, rssi):
    """Build valid ADR-018 CSI frame — 20 byte header + 56*2 IQ bytes"""
    pkt = bytearray(20 + 56*2)
    # magic 0xC5110001
    pkt[0]=0x01; pkt[1]=0x00; pkt[2]=0x11; pkt[3]=0xC5
    pkt[4] = 1   # node_id
    pkt[5] = 1   # n_antennas
    pkt[6] = 56; pkt[7] = 0   # n_subcarriers LE u16
    # freq 2412 MHz LE u32
    pkt[8]=0x6C; pkt[9]=0x09; pkt[10]=0x00; pkt[11]=0x00
    # seq LE u32
    s = seq & 0xFFFFFFFF
    pkt[12]=s&0xFF; pkt[13]=(s>>8)&0xFF; pkt[14]=(s>>16)&0xFF; pkt[15]=(s>>24)&0xFF
    # rssi i8, noise i8, pad u16
    pkt[16] = rssi & 0xFF
    pkt[17] = 176  # -80 as unsigned = 0xB0
    pkt[18] = 0; pkt[19] = 0
    # I/Q pairs — amplitude from RSSI
    amp = max(5, min(120, int((rssi + 100) * 1.2)))
    for i in range(56):
        angle = math.pi * 2 * i / 56 + seq * 0.03
        pkt[20 + i*2]   = int(amp * math.cos(angle)) & 0xFF
        pkt[21 + i*2]   = int(amp * math.sin(angle)) & 0xFF
    return bytes(pkt)

def make_vitals(rssi, br, hr, pres, np):
    """Build 32-byte vitals packet"""
    pkt = bytearray(32)
    # magic 0xC5110002
    pkt[0]=0x02; pkt[1]=0x00; pkt[2]=0x11; pkt[3]=0xC5
    pkt[4] = 1           # node_id
    pkt[5] = 1 if pres else 0  # flags
    # breathing_rate * 100, u16 LE
    br_fp = int(br * 100) & 0xFFFF
    pkt[6] = br_fp & 0xFF; pkt[7] = (br_fp >> 8) & 0xFF
    # heart_rate * 10000, u32 LE
    hr_fp = int(hr * 10000) & 0xFFFFFFFF
    pkt[8]=hr_fp&0xFF; pkt[9]=(hr_fp>>8)&0xFF; pkt[10]=(hr_fp>>16)&0xFF; pkt[11]=(hr_fp>>24)&0xFF
    pkt[12] = rssi & 0xFF  # rssi
    pkt[13] = np           # n_persons
    # motion_energy f32 LE (bytes 16-19)
    mo = min(1.0, abs(rssi + 60) / 40.0)
    mb = f2b(mo)
    pkt[16]=mb[0]; pkt[17]=mb[1]; pkt[18]=mb[2]; pkt[19]=mb[3]
    # presence_score f32 LE (bytes 20-23)
    pb = f2b(1.0 if pres else 0.0)
    pkt[20]=pb[0]; pkt[21]=pb[1]; pkt[22]=pb[2]; pkt[23]=pb[3]
    # timestamp (bytes 24-27)
    ts = time.ticks_ms() & 0xFFFFFFFF
    pkt[24]=ts&0xFF; pkt[25]=(ts>>8)&0xFF; pkt[26]=(ts>>16)&0xFF; pkt[27]=(ts>>24)&0xFF
    return bytes(pkt)

# ── Main ──────────────────────────────────────────────────────────────────
print("RuView ESP32 Bridge v4")
w = wifi_connect()

try:
    sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
except Exception as e:
    print("Socket error:", e)
    raise

addr  = (IP, PORT)
seq   = 0
tick  = 0
rssi_buf = [-70] * 20
cur_rssi  = -70
t_scan   = time.ticks_ms()
t_vitals = time.ticks_ms()

print("Streaming ->", IP, ":", PORT)
print("Each line = 1 vitals packet sent (every second)")

while True:
    now = time.ticks_ms()

    # WiFi scan every 400 ms
    if time.ticks_diff(now, t_scan) >= 400:
        try:
            nets = w.scan()
            if nets:
                cur_rssi = max(n[3] for n in nets)
        except:
            pass
        rssi_buf[tick % 20] = cur_rssi
        t_scan = now
        if not w.isconnected():
            print("Reconnecting WiFi...")
            w = wifi_connect()

    # Compute motion signal from RSSI variance
    mean_r = sum(rssi_buf) / 20
    var_r  = sum((r - mean_r) ** 2 for r in rssi_buf) / 20

    # Send CSI frame at 20 Hz
    try:
        frame = make_csi(seq, cur_rssi)
        sk.sendto(frame, addr)
    except Exception as e:
        print("CSI send error:", e)

    # Send vitals every second
    if time.ticks_diff(now, t_vitals) >= 1000:
        pres     = var_r > 3.0
        n_pers   = 1 if pres else 0
        br       = 12.0 + var_r * 0.3
        hr       = 60.0 + var_r * 0.8
        try:
            vit = make_vitals(cur_rssi, br, hr, pres, n_pers)
            sk.sendto(vit, addr)
        except Exception as e:
            print("Vitals send error:", e)
        t_vitals = now
        print("rssi=%d var=%.1f pres=%d seq=%d" % (cur_rssi, var_r, n_pers, seq))

    seq  += 1
    tick += 1
    gc.collect()
    time.sleep_ms(50)
