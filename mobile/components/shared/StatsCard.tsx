import { View, Text, StyleSheet } from "react-native";

interface StatsCardProps {
  label: string;
  value: string;
}

export function StatsCard({ label, value }: StatsCardProps) {
  return (
    <View style={styles.card}>
      <Text style={styles.label}>{label}</Text>
      <Text style={styles.value}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#1a1d27",
    borderRadius: 12,
    padding: 16,
    minWidth: "46%",
    flexGrow: 1,
    borderWidth: 1,
    borderColor: "#2a2d37",
  },
  label: {
    fontSize: 13,
    color: "#888",
    marginBottom: 4,
  },
  value: {
    fontSize: 22,
    fontWeight: "bold",
    color: "#e0e0e0",
  },
});
