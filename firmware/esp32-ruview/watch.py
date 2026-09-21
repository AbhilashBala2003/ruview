import serial, time, sys
ser = serial.Serial("COM11", 115200, timeout=1)
print("=== ESP32 Serial Monitor ===\n")
deadline = time.time() + 35
while time.time() < deadline:
    d = ser.read(ser.in_waiting or 1)
    if d:
        print(d.decode('utf-8', errors='replace'), end='', flush=True)
    time.sleep(0.02)
ser.close()
