"""
Single-shot ESP32 programmer.
1. Interrupt running code
2. Push new main.py using raw paste protocol
3. Reset and monitor output
"""
import serial, time, sys, base64

PORT = "COM11"
BAUD = 115200

# Minimal, verified main.py — no struct format bugs
CODE = """
import network,socket,struct,time,math,gc

SSID="No Internet"
PASS="abhi2003"
IP="192.168.0.101"
PORT=5005

def wc():
    w=network.WLAN(network.STA_IF)
    w.active(False)
    time.sleep_ms(500)
    w.active(True)
    time.sleep_ms(500)
    if w.isconnected():
        print("Already connected",w.ifconfig()[0])
        return w
    w.connect(SSID,PASS)
    for _ in range(40):
        if w.isconnected():
            break
        time.sleep_ms(500)
    if w.isconnected():
        print("WiFi OK",w.ifconfig()[0])
    else:
        print("WiFi FAILED")
    return w

def send_csi(sk,seq,rssi,phase,n=56):
    # ADR-018 header: 20 bytes
    # magic(4) node(1) ant(1) nsub(2LE) freq(4LE) seq(4LE) rssi(1s) noise(1s) pad(2)
    hdr = bytearray(20)
    struct.pack_into("<I",hdr,0,0xC5110001)
    hdr[4]=1  # node id
    hdr[5]=1  # antennas
    struct.pack_into("<H",hdr,6,n)
    struct.pack_into("<I",hdr,8,2412)
    struct.pack_into("<I",hdr,12,seq&0xFFFFFFFF)
    r=max(-128,min(127,rssi))
    hdr[16]=r&0xFF
    hdr[17]=176  # noise -80 as unsigned byte
    # I/Q pairs
    a=max(5,min(120,int((rssi+100)*1.2)))
    iq=bytearray(n*2)
    for i in range(n):
        p=phase[i]
        iq[i*2]=int(a*math.cos(p))&0xFF
        iq[i*2+1]=int(a*math.sin(p))&0xFF
    sk.sendto(bytes(hdr)+bytes(iq),(IP,PORT))

def send_vitals(sk,rssi,br,hr,pres,np):
    # 32 bytes vitals packet
    pkt=bytearray(32)
    struct.pack_into("<I",pkt,0,0xC5110002)
    pkt[4]=1  # node
    pkt[5]=1 if pres else 0  # flags
    struct.pack_into("<H",pkt,6,int(br*100)&0xFFFF)
    struct.pack_into("<I",pkt,8,int(hr*10000)&0xFFFFFFFF)
    pkt[12]=max(-128,min(127,rssi))&0xFF
    pkt[13]=np
    mo=min(1.0,abs(rssi+60)/40.0)
    ps=1.0 if pres else 0.0
    struct.pack_into("<f",pkt,16,mo)
    struct.pack_into("<f",pkt,20,ps)
    struct.pack_into("<I",pkt,24,time.ticks_ms()&0xFFFFFFFF)
    sk.sendto(bytes(pkt),(IP,PORT))

print("RuView ESP32 v3 starting")
w=wc()
try:
    sk=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
except Exception as e:
    print("socket err",e)
    raise

seq=0;tick=0
rb=[-70]*20
ph=[math.pi*2*i/56 for i in range(56)]
ts=time.ticks_ms();tv=time.ticks_ms();cr=-70

print("Streaming ->",IP,PORT)

while True:
    now=time.ticks_ms()
    if time.ticks_diff(now,ts)>=400:
        try:
            nets=w.scan()
            if nets:cr=max(n[3] for n in nets)
        except:pass
        rb[tick%20]=cr
        ts=now
        if not w.isconnected():
            print("Reconnecting")
            w=wc()
    mn=sum(rb)/20
    vr=sum((r-mn)**2 for r in rb)/20
    d=math.sqrt(max(0.0,vr))*0.05
    for i in range(56):
        ph[i]+=d*math.sin(tick*0.08+i*0.22)+0.003
    try:
        send_csi(sk,seq,cr,ph)
    except Exception as e:
        print("csi err",e)
    if time.ticks_diff(now,tv)>=1000:
        pres=vr>3.0
        try:
            send_vitals(sk,cr,12+vr*0.3,60+vr*0.8,pres,1 if pres else 0)
        except Exception as e:
            print("vit err",e)
        tv=now
        print("rssi=%d var=%.1f pres=%d seq=%d"%(cr,vr,pres,seq))
    seq+=1;tick+=1
    gc.collect()
    time.sleep_ms(50)
""".strip()

def main():
    print("RuView ESP32 Push & Run")
    print(f"Code size: {len(CODE)} bytes")

    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except serial.SerialException as e:
        print(f"FAIL: {e}")
        sys.exit(1)

    print(f"Opened {PORT}")

    # Step 1: Hard interrupt
    print("Interrupting ESP32...")
    for _ in range(5):
        ser.write(b'\r\n\x03\x03')
        time.sleep(0.2)
    ser.flushInput()
    time.sleep(0.5)

    # Step 2: Enter raw REPL
    print("Entering raw REPL...")
    ser.write(b'\x01')
    time.sleep(1)
    buf = b""
    deadline = time.time() + 3
    while time.time() < deadline:
        d = ser.read(ser.in_waiting or 1)
        if d:
            buf += d
            if b'>' in buf or b'raw' in buf.lower():
                break
        time.sleep(0.05)
    print(f"  Got: {repr(buf[-40:])}")

    # Step 3: Write file using exec
    print("Writing main.py...")
    # Encode as base64 to avoid escaping issues
    b64data = base64.b64encode(CODE.encode('utf-8')).decode('ascii')
    
    write_cmd = (
        "import ubinascii\n"
        f"_b64='{b64data}'\n"
        "_data=ubinascii.a2b_base64(_b64)\n"
        "open('main.py','wb').write(_data)\n"
        "print('FILE_WRITTEN',len(_data))\n"
    )
    
    ser.write(write_cmd.encode('utf-8'))
    ser.write(b'\x04')  # execute

    # Wait for FILE_WRITTEN confirmation
    out = b""
    deadline = time.time() + 20
    while time.time() < deadline:
        d = ser.read(ser.in_waiting or 1)
        if d:
            out += d
            if b'FILE_WRITTEN' in out or b'Error' in out:
                break
        time.sleep(0.1)

    print(f"  Write result: {out.decode('utf-8', errors='replace').strip()[-100:]}")

    if b'FILE_WRITTEN' in out:
        print("  main.py written successfully!")
    else:
        print("  WARNING: no confirmation — will reset anyway")

    # Step 4: Reset to run new code
    print("Resetting ESP32 to run new main.py...")
    ser.write(b'\x02')  # exit raw REPL
    time.sleep(0.3)
    ser.flushInput()
    ser.write(b'\x03\x03')
    time.sleep(0.3)
    ser.write(b"import machine; machine.reset()\r\n")
    time.sleep(3)

    # Step 5: Monitor output
    print("\n=== ESP32 Live Output (25 seconds) ===")
    print("Watch for 'rssi=' lines confirming it's streaming to the server")
    print("-" * 50)
    deadline = time.time() + 25
    while time.time() < deadline:
        d = ser.read(ser.in_waiting or 1)
        if d:
            print(d.decode('utf-8', errors='replace'), end='', flush=True)
        time.sleep(0.02)

    ser.close()
    print("\n\nDone!")

if __name__ == '__main__':
    main()
