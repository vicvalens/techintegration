# Clinical Dark Sensor Dashboard with Flet
# Reads ESP32 Serial CSV data:
# time_ms,raw_value,percent,state,indicator
#
# Install:
# pip install flet flet-charts pyserial

import flet as ft
import flet_charts as fch
import serial
import serial.tools.list_ports
import asyncio
import csv
import os
import time
import random
from datetime import datetime
from collections import deque


# =========================
# CONFIG
# =========================

BUFFER_SIZE = 140
DEFAULT_BAUD = 9600
UPDATE_INTERVAL = 0.08
SERIAL_TIMEOUT = 0.05
CSV_FOLDER = "participants"
ESP32_ADC_MAX = 4095


# =========================
# COLORS
# =========================

BG = "#0B1120"
PANEL = "#111827"
PANEL_2 = "#172033"
BORDER = "#263244"
TEXT = "#E5E7EB"
MUTED = "#94A3B8"

CYAN = "#22D3EE"
BLUE = "#38BDF8"
GREEN = "#34D399"
AMBER = "#FBBF24"
RED = "#F87171"


# =========================
# STATE
# =========================

app_state = {
    "running": False,
    "connected": False,
    "simulate": False,
    "ser": None,

    "time_ms": 0,
    "raw": 0,
    "percent": 0,
    "state": "LOW",
    "indicator": "Pressure Load Index",

    "csv_writer": None,
    "csv_file": None,
    "csv_path": None,
    "recording": False,

    "last_event": "Waiting",
    "last_raw_line": "",
}

percent_buffer = deque([0] * BUFFER_SIZE, maxlen=BUFFER_SIZE)


# =========================
# HELPERS
# =========================

def list_serial_ports():
    try:
        return [p.device for p in serial.tools.list_ports.comports()]
    except Exception:
        return []


def parse_serial_line(line: str):
    """
    Accepted formats:
    1) time_ms,raw_value,percent,state,indicator
    2) time_ms,raw_value,percent,state
    3) time_ms,raw_value,state
    """

    line = line.strip()

    if not line:
        return None

    ignored_words = [
        "Wi-Fi",
        "WiFi",
        "ESP32",
        "Connecting",
        "connected",
        "Local server",
        "IP address",
        "Serial CSV",
        "Multiplatform",
        "rst:",
        "boot:",
    ]

    if any(word in line for word in ignored_words):
        return None

    if set(line) == {"."}:
        return None

    if line.startswith("time_ms"):
        return None

    parts = line.split(",")

    try:
        if len(parts) >= 5:
            time_ms = int(parts[0])
            raw = int(parts[1])
            percent = int(parts[2])
            state = parts[3].strip().upper()
            indicator = ",".join(parts[4:]).strip()

        elif len(parts) == 4:
            time_ms = int(parts[0])
            raw = int(parts[1])
            percent = int(parts[2])
            state = parts[3].strip().upper()
            indicator = "Pressure Load Index"

        elif len(parts) == 3:
            time_ms = int(parts[0])
            raw = int(parts[1])
            state = parts[2].strip().upper()
            percent = int((raw / ESP32_ADC_MAX) * 100)
            indicator = "Pressure Load Index"

        else:
            return None

        percent = max(0, min(100, percent))

        if state not in ["LOW", "MEDIUM", "HIGH"]:
            if percent < 35:
                state = "LOW"
            elif percent < 70:
                state = "MEDIUM"
            else:
                state = "HIGH"

        return time_ms, raw, percent, state, indicator

    except ValueError:
        return None


def buffer_to_points(buffer_data):
    """
    Convert a stable list or deque into chart points.
    This function always makes a copy to avoid mutation errors.
    """
    values = list(buffer_data)

    return [
        fch.LineChartDataPoint(x=float(i), y=float(v))
        for i, v in enumerate(values)
    ]


def get_auto_range(buffer_data):
    """
    Auto-scale the graph vertically.
    This function also works with a stable copy/list.
    """
    values = list(buffer_data)

    if not values:
        return 0, 100

    min_v = min(values)
    max_v = max(values)

    if max_v - min_v < 8:
        center = (max_v + min_v) / 2
        min_y = max(0, center - 4)
        max_y = min(100, center + 4)
    else:
        pad = (max_v - min_v) * 0.18
        min_y = max(0, min_v - pad)
        max_y = min(100, max_v + pad)

    return min_y, max_y


def get_status_color(state):
    state = str(state).upper()

    if state == "HIGH":
        return RED

    if state == "MEDIUM":
        return AMBER

    return GREEN


