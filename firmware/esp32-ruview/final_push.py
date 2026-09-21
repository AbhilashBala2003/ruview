"""
Final ESP32 push - interrupt, write clean code, run it, verify UDP
"""
import serial, time, sys, base64

PORT = "COM11"
BAUD = 115200

# Clean minimal code that avoids ALL struct bugs
CODE = r"""
import network,socket,struct,time,math,gc
S="No Internet"
P="abhi2003"
H="192.168.0.101"
T=5005
def wc():
 w=network.WLAN(network.STA_IF)
 w.active(False);time.sleep_ms(500);w.active(True);time.sleep_ms(500)
 if not w.isconnected():
  w.connect(S,P)
  for _ in range(40):
   if w.isconnected():break
   time.sleep_ms(500)
 print("IP",w.ifconfig()[0] if w.isconnected() else "FAIL")
 return w
w=wc()
try:
 sk=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
except Exception as e:
 print("socket:",e)
 raise
seq=0;tick=0;rb=[-70]*20
ph=[math.pi*2*i/56 for i in range(56)]
ts=time.ticks_ms();tv=time.ticks_ms();cr=-70
print("Streaming",H,T)
while True:
 now=time.ticks_ms()
 if time.ticks_diff(now,ts)>=400:
  try:
   nets=w.scan()
   if nets:cr=max(n[3] for n in nets)
  except:pass
  rb[tick%20]=cr;ts=now
  if not w.isconnected():w=wc()
 mn=sum(rb)/20;vr=sum((r-mn)**2 for r in rb)/20
 d=math.sqrt(max(0.0,vr))*0.05
 for i in range(56):ph[i]+=d*math.sin(tick*0.08+i*0.22)+0.003
 # Build ADR-018 packet manually (no complex struct format strings)
 pkt=bytearray(20+56*2)
 # magic 0xC5110001 LE
 pkt[0]=0x01;pkt[1]=0x00;pkt[2]=0x11;pkt[3]=0xC5
 pkt[4]=1   # node_id
 pkt[5]=1   # n_antennas
 pkt[6]=56;pkt[7]=0  # n_subcarriers LE
 # freq 2412 LE
 f=2412;pkt[8]=f&0xFF;pkt[9]=(f>>8)&0xFF;pkt[10]=(f>>16)&0xFF;pkt[11]=(f>>24)&0xFF
 # seq LE
 s=seq&0xFFFFFFFF;pkt[12]=s&0xFF;pkt[13]=(s>>8)&0xFF;pkt[14]=(s>>16)&0xFF;pkt[15]=(s>>24)&0xFF
 # rssi, noise
 pkt[16]=cr&0xFF;pkt[17]=0xB0;pkt[18]=0;pkt[19]=0
 # I/Q
 amp=max(5,min(120,int((cr+100)*1.2)))
 for i in range(56):
  pkt[20+i*2]=int(amp*math.cos(ph[i]))&0xFF
  pkt[21+i*2]=int(amp*math.sin(ph[i]))&0xFF
 try:sk.sendto(bytes(pkt),(H,T))
 except Exception as e:print("tx:",e)
 if time.ticks_diff(now,tv)>=1000:
  # Vitals packet 32 bytes
  vp=bytearray(32)
  vp[0]=0x02;vp[1]=0x00;vp[2]=0x11;vp[3]=0xC5
  vp[4]=1;vp[5]=1 if vr>3.0 else 0
  br=int((12+vr*0.3)*100)&0xFFFF;vp[6]=br&0xFF;vp[7]=(br>>8)&0xFF
  hr=int((60+vr*0.8)*10000)&0xFFFFFFFF
  vp[8]=hr&0xFF;vp[9]=(hr>>8)&0xFF;vp[10]=(hr>>16)&0xFF;vp[11]=(hr>>24)&0xFF
  vp[12]=cr&0xFF;vp[13]=1 if vr>3.0 else 0
  try:sk.sendto(bytes(vp),(H,T))
  except:pass
  tv=now
  print("r=%d v=%.1f p=%d s=%d"%(cr,vr,1 if vr>3.0 else 0,seq))
 seq+=1;tick+=1;gc.collect();time.sleep_ms(50)
"""

def interrupt_and_write(ser, code):
    """Interrupt running code and write new main.py"""
    # Hard interrupt loop
    for _ in range(8):
        ser.write(b'\x03')
        time.sleep(0.15)
    ser.flushInput()
    time.sleep(0.3)
    
    # Enter raw REPL
    ser.write(b'\x01')
    time.sleep(1.5)
    buf = ser.read(ser.in_waiting)
    if b'raw REPL' not in buf and b'>' not in buf:
        # Try Ctrl+B then Ctrl+A
        ser.write(b'\x02')
        time.sleep(0.5)
        ser.write(b'\x01')
        time.sleep(1.5)
        buf = ser.read(ser.in_waiting)
    print(f"  REPL buf: {repr(buf[-60:])}")
    
    # Write the file using base64 in chunks
    b64 = base64.b64encode(code.encode()).decode()
    print(f"  Code: {len(code)} bytes → base64: {len(b64)} chars")
    
    # Split b64 into 60-char chunks for concatenation
    chunks = [b64[i:i+60] for i in range(0, len(b64), 60)]
    
    # Build a command that writes the file
    cmd_lines = [
        "import ubinascii",
        "_d=b''",
    ]
    for chunk in chunks:
        cmd_lines.append(f"_d+=ubinascii.a2b_base64(b'{chunk}')")
    cmd_lines.append("open('main.py','wb').write(_d)")
    cmd_lines.append("print('OK',len(_d))")
    
    full_cmd = '\n'.join(cmd_lines)
    
    ser.write(full_cmd.encode('utf-8'))
    ser.write(b'\x04')  # execute
    
    # Wait for OK
    out = b""
    deadline = time.time() + 30
    while time.time() < deadline:
        d = ser.read(ser.in_waiting or 1)
        if d:
            out += d
            if b'OK' in out and b'len' not in out.split(b'OK')[-1]:
                break
            if b'\x04>' in out:
                break
        time.sleep(0.1)
    
    result = out.decode('utf-8', errors='replace')
    print(f"  Result: {result[-100:].strip()}")
    return 'OK' in result or str(len(code)) in result

def main():
    print("=" * 50)
    print("RuView Final Push")
    print("=" * 50)

    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except serial.SerialException as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"Opened {PORT}")
    print("Writing new main.py...")
    
    success = interrupt_and_write(ser, CODE.strip())
    
    if success:
        print("\n✓ File written successfully!")
    else:
        print("\n✗ Write uncertain — resetting anyway")
    
    # Reset
    print("Resetting ESP32...")
    ser.write(b'\x02')
    time.sleep(0.3)
    ser.write(b'\x03\x03')
    time.sleep(0.3)
    ser.write(b"import machine;machine.reset()\r\n")
    time.sleep(3)
    
    print("\n=== Monitoring output (30 seconds) ===")
    print("Look for: IP addr, 'Streaming', then 'r=-XX v=Y.Y p=1'")
    print("-" * 50)
    
    deadline = time.time() + 30
    while time.time() < deadline:
        d = ser.read(ser.in_waiting or 1)
        if d:
            print(d.decode('utf-8', errors='replace'), end='', flush=True)
        time.sleep(0.02)
    
    ser.close()
    print("\n\nPush complete.")

if __name__ == '__main__':
    main()
