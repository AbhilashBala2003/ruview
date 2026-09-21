"""
Fast ESP32 MicroPython uploader using ampy-style raw file write.
Interrupts running code, writes files in binary chunks, then reboots.
"""
import serial, time, sys, textwrap

PORT  = "COM11"
BAUD  = 115200

MAIN_PY = r"""
import network, socket, struct, time, math, gc

WIFI_SSID    = "No Internet"
WIFI_PASS    = "abhi2003"
TARGET_IP    = "192.168.0.101"
TARGET_PORT  = 5005
NODE_ID      = 1
N_SUB        = 56
FREQ_MHZ     = 2412
MAGIC_CSI    = 0xC5110001
MAGIC_VIT    = 0xC5110002

def wifi_connect():
    w = network.WLAN(network.STA_IF)
    w.active(False); time.sleep_ms(300)
    w.active(True);  time.sleep_ms(300)
    if w.isconnected():
        return w
    w.connect(WIFI_SSID, WIFI_PASS)
    for i in range(40):
        if w.isconnected(): break
        time.sleep_ms(500)
        print("." if i%10 else "\nwaiting", end="")
    print()
    if w.isconnected():
        print("IP:", w.ifconfig()[0])
    else:
        print("WiFi failed")
    return w

def csi_frame(seq, rssi, ph):
    h = struct.pack("<IBBHII", MAGIC_CSI, NODE_ID, 1, N_SUB, FREQ_MHZ, seq)
    h += struct.pack("<bbH", max(-128,min(127,rssi)), -80, 0)
    amp = max(5, min(120, int((rssi+100)*1.2)))
    iq  = bytearray(N_SUB*2)
    for i in range(N_SUB):
        iq[i*2]   = int(amp*math.cos(ph[i])) & 0xFF
        iq[i*2+1] = int(amp*math.sin(ph[i])) & 0xFF
    return h+bytes(iq)

def vitals(rssi, br, hr, pres, np):
    fl = 1 if pres else 0
    mo = min(1.0, abs(rssi+60)/40.0)
    ps = 1.0 if pres else 0.0
    return struct.pack("<IbbHIbbHffII",
        MAGIC_VIT, NODE_ID, fl,
        int(br*100)&0xFFFF, int(hr*10000)&0xFFFFFFFF,
        max(-128,min(127,rssi)), np, 0,
        mo, ps, time.ticks_ms()&0xFFFFFFFF, 0)

print("RuView ESP32 Bridge v2")
w   = wifi_connect()
try:
    sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
except Exception as e:
    print("socket:", e); raise

addr  = (TARGET_IP, TARGET_PORT)
seq   = 0
tick  = 0
rbuf  = [-70]*20
ph    = [math.pi*2*i/N_SUB for i in range(N_SUB)]
t_sc  = time.ticks_ms()
t_vt  = time.ticks_ms()
cur_r = -70

print("Streaming ->", TARGET_IP, TARGET_PORT)

while True:
    now = time.ticks_ms()
    if time.ticks_diff(now, t_sc) >= 400:
        try:
            nets = w.scan()
            if nets: cur_r = max(n[3] for n in nets)
        except: pass
        rbuf[tick%20] = cur_r
        t_sc = now
        if not w.isconnected():
            print("reconnecting"); w = wifi_connect()
    mn = sum(rbuf)/20
    vr = sum((r-mn)**2 for r in rbuf)/20
    d  = math.sqrt(max(0.0,vr))*0.05
    for i in range(N_SUB):
        ph[i] += d*math.sin(tick*0.08+i*0.22)+0.003
    try: sk.sendto(csi_frame(seq, cur_r, ph), addr)
    except: pass
    if time.ticks_diff(now, t_vt) >= 1000:
        pres = vr > 3.0
        try: sk.sendto(vitals(cur_r, 12+vr*0.3, 60+vr*0.8, pres, 1 if pres else 0), addr)
        except: pass
        t_vt = now
        print("r=%d v=%.1f p=%d" % (cur_r, vr, pres))
    seq+=1; tick+=1
    gc.collect()
    time.sleep_ms(50)
""".strip()

def send_cmd(ser, cmd, timeout=3.0):
    ser.write(cmd.encode() + b'\r\n')
    time.sleep(0.1)
    out = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = ser.read(ser.in_waiting or 1)
        if d: out += d
        time.sleep(0.05)
    return out.decode('utf-8', errors='replace')