def get_status_label(state):
    state = str(state).upper()

    if state == "HIGH":
        return "CHECK USER / ALERT"

    if state == "MEDIUM":
        return "MONITOR"

    return "SAFE"


def get_interpretation(indicator, state, percent):
    indicator_l = str(indicator).lower()
    state = str(state).upper()

    if "pressure" in indicator_l:
        if state == "HIGH":
            return "High pressure load detected. The user may be applying excessive support or force."
        if state == "MEDIUM":
            return "Moderate pressure load detected. Continue monitoring during the activity."
        return "Low pressure load detected. The user is applying minimal force."

    if "flexion" in indicator_l:
        if state == "HIGH":
            return "High flexion range detected. Movement may be close to its limit."
        if state == "MEDIUM":
            return "Functional flexion range detected. Movement appears within an active zone."
        return "Low flexion detected. The limb or object may be close to extension."

    if "emg" in indicator_l or "effort" in indicator_l:
        if state == "HIGH":
            return "High muscle activation detected. This may indicate strong contraction or excessive effort."
        if state == "MEDIUM":
            return "Moderate muscle activation detected. This may indicate active participation."
        return "Low muscle activation detected. The muscle may be relaxed or inactive."

    if "arousal" in indicator_l:
        if state == "HIGH":
            return "High physiological activation detected. This may indicate arousal, stress, or high engagement."
        if state == "MEDIUM":
            return "Moderate physiological activation detected."
        return "Low or stable activation detected. This may suggest a calmer state."

    return f"Current indicator value is {percent}%. State: {state}."


# =========================
# MAIN APP
# =========================

