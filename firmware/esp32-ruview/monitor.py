"""Monitor ESP32 serial output and show connection status"""
import serial
import time
import sys

PORT = "COM11"
BAUD = 115200

print("=== RuView ESP32 Monitor ===")
print(f"Opening {PORT} at {BAUD} baud...")

try:
    ser = serial.Serial(PORT, BAUD, timeout=2)
    print(f"Connected to {PORT}")
    print("Watching for ESP32 output (Ctrl+C to stop)...")
    print("-" * 50)

    # Send Ctrl+D to soft-reset MicroPython REPL, triggering main.py
    ser.write(b'\x04')
    time.sleep(1)

    start = time.time()
    while True:
        line = ser.readline()
        if line:
            decoded = line.decode('utf-8', errors='replace').strip()
            if decoded:
                ts = f"[{time.time()-start:6.1f}s]"
                print(f"{ts} {decoded}")
                sys.stdout.flush()
except serial.SerialException as e:
    print(f"ERROR: {e}")
    print("Make sure no other program is using COM11")
except KeyboardInterrupt:
    print("\nMonitor stopped")
finally:
    try:
        ser.close()
    except:
        pass
