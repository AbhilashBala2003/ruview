"""
Upload main.py to ESP32 MicroPython via raw serial.
Handles interrupting a running script before uploading.
"""
import serial, time, sys, os

PORT   = "COM11"
BAUD   = 115200
FILES  = [
    ("boot.py", r"C:\Users\91949\Desktop\ruview\RuView\firmware\esp32-ruview\boot.py"),
    ("main.py", r"C:\Users\91949\Desktop\ruview\RuView\firmware\esp32-ruview\main.py"),
]

def wait_for(ser, expect, timeout=5.0):
    buf = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        c = ser.read(1)
        if c:
            buf += c
            if expect in buf:
                return True
    return False

def enter_raw_repl(ser):
    # Send Ctrl+C twice to interrupt running code
    ser.write(b'\x03')
    time.sleep(0.2)
    ser.write(b'\x03')
    time.sleep(0.3)
    ser.flushInput()
    # Enter raw REPL mode (Ctrl+A)
    ser.write(b'\x01')
    ok = wait_for(ser, b'raw REPL', timeout=4)
    if not ok:
        # Try soft reset then raw repl
        ser.write(b'\x04')
        time.sleep(1)
        ser.write(b'\x01')
        ok = wait_for(ser, b'raw REPL', timeout=4)
    return ok

def raw_exec(ser, code):
    ser.write(code.encode('utf-8'))
    ser.write(b'\x04')  # Ctrl+D = execute
    result = b""
    deadline = time.time() + 10
    while time.time() < deadline:
        c = ser.read(1)
        if c:
            result += c
            if result.endswith(b'\x04>'):
                break
    return result

def upload_file(ser, dest_name, src_path):
    with open(src_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Write file via MicroPython
    # Split into chunks to avoid REPL buffer overflow
    escaped = content.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '')
    chunk_size = 200
    chunks = [escaped[i:i+chunk_size] for i in range(0, len(escaped), chunk_size)]
    # Open file for writing
    raw_exec(ser, f"f=open('{dest_name}','w')")
    for chunk in chunks:
        raw_exec(ser, f"f.write('{chunk}')")
    raw_exec(ser, "f.close()")
    # Verify
    result = raw_exec(ser, f"import os; print(os.stat('{dest_name}')[6])")
    print(f"  {dest_name}: {len(content)} bytes written, device confirms: {result}")

def main():
    print("=== RuView ESP32 Uploader ===")
    print(f"Port: {PORT}")

    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        print("Serial connected")
    except serial.SerialException as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print("Interrupting running code...")
    ok = enter_raw_repl(ser)
    if not ok:
        print("WARNING: Could not confirm raw REPL — trying anyway")

    print("Raw REPL ready, uploading files...")
    for dest, src in FILES:
        print(f"Uploading {dest}...")
        try:
            upload_file(ser, dest, src)
        except Exception as e:
            print(f"  ERROR: {e}")

    # Soft reset to run new code
    print("Resetting ESP32 to run new code...")
    ser.write(b'\x04')
    time.sleep(0.5)
    # Exit raw REPL (Ctrl+B)
    ser.write(b'\x02')
    time.sleep(2)

    # Read boot output
    print("\n=== ESP32 Boot Output (10 seconds) ===")
    deadline = time.time() + 12
    while time.time() < deadline:
        line = ser.readline()
        if line:
            print(line.decode('utf-8', errors='replace').strip())

    ser.close()
    print("\nDone! ESP32 is running the new code.")

if __name__ == "__main__":
    main()