def main(page: ft.Page):
    page.title = "Clinical Dark Sensor Dashboard"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 18
    page.window_width = 1240
    page.window_height = 860
    page.scroll = ft.ScrollMode.AUTO
    page.bgcolor = BG

    start_time = time.time()

    def safe_update():
        try:
            page.update()
            return True
        except Exception:
            app_state["running"] = False
            return False

    # =========================
    # UI TEXTS
    # =========================

    title = ft.Text(
        "Clinical Sensor Dashboard",
        size=32,
        weight=ft.FontWeight.BOLD,
        color=TEXT,
    )

    subtitle = ft.Text(
        "Real-time ESP32 sensor data, patient indicator, trend graph, and CSV logging",
        size=14,
        color=MUTED,
    )

    port_dropdown = ft.Dropdown(
        label="Serial port",
        width=300,
        options=[],
    )

    baud_dropdown = ft.Dropdown(
        label="Baud rate",
        width=150,
        value=str(DEFAULT_BAUD),
        options=[
            ft.DropdownOption(key="9600", text="9600"),
            ft.DropdownOption(key="115200", text="115200"),
        ],
    )

    simulate_switch = ft.Switch(
        label="Simulation",
        value=False,
    )

    status_text = ft.Text(
        "Status: waiting",
        size=13,
        color=AMBER,
    )

    connection_text = ft.Text(
        "Disconnected",
        size=14,
        weight=ft.FontWeight.BOLD,
        color=RED,
    )

    recording_text = ft.Text(
        "CSV recording: inactive",
        size=13,
        color=MUTED,
    )

    indicator_text = ft.Text(
        "Pressure Load Index",
        size=18,
        color=CYAN,
        weight=ft.FontWeight.BOLD,
    )

    percent_text = ft.Text(
        "--%",
        size=76,
        weight=ft.FontWeight.BOLD,
        color=TEXT,
    )

    raw_text = ft.Text(
        "Raw: --",
        size=22,
        weight=ft.FontWeight.BOLD,
        color=TEXT,
    )

    state_badge_text = ft.Text(
        "WAITING",
        size=14,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.BLACK,
    )

    state_badge = ft.Container(
        content=state_badge_text,
        padding=ft.Padding.only(left=14, right=14, top=8, bottom=8),
        border_radius=99,
        bgcolor=MUTED,
    )

    operator_badge_text = ft.Text(
        "NO DATA",
        size=13,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.BLACK,
    )

    operator_badge = ft.Container(
        content=operator_badge_text,
        padding=ft.Padding.only(left=14, right=14, top=8, bottom=8),
        border_radius=99,
        bgcolor=MUTED,
    )

    progress_bar = ft.ProgressBar(
        value=0,
        width=520,
        color=CYAN,
        bgcolor="#1E293B",
    )

    interpretation_text = ft.Text(
        "Waiting for ESP32 data.",
        size=16,
        color=TEXT,
    )

    range_text = ft.Text(
        "Graph range: --",
        size=13,
        color=MUTED,
    )

    last_event_text = ft.Text(
        "Last event: Waiting",
        size=13,
        color=MUTED,
    )

    raw_line_text = ft.Text(
        "Last raw serial line: --",
        size=12,
        color=MUTED,
        selectable=True,
    )

    session_time_text = ft.Text(
        "Session time: 00:00",
        size=13,
        color=MUTED,
    )

    # =========================
    # CHART
    # =========================

    sensor_chart = fch.LineChart(
        min_x=0,
        max_x=BUFFER_SIZE - 1,
        min_y=0,
        max_y=100,
        expand=True,
        horizontal_grid_lines=fch.ChartGridLines(
            interval=10,
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
            title=ft.Text("Index %", color=MUTED),
        ),
        bottom_axis=fch.ChartAxis(
            label_size=28,
            title=ft.Text("Samples", color=MUTED),
        ),
        bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
        data_series=[],
    )

    # =========================
    # UI HELPERS
    # =========================

    def small_metric_card(title_text, value_control, accent_color):
        return ft.Container(
            expand=True,
            padding=16,
            border_radius=18,
            bgcolor=PANEL_2,
            border=ft.Border.all(1, BORDER),
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Text(title_text, size=12, color=MUTED),
                    value_control,
                    ft.Container(height=3, bgcolor=accent_color, border_radius=99),
                ],
            ),
        )

    # =========================
    # PANELS
    # =========================

    connection_panel = ft.Card(
        bgcolor=PANEL,
        content=ft.Container(
            padding=18,
            border=ft.Border.all(1, BORDER),
            border_radius=12,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("Device connection", size=20, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(
                        "Connect to the ESP32 Serial output. Close Arduino Serial Monitor before connecting.",
                        size=13,
                        color=MUTED,
                    ),
                    ft.Row(
                        controls=[
                            port_dropdown,
                            baud_dropdown,
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip="Refresh ports",
                                icon_color=CYAN,
                                on_click=lambda e: refresh_ports(),
                            ),
                        ],
                        wrap=True,
                        spacing=10,
                    ),
                    simulate_switch,
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Connect",
                                icon=ft.Icons.USB,
                                on_click=lambda e: connect_serial(),
                            ),
                            ft.OutlinedButton(
                                "Disconnect",
                                icon=ft.Icons.LINK_OFF,
                                on_click=lambda e: disconnect_serial(),
                            ),
                        ],
                        wrap=True,
                        spacing=10,
                    ),
                    connection_text,
                    status_text,
                    raw_line_text,
                ],
            ),
        ),
    )

    recording_panel = ft.Card(
        bgcolor=PANEL,
        content=ft.Container(
            padding=18,
            border=ft.Border.all(1, BORDER),
            border_radius=12,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Text("Session recording", size=20, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text("Save patient/operator data as CSV.", size=13, color=MUTED),
                    ft.Row(
                        controls=[
                            ft.FilledButton(
                                "Start CSV",
                                icon=ft.Icons.SAVE,
                                on_click=lambda e: start_recording(),
                            ),
                            ft.OutlinedButton(
                                "Stop CSV",
                                icon=ft.Icons.STOP_CIRCLE,
                                on_click=lambda e: stop_recording(),
                            ),
                        ],
                        wrap=True,
                        spacing=10,
                    ),
                    recording_text,
                    session_time_text,
                ],
            ),
        ),
    )

    metric_panel = ft.Card(
        bgcolor=PANEL,
        content=ft.Container(
            padding=22,
            border=ft.Border.all(1, BORDER),
            border_radius=12,
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=4,
                                controls=[
                                    ft.Text("Patient data indicator", size=13, color=MUTED),
                                    indicator_text,
                                ],
                            ),
                            state_badge,
                        ],
                    ),
                    percent_text,
                    progress_bar,
                    ft.Row(
                        controls=[
                            small_metric_card("Raw value", raw_text, BLUE),
                            small_metric_card("Operator status", operator_badge, GREEN),
                        ],
                        spacing=12,
                    ),
                    ft.Divider(color=BORDER),
                    ft.Text("Patient / operator meaning", size=14, weight=ft.FontWeight.BOLD, color=TEXT),
                    interpretation_text,
                    last_event_text,
                ],
            ),
        ),
    )

    graph_panel = ft.Card(
        bgcolor=PANEL,
        content=ft.Container(
            padding=18,
            border=ft.Border.all(1, BORDER),
            border_radius=12,
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Live sensor trend", size=20, weight=ft.FontWeight.BOLD, color=TEXT),
                            range_text,
                        ],
                    ),
                    ft.Text(
                        "Auto-scaled line graph of the latest normalized values.",
                        size=13,
                        color=MUTED,
                    ),
                    ft.Container(
                        height=340,
                        content=sensor_chart,
                    ),
                ],
            ),
        ),
    )

    ai_panel = ft.Card(
        bgcolor="#102A43",
        content=ft.Container(
            padding=18,
            border=ft.Border.all(1, "#1E3A5F"),
            border_radius=12,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Text("Future AI layer", size=20, weight=ft.FontWeight.BOLD, color=TEXT),
                    ft.Text(
                        "This data could later classify risk states, detect fatigue, identify excessive effort, or recommend adjustments based on previous sessions.",
                        size=14,
                        color="#D7E8F5",
                    ),
                ],
            ),
        ),
    )

    page.add(
        ft.Column(
            spacing=12,
            controls=[
                title,
                subtitle,
                ft.ResponsiveRow(
                    controls=[
                        ft.Column(
                            col={"xs": 12, "lg": 4},
                            controls=[connection_panel, recording_panel, ai_panel],
                        ),
                        ft.Column(
                            col={"xs": 12, "lg": 8},
                            controls=[metric_panel, graph_panel],
                        ),
                    ],
                ),
            ],
        )
    )

    # =========================
    # FUNCTIONS
    # =========================

    def refresh_ports():
        ports = list_serial_ports()
        port_dropdown.options = [
            ft.DropdownOption(key=p, text=p)
            for p in ports
        ]

        if ports and port_dropdown.value not in ports:
            port_dropdown.value = ports[0]

        if not ports:
            port_dropdown.value = None

        safe_update()

    def set_status(message, color=MUTED):
        status_text.value = message
        status_text.color = color
        safe_update()

    def connect_serial():
        app_state["simulate"] = bool(simulate_switch.value)

        if app_state["simulate"]:
            app_state["running"] = True
            app_state["connected"] = False
            app_state["last_event"] = "Simulation started"
            connection_text.value = "Simulation mode"
            connection_text.color = BLUE
            set_status("Simulation active.", BLUE)
            page.run_task(ui_update_loop)
            return

        port = port_dropdown.value
        baud = int(baud_dropdown.value or DEFAULT_BAUD)

        if not port:
            set_status("Select a serial port first.", RED)
            return

        try:
            ser = serial.Serial(port, baud, timeout=SERIAL_TIMEOUT)
            time.sleep(2.0)

            try:
                ser.reset_input_buffer()
            except Exception:
                pass

            app_state["ser"] = ser
            app_state["connected"] = True
            app_state["running"] = True
            app_state["last_event"] = f"Connected to {port}"

            connection_text.value = f"Connected to {port} @ {baud}"
            connection_text.color = GREEN

            set_status("Serial connection active. Waiting for CSV data...", GREEN)

            page.run_thread(serial_reader_loop)
            page.run_task(ui_update_loop)

        except Exception as ex:
            app_state["ser"] = None
            app_state["connected"] = False
            connection_text.value = "Disconnected"
            connection_text.color = RED
            set_status(f"Could not connect: {ex}", RED)

    def disconnect_serial():
        app_state["running"] = False
        app_state["simulate"] = False

        try:
            if app_state["ser"] is not None:
                app_state["ser"].close()
        except Exception:
            pass

        app_state["ser"] = None
        app_state["connected"] = False
        app_state["last_event"] = "Disconnected"

        connection_text.value = "Disconnected"
        connection_text.color = RED
        set_status("Disconnected.", MUTED)
        safe_update()

    def start_recording():
        if app_state["recording"]:
            set_status("CSV is already recording.", AMBER)
            return

        os.makedirs(CSV_FOLDER, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(CSV_FOLDER, f"sensor_session_{timestamp}.csv")

        try:
            f = open(filepath, "w", newline="", encoding="utf-8")
            writer = csv.writer(f)

            writer.writerow([
                "timestamp",
                "time_ms",
                "raw",
                "percent",
                "state",
                "indicator",
                "interpretation",
            ])

            app_state["csv_file"] = f
            app_state["csv_writer"] = writer
            app_state["csv_path"] = filepath
            app_state["recording"] = True
            app_state["last_event"] = "CSV recording started"

            recording_text.value = f"CSV recording: active\n{filepath}"
            set_status("CSV recording started.", GREEN)

        except Exception as ex:
            set_status(f"Could not start CSV: {ex}", RED)

    def stop_recording():
        if not app_state["recording"]:
            set_status("No active CSV recording.", AMBER)
            return

        try:
            if app_state["csv_file"] is not None:
                app_state["csv_file"].close()
        except Exception:
            pass

        path = app_state["csv_path"]

        app_state["csv_file"] = None
        app_state["csv_writer"] = None
        app_state["csv_path"] = None
        app_state["recording"] = False
        app_state["last_event"] = "CSV recording stopped"

        recording_text.value = "CSV recording: inactive"
        set_status(f"CSV saved: {path}", BLUE)

    def write_csv_row():
        if not app_state["recording"] or app_state["csv_writer"] is None:
            return

        interpretation = get_interpretation(
            app_state["indicator"],
            app_state["state"],
            app_state["percent"],
        )

        app_state["csv_writer"].writerow([
            datetime.now().isoformat(timespec="milliseconds"),
            app_state["time_ms"],
            app_state["raw"],
            app_state["percent"],
            app_state["state"],
            app_state["indicator"],
            interpretation,
        ])

        try:
            app_state["csv_file"].flush()
        except Exception:
            pass

    def simulate_sample():
        now = int(time.time() * 1000)
        base = app_state["percent"]

        if base <= 0:
            base = 45

        percent = int(max(0, min(100, base + random.randint(-8, 8))))
        raw = int((percent / 100) * ESP32_ADC_MAX)

        if percent < 35:
            state = "LOW"
        elif percent < 70:
            state = "MEDIUM"
        else:
            state = "HIGH"

        app_state["time_ms"] = now
        app_state["raw"] = raw
        app_state["percent"] = percent
        app_state["state"] = state
        app_state["indicator"] = "Pressure Load Index"
        app_state["last_event"] = "Simulation data"
        app_state["last_raw_line"] = f"{now},{raw},{percent},{state},Pressure Load Index"

        percent_buffer.append(percent)
        write_csv_row()

    def update_charts_and_ui():
        percent = app_state["percent"]
        state = app_state["state"]
        indicator = app_state["indicator"]
        raw = app_state["raw"]

        percent_text.value = f"{percent}%"
        raw_text.value = f"Raw: {raw}"
        indicator_text.value = indicator

        color = get_status_color(state)

        state_badge.bgcolor = color
        state_badge_text.value = state

        operator_badge.bgcolor = color
        operator_badge_text.value = get_status_label(state)

        progress_bar.value = percent / 100
        progress_bar.color = color

        interpretation_text.value = get_interpretation(indicator, state, percent)
        last_event_text.value = f"Last event: {app_state['last_event']}"
        raw_line_text.value = f"Last raw serial line: {app_state['last_raw_line'] or '--'}"

        elapsed = int(time.time() - start_time)
        minutes = elapsed // 60
        seconds = elapsed % 60
        session_time_text.value = f"Session time: {minutes:02d}:{seconds:02d}"

        # IMPORTANT:
        # Make one stable copy of the deque before charting.
        # This avoids: RuntimeError: deque mutated during iteration.
        buffer_snapshot = list(percent_buffer)

        min_y, max_y = get_auto_range(buffer_snapshot)

        sensor_chart.min_y = min_y
        sensor_chart.max_y = max_y

        sensor_chart.data_series = [
            fch.LineChartData(
                points=buffer_to_points(buffer_snapshot),
                stroke_width=3,
                curved=True,
                color=CYAN,
            )
        ]

        range_text.value = f"Graph range: {min_y:.0f}–{max_y:.0f}%"

        return safe_update()

    def serial_reader_loop():
        while app_state["running"] and not app_state["simulate"]:
            ser = app_state["ser"]

            if ser is None or not app_state["connected"]:
                time.sleep(0.05)
                continue

            try:
                raw_line = ser.readline().decode("utf-8", errors="ignore").strip()

                if raw_line:
                    app_state["last_raw_line"] = raw_line

                parsed = parse_serial_line(raw_line)

                if parsed is None:
                    continue

                time_ms, raw, percent, state, indicator = parsed

                app_state["time_ms"] = time_ms
                app_state["raw"] = raw
                app_state["percent"] = percent
                app_state["state"] = state
                app_state["indicator"] = indicator
                app_state["last_event"] = "Data received"

                percent_buffer.append(percent)

                write_csv_row()

            except Exception as ex:
                app_state["last_event"] = f"Serial read error: {ex}"

            time.sleep(0.001)

    async def ui_update_loop():
        while app_state["running"]:
            if app_state["simulate"]:
                simulate_sample()

            ok = update_charts_and_ui()

            if not ok:
                break

            await asyncio.sleep(UPDATE_INTERVAL)

    refresh_ports()
    update_charts_and_ui()


if __name__ == "__main__":
    ft.run(main)