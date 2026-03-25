import { View, Dimensions, StyleSheet } from "react-native";
import { LineChart } from "react-native-chart-kit";

const SCREEN_WIDTH = Dimensions.get("window").width;

const PLACEHOLDER_DATA = {
  labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
  datasets: [
    {
      data: [68, 72, 70, 74, 71, 69, 72],
      color: () => "#4fc3f7",
      strokeWidth: 2,
    },
  ],
};

export function HealthChart() {
  return (
    <View style={styles.container}>
      <LineChart
        data={PLACEHOLDER_DATA}
        width={SCREEN_WIDTH - 40}
        height={200}
        yAxisSuffix=" bpm"
        chartConfig={{
          backgroundColor: "#1a1d27",
          backgroundGradientFrom: "#1a1d27",
          backgroundGradientTo: "#1a1d27",
          decimalCount: 0,
          color: (opacity = 1) => `rgba(79, 195, 247, ${opacity})`,
          labelColor: () => "#888",
          style: { borderRadius: 12 },
          propsForDots: {
            r: "4",
            strokeWidth: "2",
            stroke: "#4fc3f7",
          },
        }}
        bezier
        style={styles.chart}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    marginBottom: 8,
  },
  chart: {
    borderRadius: 12,
  },
});
