# Arduino Sensor Dashboard with Flet Charts
# Reads Arduino CSV-style serial data:
# time_ms,sensor_value,state
#
# Install:
# pip install flet flet-charts pyserial

import flet as ft
import flet_charts as fch
import serial
import serial.tools.list_ports
import asyncio
import csv
import time
from collections import deque
from datetime import datetime

# =========================
# CONFIG
# =========================

SERIAL_PORT = "/dev/cu.wchusbserial14140"  # Change this
BAUD_RATE = 9600

BUFFER_SIZE = 120
UPDATE_INTERVAL = 0.08
CSV_FILE = "arduino_sensor_data.csv"

sensor_buffer = deque([0] * BUFFER_SIZE, maxlen=BUFFER_SIZE)

app_state = {
    "connected": False,
    "running": False,
    "ser": None,
    "last_time_ms": 0,
    "last_value": 0,
    "last_state": "LOW",
    "csv_writer": None,
    "csv_file": None,
}


def list_serial_ports():
    ports = serial.tools.list_ports.comports()
    return [p.device for p in ports]


def parse_arduino_line(line):
    """
    Expected format:
    time_ms,sensor_value,state
    Example:
    1200,523,MEDIUM
    """
    line = line.strip()

    if not line or line.startswith("time_ms"):
        return None

    parts = line.split(",")

    if len(parts) != 3:
        return None

    try:
        time_ms = int(parts[0])
        sensor_value = int(parts[1])
        state = parts[2]
        return time_ms, sensor_value, state
    except ValueError:
        return None


def buffer_to_points(buffer_data):
    return [
        fch.LineChartDataPoint(x=float(i), y=float(v))
        for i, v in enumerate(buffer_data)
    ]


def get_auto_range(buffer_data):
    values = list(buffer_data)

    if not values:
        return 0, 1023

    min_v = min(values)
    max_v = max(values)

    # If values are almost flat, expand the visual range
    if max_v - min_v < 30:
        center = (max_v + min_v) / 2
        min_y = max(0, center - 30)
        max_y = min(1023, center + 30)
    else:
        pad = 20
        min_y = max(0, min_v - pad)
        max_y = min(1023, max_v + pad)

    return min_y, max_y


def main(page: ft.Page):
    page.title = "Arduino Sensor Dashboard"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.window_width = 1100
    page.window_height = 760
    page.scroll = ft.ScrollMode.AUTO

    # ---------- UI TEXTS ----------

    title = ft.Text(
        "Arduino Sensor Dashboard",
        size=30,
        weight=ft.FontWeight.BOLD,
    )

    subtitle = ft.Text(
        "Real-time sensor value, line graph, and CSV logging",
        size=14,
        color=ft.Colors.WHITE70,
    )

    value_text = ft.Text(
        "Sensor value: --",
        size=34,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.CYAN_300,
    )

    state_text = ft.Text(
        "State: --",
        size=24,
        color=ft.Colors.WHITE,
    )

    port_text = ft.Text(
        f"Port: {SERIAL_PORT}",
        size=13,
        color=ft.Colors.WHITE70,
    )

    csv_text = ft.Text(
        f"CSV: {CSV_FILE}",
        size=13,
        color=ft.Colors.WHITE70,
    )

    status_text = ft.Text(
        "Status: waiting",
        size=13,
        color=ft.Colors.AMBER_300,
    )

    range_text = ft.Text(
        "Graph range: --",
        size=13,
        color=ft.Colors.WHITE70,
    )

    # ---------- CHART ----------

    sensor_chart = fch.LineChart(
        min_x=0,
        max_x=BUFFER_SIZE - 1,
        min_y=0,
        max_y=1023,
        expand=True,
        horizontal_grid_lines=fch.ChartGridLines(
            interval=50,
            color=ft.Colors.with_opacity(0.10, ft.Colors.WHITE),
            width=1,
        ),
        vertical_grid_lines=fch.ChartGridLines(
            interval=20,
            color=ft.Colors.with_opacity(0.06, ft.Colors.WHITE),
            width=1,
        ),
        left_axis=fch.ChartAxis(
            label_size=42,
            title=ft.Text("Sensor value"),
        ),
        bottom_axis=fch.ChartAxis(
            label_size=28,
            title=ft.Text("Samples"),
        ),
        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
        data_series=[],
    )

    status_card = ft.Card(
        content=ft.Container(
            padding=20,
            content=ft.Column(
                spacing=8,
                controls=[
                    value_text,
                    state_text,
                    ft.Divider(),
                    port_text,
                    csv_text,
                    status_text,
                    range_text,
                ],
            ),
        )
    )

    graph_card = ft.Card(
        content=ft.Container(
            padding=16,
            height=360,
            content=ft.Column(
                expand=True,
                spacing=10,
                controls=[
                    ft.Text(
                        "Real-time line graph",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Container(
                        height=290,
                        content=sensor_chart,
                    ),
                ],
            ),
        )
    )

    page.add(
        title,
        subtitle,
        status_card,
        graph_card,
    )

    # ---------- SERIAL CONNECTION ----------

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.02)
        time.sleep(2)

        app_state["ser"] = ser
        app_state["connected"] = True
        app_state["running"] = True

        status_text.value = f"Status: connected to {SERIAL_PORT} @ {BAUD_RATE}"
        status_text.color = ft.Colors.GREEN_300

    except Exception as e:
        status_text.value = f"Status: could not connect — {e}"
        status_text.color = ft.Colors.RED_300
        page.update()
        return

    # ---------- CSV ----------

    csv_file = open(CSV_FILE, "w", newline="", encoding="utf-8")
    writer = csv.writer(csv_file)
    writer.writerow(["timestamp", "time_ms", "sensor_value", "state"])

    app_state["csv_file"] = csv_file
    app_state["csv_writer"] = writer

    # ---------- SERIAL READER THREAD ----------

    def serial_reader_loop():
        while app_state["running"]:
            try:
                raw_line = app_state["ser"].readline().decode(
                    "utf-8",
                    errors="ignore"
                ).strip()

                parsed = parse_arduino_line(raw_line)

                if parsed is None:
                    continue

                time_ms, sensor_value, state = parsed

                sensor_buffer.append(sensor_value)

                app_state["last_time_ms"] = time_ms
                app_state["last_value"] = sensor_value
                app_state["last_state"] = state

                timestamp = datetime.now().isoformat(timespec="milliseconds")
                app_state["csv_writer"].writerow(
                    [timestamp, time_ms, sensor_value, state]
                )
                app_state["csv_file"].flush()

            except Exception:
                pass

            time.sleep(0.001)

    # ---------- UI UPDATE LOOP ----------

    async def ui_update_loop():
        while app_state["running"]:
            sensor_value = app_state["last_value"]
            state = app_state["last_state"]

            value_text.value = f"Sensor value: {sensor_value}"
            state_text.value = f"State: {state}"

            min_y, max_y = get_auto_range(sensor_buffer)

            sensor_chart.min_y = min_y
            sensor_chart.max_y = max_y

            sensor_chart.data_series = [
                fch.LineChartData(
                    points=buffer_to_points(sensor_buffer),
                    stroke_width=3,
                    curved=True,
                    color=ft.Colors.CYAN_300,
                )
            ]

            range_text.value = f"Graph range: {min_y:.0f} - {max_y:.0f}"

            try:
                page.update()
            except Exception:
                app_state["running"] = False
                break

            await asyncio.sleep(UPDATE_INTERVAL)

    page.run_thread(serial_reader_loop)
    page.run_task(ui_update_loop)


if __name__ == "__main__":
    ft.run(main)