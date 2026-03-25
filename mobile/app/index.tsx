import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from "react-native";
import { useRouter } from "expo-router";
import { HealthChart } from "../components/charts/HealthChart";
import { StatsCard } from "../components/shared/StatsCard";

const PLACEHOLDER_STATS = [
  { label: "Steps", value: "8,432" },
  { label: "Heart Rate", value: "72 bpm" },
  { label: "Sleep", value: "7h 23m" },
  { label: "Calories", value: "2,145" },
];

export default function DashboardScreen() {
  const router = useRouter();

  const handleSync = () => {
    // TODO: Call backend sync endpoint
    console.log("Sync triggered");
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.greeting}>Good morning</Text>
      <Text style={styles.date}>Today's Overview</Text>

      <View style={styles.statsGrid}>
        {PLACEHOLDER_STATS.map((stat) => (
          <StatsCard key={stat.label} label={stat.label} value={stat.value} />
        ))}
      </View>

      <Text style={styles.sectionTitle}>Heart Rate (7 days)</Text>
      <HealthChart />

      <TouchableOpacity style={styles.syncButton} onPress={handleSync}>
        <Text style={styles.syncButtonText}>Sync Garmin Data</Text>
      </TouchableOpacity>

      <View style={styles.navRow}>
        <TouchableOpacity
          style={styles.navButton}
          onPress={() => router.push("/ask")}
        >
          <Text style={styles.navButtonText}>Ask AI</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.navButton}
          onPress={() => router.push("/settings")}
        >
          <Text style={styles.navButtonText}>Settings</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f1117",
  },
  content: {
    padding: 20,
    paddingBottom: 40,
  },
  greeting: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#e0e0e0",
    marginBottom: 4,
  },
  date: {
    fontSize: 16,
    color: "#888",
    marginBottom: 20,
  },
  statsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: "#e0e0e0",
    marginBottom: 12,
  },
  syncButton: {
    backgroundColor: "#4fc3f7",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 24,
    marginBottom: 16,
  },
  syncButtonText: {
    color: "#0f1117",
    fontSize: 16,
    fontWeight: "bold",
  },
  navRow: {
    flexDirection: "row",
    gap: 12,
  },
  navButton: {
    flex: 1,
    backgroundColor: "#1a1d27",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#2a2d37",
  },
  navButtonText: {
    color: "#4fc3f7",
    fontSize: 15,
    fontWeight: "600",
  },
});
