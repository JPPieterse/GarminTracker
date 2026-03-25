import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from "react-native";

export default function SettingsScreen() {
  const handleConnectGarmin = () => {
    // TODO: Trigger Garmin credential flow via backend
    console.log("Connect Garmin");
  };

  const handleLogout = () => {
    // TODO: Clear SecureStore tokens and redirect to login
    console.log("Logout");
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.sectionTitle}>Garmin Connect</Text>
      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.label}>Status</Text>
          <View style={styles.statusBadge}>
            <Text style={styles.statusText}>Not Connected</Text>
          </View>
        </View>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={handleConnectGarmin}
        >
          <Text style={styles.primaryButtonText}>Connect Garmin Account</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.sectionTitle}>Subscription</Text>
      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.label}>Plan</Text>
          <Text style={styles.value}>Free</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>AI Queries</Text>
          <Text style={styles.value}>0 / 10 used</Text>
        </View>
        <TouchableOpacity style={styles.upgradeButton}>
          <Text style={styles.upgradeButtonText}>Upgrade to Pro</Text>
        </TouchableOpacity>
      </View>

      <Text style={styles.sectionTitle}>Account</Text>
      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.label}>Email</Text>
          <Text style={styles.value}>Not signed in</Text>
        </View>
        <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
          <Text style={styles.logoutButtonText}>Log Out</Text>
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
  sectionTitle: {
    fontSize: 18,
    fontWeight: "600",
    color: "#e0e0e0",
    marginBottom: 12,
    marginTop: 8,
  },
  card: {
    backgroundColor: "#1a1d27",
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: "#2a2d37",
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  label: {
    fontSize: 15,
    color: "#888",
  },
  value: {
    fontSize: 15,
    color: "#e0e0e0",
  },
  statusBadge: {
    backgroundColor: "#332200",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  statusText: {
    color: "#ffaa00",
    fontSize: 13,
    fontWeight: "600",
  },
  primaryButton: {
    backgroundColor: "#4fc3f7",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 4,
  },
  primaryButtonText: {
    color: "#0f1117",
    fontSize: 15,
    fontWeight: "bold",
  },
  upgradeButton: {
    backgroundColor: "transparent",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 4,
    borderWidth: 1,
    borderColor: "#4fc3f7",
  },
  upgradeButtonText: {
    color: "#4fc3f7",
    fontSize: 15,
    fontWeight: "600",
  },
  logoutButton: {
    backgroundColor: "transparent",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 4,
    borderWidth: 1,
    borderColor: "#ff5252",
  },
  logoutButtonText: {
    color: "#ff5252",
    fontSize: 15,
    fontWeight: "600",
  },
});
