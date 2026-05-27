import React, { useEffect, useRef, useState } from "react";
import {
  SafeAreaView,
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  ScrollView,
} from "react-native";
import Svg, { Polyline, Circle, Line, Text as SvgText } from "react-native-svg";

const DEFAULT_INPUT = "http://192.168.1.80/data";
const MAX_POINTS = 40;

export default function App() {
  const [esp32Input, setEsp32Input] = useState(DEFAULT_INPUT);
  const [useSimulation, setUseSimulation] = useState(true);
  const [connectionStatus, setConnectionStatus] = useState("SIMULATION MODE");

  const [sensorData, setSensorData] = useState({
    time_ms: 0,
    raw: 0,
    percent: 0,
    state: "LOW",
    indicator: "Pressure Load Index",
  });

  const [history, setHistory] = useState(Array(MAX_POINTS).fill(0));
  const intervalRef = useRef(null);

  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    if (useSimulation) {
      simulateData();
      intervalRef.current = setInterval(simulateData, 800);
    } else {
      readESP32Data();
      intervalRef.current = setInterval(readESP32Data, 800);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [useSimulation, esp32Input]);

  function getESP32Url(input) {
    const cleanInput = input.trim();

    if (cleanInput.startsWith("http://") || cleanInput.startsWith("https://")) {
      if (cleanInput.endsWith("/data")) {
        return cleanInput;
      }
      return `${cleanInput}/data`;
    }

    return `http://${cleanInput}/data`;
  }

  async function readESP32Data() {
    try {
      const url = getESP32Url(esp32Input);

      console.log("Reading from:", url);

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
      }

      const data = await response.json();

      setConnectionStatus("ONLINE / ESP32 DATA");
      updateData(data);
    } catch (error) {
      setConnectionStatus("CONNECTION ERROR");
      console.log("ESP32 error:", error.message);
    }
  }

  function simulateData() {
    const percent = Math.floor(35 + Math.random() * 45);
    const raw = Math.floor((percent / 100) * 4095);

    const state =
      percent < 35 ? "LOW" : percent < 70 ? "MEDIUM" : "HIGH";

    updateData({
      time_ms: Date.now(),
      raw,
      percent,
      state,
      indicator: "Pressure Load Index",
    });

    setConnectionStatus("SIMULATION MODE");
  }

  function updateData(data) {
    const cleanPercent = Math.max(0, Math.min(100, Number(data.percent || 0)));

    const cleanData = {
      time_ms: data.time_ms || Date.now(),
      raw: data.raw ?? 0,
      percent: cleanPercent,
      state: data.state || "LOW",
      indicator: data.indicator || "User Data Indicator",
    };

    setSensorData(cleanData);

    setHistory((prev) => [...prev.slice(1), cleanPercent]);
  }

  function connectToESP32() {
    const cleanInput = esp32Input.trim();

    if (!cleanInput) {
      setConnectionStatus("TYPE ESP32 IP OR URL");
      return;
    }

    setEsp32Input(cleanInput);
    setUseSimulation(false);
    setConnectionStatus("CONNECTING...");
  }

  function activateSimulation() {
    setUseSimulation(true);
    setConnectionStatus("SIMULATION MODE");
  }

  function getStatusStyle(state) {
    if (state === "HIGH") return styles.statusAlert;
    if (state === "MEDIUM") return styles.statusCaution;
    return styles.statusSafe;
  }

  function getInterpretation(data) {
    const indicator = String(data.indicator || "").toLowerCase();
    const state = String(data.state || "LOW").toUpperCase();

    if (indicator.includes("pressure")) {
      if (state === "HIGH") {
        return "High pressure load detected. The user may be applying excessive support or force.";
      }
      if (state === "MEDIUM") {
        return "Moderate pressure load detected. Continue monitoring during the activity.";
      }
      return "Low pressure load detected. The user is applying minimal force.";
    }

    if (indicator.includes("flexion")) {
      if (state === "HIGH") {
        return "High flexion range detected. Movement may be close to its limit.";
      }
      if (state === "MEDIUM") {
        return "Functional flexion range detected. Movement appears within an active zone.";
      }
      return "Low flexion detected. The limb or object may be close to extension.";
    }

    if (indicator.includes("emg") || indicator.includes("effort")) {
      if (state === "HIGH") {
        return "High muscle activation detected. This may indicate strong contraction or excessive effort.";
      }
      if (state === "MEDIUM") {
        return "Moderate muscle activation detected. This may indicate active participation.";
      }
      return "Low muscle activation detected. The muscle may be relaxed or inactive.";
    }

    if (indicator.includes("arousal")) {
      if (state === "HIGH") {
        return "High physiological activation detected. This may indicate arousal, stress, or high engagement.";
      }
      if (state === "MEDIUM") {
        return "Moderate physiological activation detected.";
      }
      return "Low or stable activation detected. This may suggest a calmer state.";
    }

    return `Current indicator value is ${data.percent}%. State: ${state}.`;
  }

  const endpointText = getESP32Url(esp32Input);

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.eyebrow}>ESP32 + Expo Go</Text>
        <Text style={styles.title}>Patient Sensor Monitor</Text>
        <Text style={styles.subtitle}>
          Mobile interface for visualizing live sensor data, user indicators,
          and operator feedback.
        </Text>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Device connection</Text>
          <Text style={styles.smallText}>
            Type only the ESP32 IP or the full URL.
          </Text>

          <TextInput
            value={esp32Input}
            onChangeText={setEsp32Input}
            placeholder="192.168.1.80 or http://192.168.1.80/data"
            autoCapitalize="none"
            keyboardType="url"
            style={styles.input}
          />

          <View style={styles.buttonRow}>
            <Pressable style={styles.primaryButton} onPress={connectToESP32}>
              <Text style={styles.primaryButtonText}>Connect</Text>
            </Pressable>

            <Pressable style={styles.secondaryButton} onPress={activateSimulation}>
              <Text style={styles.secondaryButtonText}>Simulation</Text>
            </Pressable>
          </View>

          <Text style={styles.connectionText}>{connectionStatus}</Text>
          <Text style={styles.endpoint}>Endpoint: {endpointText}</Text>
        </View>

        <View style={styles.metricCard}>
          <Text style={styles.indicatorLabel}>{sensorData.indicator}</Text>

          <View style={styles.valueRow}>
            <Text style={styles.bigValue}>{sensorData.percent}%</Text>

            <View style={[styles.statusPill, getStatusStyle(sensorData.state)]}>
              <Text style={styles.statusText}>{sensorData.state}</Text>
            </View>
          </View>

          <View style={styles.progressBackground}>
            <View
              style={[
                styles.progressFill,
                { width: `${sensorData.percent}%` },
              ]}
            />
          </View>

          <View style={styles.detailsRow}>
            <View style={styles.detailBox}>
              <Text style={styles.detailLabel}>Raw value</Text>
              <Text style={styles.detailValue}>{sensorData.raw}</Text>
            </View>

            <View style={styles.detailBox}>
              <Text style={styles.detailLabel}>Range</Text>
              <Text style={styles.detailValue}>0–4095</Text>
            </View>
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Live sensor trend</Text>
          <Text style={styles.smallText}>
            Auto-scaled line graph using the latest values.
          </Text>

          <LineGraph values={history} />
        </View>

        <View style={styles.card}>
          <Text style={styles.sectionTitle}>Patient / operator meaning</Text>
          <Text style={styles.interpretationText}>
            {getInterpretation(sensorData)}
          </Text>
        </View>

        <View style={styles.aiCard}>
          <Text style={styles.sectionTitle}>Future AI layer</Text>
          <Text style={styles.smallText}>
            In a future version, this data could classify risk states, detect
            fatigue, identify excessive effort, or recommend adjustments based
            on previous sessions.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function LineGraph({ values }) {
  const width = 320;
  const height = 180;
  const padding = 22;

  let minValue = Math.min(...values);
  let maxValue = Math.max(...values);

  if (maxValue - minValue < 8) {
    const center = (maxValue + minValue) / 2;
    minValue = Math.max(0, center - 4);
    maxValue = Math.min(100, center + 4);
  } else {
    const pad = (maxValue - minValue) * 0.15;
    minValue = Math.max(0, minValue - pad);
    maxValue = Math.min(100, maxValue + pad);
  }

  const range = maxValue - minValue || 1;

  const points = values
    .map((value, index) => {
      const x = padding + (index / (values.length - 1)) * (width - padding * 2);
      const normalized = (value - minValue) / range;
      const y = height - padding - normalized * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");

  const lastValue = values[values.length - 1];
  const lastX =
    padding + ((values.length - 1) / (values.length - 1)) * (width - padding * 2);
  const lastNormalized = (lastValue - minValue) / range;
  const lastY = height - padding - lastNormalized * (height - padding * 2);

  return (
    <Svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
      <Line
        x1={padding}
        y1={padding}
        x2={padding}
        y2={height - padding}
        stroke="#D8E4EC"
        strokeWidth="1"
      />
      <Line
        x1={padding}
        y1={height - padding}
        x2={width - padding}
        y2={height - padding}
        stroke="#D8E4EC"
        strokeWidth="1"
      />
      <Line
        x1={padding}
        y1={height / 2}
        x2={width - padding}
        y2={height / 2}
        stroke="#EDF4F8"
        strokeWidth="1"
      />

      <Polyline
        points={points}
        fill="none"
        stroke="#0F6EA8"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      <Circle cx={lastX} cy={lastY} r="5" fill="#0F6EA8" />

      <SvgText x={padding} y={18} fill="#607085" fontSize="11">
        Auto-scaled trend
      </SvgText>

      <SvgText x={width - 82} y={18} fill="#607085" fontSize="11">
        {Math.round(minValue)}–{Math.round(maxValue)}%
      </SvgText>
    </Svg>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: "#EEF4F8",
  },
  container: {
    padding: 20,
    paddingBottom: 40,
  },
  eyebrow: {
    fontSize: 12,
    letterSpacing: 2,
    color: "#607085",
    textTransform: "uppercase",
    marginTop: 6,
  },
  title: {
    fontSize: 36,
    fontWeight: "800",
    color: "#102033",
    letterSpacing: -1.2,
    marginTop: 8,
  },
  subtitle: {
    fontSize: 15,
    color: "#607085",
    lineHeight: 22,
    marginTop: 10,
    marginBottom: 20,
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 22,
    padding: 18,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#D8E4EC",
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: "700",
    color: "#102033",
    marginBottom: 6,
  },
  smallText: {
    fontSize: 14,
    color: "#607085",
    lineHeight: 20,
  },
  input: {
    borderWidth: 1,
    borderColor: "#D8E4EC",
    borderRadius: 14,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    backgroundColor: "#F8FBFD",
    marginTop: 14,
  },
  buttonRow: {
    flexDirection: "row",
    gap: 10,
    marginTop: 12,
  },
  primaryButton: {
    backgroundColor: "#0F6EA8",
    paddingVertical: 12,
    paddingHorizontal: 18,
    borderRadius: 14,
  },
  primaryButtonText: {
    color: "white",
    fontWeight: "700",
  },
  secondaryButton: {
    backgroundColor: "#E8F3FA",
    paddingVertical: 12,
    paddingHorizontal: 18,
    borderRadius: 14,
  },
  secondaryButtonText: {
    color: "#0F6EA8",
    fontWeight: "700",
  },
  connectionText: {
    marginTop: 14,
    fontSize: 13,
    color: "#0F6EA8",
    fontWeight: "700",
  },
  endpoint: {
    marginTop: 4,
    fontSize: 12,
    color: "#607085",
  },
  metricCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 24,
    padding: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: "#D8E4EC",
  },
  indicatorLabel: {
    fontSize: 16,
    color: "#607085",
    marginBottom: 8,
  },
  valueRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  bigValue: {
    fontSize: 64,
    fontWeight: "800",
    color: "#102033",
    letterSpacing: -2,
  },
  statusPill: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 99,
  },
  statusSafe: {
    backgroundColor: "#1F9D72",
  },
  statusCaution: {
    backgroundColor: "#D99A21",
  },
  statusAlert: {
    backgroundColor: "#D84A4A",
  },
  statusText: {
    color: "white",
    fontSize: 13,
    fontWeight: "800",
  },
  progressBackground: {
    height: 14,
    borderRadius: 99,
    overflow: "hidden",
    backgroundColor: "#D8E4EC",
    marginVertical: 16,
  },
  progressFill: {
    height: "100%",
    backgroundColor: "#0F6EA8",
    borderRadius: 99,
  },
  detailsRow: {
    flexDirection: "row",
    gap: 12,
  },
  detailBox: {
    flex: 1,
    backgroundColor: "#F8FBFD",
    borderRadius: 16,
    padding: 14,
  },
  detailLabel: {
    fontSize: 12,
    color: "#607085",
  },
  detailValue: {
    fontSize: 24,
    fontWeight: "700",
    color: "#102033",
    marginTop: 4,
  },
  interpretationText: {
    color: "#102033",
    fontSize: 16,
    lineHeight: 24,
  },
  aiCard: {
    backgroundColor: "#DFF0FA",
    borderRadius: 24,
    padding: 20,
    borderWidth: 1,
    borderColor: "#B7D9EA",
  },
});