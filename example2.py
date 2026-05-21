# Python Example 2 — Real-time graph + CSV
# Install first: pip install pyserial matplotlib

import serial
import csv
import time
import matplotlib.pyplot as plt
from collections import deque

SERIAL_PORT = "/dev/cu.wchusbserial14140"  # Windows: "COM3"
BAUD_RATE = 9600
CSV_FILE = "sensor_data.csv"

MAX_POINTS = 100

times = deque(maxlen=MAX_POINTS)
values = deque(maxlen=MAX_POINTS)

arduino = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
time.sleep(2)

csv_file = open(CSV_FILE, "w", newline="")
writer = csv.writer(csv_file)
writer.writerow(["time_ms", "sensor_value", "state"])

plt.ion()
fig, ax = plt.subplots()
line, = ax.plot([], [])
ax.set_title("Real-Time Sensor Data")
ax.set_xlabel("Time (s)")
ax.set_ylabel("Sensor Value")
ax.set_ylim(0, 1023)

print("Reading Arduino data... Press Ctrl+C to stop.")

try:
    while True:
        raw_line = arduino.readline().decode("utf-8", errors="ignore").strip()

        if not raw_line or raw_line.startswith("time_ms"):
            continue

        parts = raw_line.split(",")

        if len(parts) == 3:
            time_ms = int(parts[0])
            sensor_value = int(parts[1])
            state = parts[2]

            writer.writerow([time_ms, sensor_value, state])
            csv_file.flush()

            times.append(time_ms / 1000)
            values.append(sensor_value)

            line.set_xdata(times)
            line.set_ydata(values)

            ax.set_xlim(max(0, times[0]), max(5, times[-1]))
            fig.canvas.draw()
            fig.canvas.flush_events()

            print(time_ms, sensor_value, state)

except KeyboardInterrupt:
    print("Recording stopped.")

finally:
    csv_file.close()
    arduino.close()