# Python Example 1 — Real-time numbers
# Install first: pip install pyserial

import serial
import time

SERIAL_PORT = "/dev/cu.wchusbserial14140"  # Windows example: "COM3"
BAUD_RATE = 9600

arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)

print("Reading Arduino data. Press Ctrl+C to stop.")

try:
    while True:
        line = arduino.readline().decode("utf-8", errors="ignore").strip()

        if line:
            print(line)

except KeyboardInterrupt:
    print("Stopped by user.")

finally:
    arduino.close()