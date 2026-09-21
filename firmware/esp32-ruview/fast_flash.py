"""
Fast ESP32 upload using base64 encoding in a single exec block.
Much faster than line-by-line writing.
"""
import serial, time, sys, base64, textwrap

PORT = "COM11"
BAUD = 115200

MAIN_CODE = b"""
import network,socket,struct,time,math,gc
SSID="No Internet"
PASS="abhi2003"
IP="192.168.0.101"
PORT=5005
N=56
MC=0xC5110001
MV=0xC5110002
def wc():
 w=network.WLAN(network.STA_IF)
 w.active(False);time.sleep_ms(300);w.active(True);time.sleep_ms(300)
 if not w.isconnected():
  w.connect(SSID,PASS)
  for i in range(40):
   if w.isconnected():break
   time.sleep_ms(500);print(".",end="")
 print("IP:",w.ifconfig()[0] if w.isconnected() else "FAIL")
 return w
def cf(seq,r,ph):
 h=struct.pack("<IBBHII",MC,1,1,N,2412,seq)
 h+=struct.pack("<bbH",max(-128,min(127,r)),-80,0)
 a=max(5,min(120,int((r+100)*1.2)))
 iq=bytearray(N*2)
 for i in range(N):
  iq[i*2]=int(a*math.cos(ph[i]))&0xFF
  iq[i*2+1]=int(a*math.sin(ph[i]))&0xFF
 return h+bytes(iq)
def vf(r,br,hr,p,np):
 return struct.pack("<IbbHIbbHffII",MV,1,1 if p else 0,int(br*100)&0xFFFF,int(hr*10000)&0xFFFFFFFF,max(-128,min(127,r)),np,0,min(1.0,abs(r+60)/40.0),1.0 if p else 0.0,time.ticks_ms()&0xFFFFFFFF,0)
print("RuView v2 starting")
w=wc()
sk=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
addr=(IP,PORT)
seq=0;tick=0;rb=[-70]*20;ph=[math.pi*2*i/N for i in range(N)]
ts=time.ticks_ms();tv=time.ticks_ms();cr=-70
print("Streaming ->",IP,PORT)
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
 for i in range(N):ph[i]+=d*math.sin(tick*0.08+i*0.22)+0.003
 try:sk.sendto(cf(seq,cr,ph),addr)
 except:pass
 if time.ticks_diff(now,tv)>=1000:
  p=vr>3.0
  try:sk.sendto(vf(cr,12+vr*0.3,60+vr*0.8,p,1 if p else 0),addr)
  except:pass
  tv=now;print("r=%d v=%.1f p=%d"%(cr,vr,p))
 seq+=1;tick+=1;gc.collect();time.sleep_ms(50)
""".strip()

def main():
    print("=" * 50)
    print("RuView Fast Flash")
    print("=" * 50)

    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except serial.SerialException as e:
        print(f"ERROR opening {PORT}: {e}")
        sys.exit(1)

    print(f"Opened {PORT} at {BAUD}")

    # Interrupt running code
    print("Sending Ctrl+C x3 to interrupt...")
    for _ in range(3):
        ser.write(b'\x03')
        time.sleep(0.3)
    ser.flushInput()
    time.sleep(0.5)

    # Enter raw REPL
    print("Entering raw REPL (Ctrl+A)...")
    ser.write(b'\x01')
    time.sleep(1)
    resp = ser.read(ser.in_waiting)
    print(f"Response: {repr(resp[:50])}")

    # Encode main code as base64
    b64 = base64.b64encode(MAIN_CODE).decode('ascii')
    
    # Write in one shot using base64 decode
    upload_code = f"""
import ubinascii,os
_d=ubinascii.a2b_base64("{b64}")
_f=open("main.py","wb")
_f.write(_d)
_f.close()
print("DONE:",os.stat("main.py")[6],"bytes")
""".strip()

    print(f"Uploading {len(MAIN_CODE)} bytes as base64 ({len(b64)} chars)...")
    
    ser.write(upload_code.encode('utf-8'))
    ser.write(b'\x04')  # Execute
    
    # Wait for execution
    out = b""
    deadline = time.time() + 15
    while time.time() < deadline:
        d = ser.read(ser.in_waiting or 1)
        if d:
            out += d
            if b'DONE:' in out or b'Error' in out or b'error' in out:
                break
        time.sleep(0.1)
    
    print(f"Upload result: {out.decode('utf-8', errors='replace')[:200]}")

    if b'DONE:' in out:
        print("\n✓ main.py written successfully!")
    else:
        print("\n✗ Upload may have failed. Trying soft reset anyway...")

    # Reset to run main.py
    print("Resetting ESP32...")
    ser.write(b'\x02')  # exit raw repl
    time.sleep(0.3)
    # Hard reset via machine module
    ser.write(b'\x03\x03')
    time.sleep(0.3)
    ser.write(b"import machine; machine.reset()\r\n")
    time.sleep(2)

    # Read output
    print("\n=== ESP32 Output (20 seconds) ===")
    deadline = time.time() + 20
    while time.time() < deadline:
        d = ser.read(ser.in_waiting or 1)
        if d:
            txt = d.decode('utf-8', errors='replace')
            print(txt, end='', flush=True)
        time.sleep(0.05)

    ser.close()
    print("\n\nFlash complete.")

if __name__ == "__main__":
    main()