def raw_paste(ser, code):
    """Write a file using MicroPython raw paste mode."""
    ser.write(b'\x05')   # raw paste mode
    time.sleep(0.2)
    if b'R' not in ser.read(10):
        # Fall back to normal raw REPL
        ser.write(code.encode('utf-8'))
        ser.write(b'\x04')
    else:
        window = 256
        data = code.encode('utf-8')
        i = 0
        while i < len(data):
            chunk = data[i:i+window]
            ser.write(chunk)
            i += len(chunk)
            time.sleep(0.01)
        ser.write(b'\x04')
    time.sleep(0.5)
    # Read until we see the OK marker
    out = b""
    deadline = time.time() + 15
    while time.time() < deadline:
        d = ser.read(ser.in_waiting or 1)
        if d:
            out += d
            if b'OK' in out or b'>' in out:
                break
        time.sleep(0.05)
    return out

def enter_raw_repl(ser):
    """Interrupt + enter raw REPL."""
    for _ in range(3):
        ser.write(b'\x03')   # Ctrl+C
        time.sleep(0.3)
    ser.flushInput()
    ser.write(b'\x01')       # Ctrl+A = raw REPL
    time.sleep(0.5)
    buf = ser.read(ser.in_waiting)
    return b'raw REPL' in buf or b'>' in buf

def exec_raw(ser, code, timeout=8):
    """Execute code in raw REPL, return stdout."""
    ser.write(code.encode('utf-8'))
    ser.write(b'\x04')
    out = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        d = ser.read(ser.in_waiting or 1)
        if d:
            out += d
            if out.count(b'\x04') >= 2:
                break
        else:
            time.sleep(0.05)
    # Strip control chars
    if b'\x04' in out:
        parts = out.split(b'\x04')
        return parts[1].decode('utf-8', errors='replace') if len(parts) > 1 else ''
    return out.decode('utf-8', errors='replace')

def write_file(ser, name, content):
    """Write a file to the ESP32 filesystem in chunks."""
    lines = content.split('\n')
    # Open file
    exec_raw(ser, f"_f=open('{name}','w')")
    # Write line by line to avoid buffer issues
    for line in lines:
        safe = line.replace('\\', '\\\\').replace("'", "\\'")
        exec_raw(ser, f"_f.write('{safe}\\n')", timeout=3)
    exec_raw(ser, "_f.close()")
    # Verify
    size = exec_raw(ser, f"import os; print(os.stat('{name}')[6])")
    return size.strip()

def main():
    print("=" * 50)
    print("RuView ESP32 Flash & Run")
    print("=" * 50)

    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.5)
    except serial.SerialException as e:
        print(f"CANNOT open {PORT}: {e}")
        print("Unplug and replug the ESP32, then try again.")
        sys.exit(1)

    print(f"Opened {PORT}")
    print("Interrupting any running code...")
    
    for _ in range(5):
        ser.write(b'\x03')
        time.sleep(0.2)
    ser.flushInput()
    
    print("Entering raw REPL...")
    ok = enter_raw_repl(ser)
    print(f"Raw REPL: {'OK' if ok else 'uncertain, proceeding anyway'}")
    
    # Quick test
    r = exec_raw(ser, "print('REPL_OK')")
    if 'REPL_OK' in r:
        print("REPL confirmed working")
    else:
        print(f"REPL response: {repr(r[:80])}")

    print("\nWriting main.py to ESP32...")
    size = write_file(ser, "main.py", MAIN_PY)
    print(f"main.py written — device says size={size}")

    print("\nSoft-resetting ESP32 (will run main.py)...")
    ser.write(b'\x02')   # Ctrl+B = normal REPL
    time.sleep(0.3)
    exec_raw(ser, "import machine; machine.reset()")

    print("\n=== Watching serial output (15 seconds) ===")
    deadline = time.time() + 15
    while time.time() < deadline:
        d = ser.read(ser.in_waiting or 1)
        if d:
            try:
                print(d.decode('utf-8', errors='replace'), end='', flush=True)
            except:
                pass
        else:
            time.sleep(0.05)

    ser.close()
    print("\n\nDone. ESP32 should now be streaming UDP packets.")

if __name__ == "__main__":
    main()
