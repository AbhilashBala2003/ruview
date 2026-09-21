# boot.py — runs before main.py on MicroPython
import gc
gc.enable()

# Increase WiFi TX power for better range
import network
sta = network.WLAN(network.STA_IF)
sta.active(True)

print("RuView ESP32 booting...")
