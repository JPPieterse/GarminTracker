import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: "#0f1117" },
          headerTintColor: "#e0e0e0",
          headerTitleStyle: { fontWeight: "bold" },
          contentStyle: { backgroundColor: "#0f1117" },
        }}
      >
        <Stack.Screen name="index" options={{ title: "ZEV" }} />
        <Stack.Screen name="ask" options={{ title: "Ask AI" }} />
        <Stack.Screen name="settings" options={{ title: "Settings" }} />
      </Stack>
    </>
  );
}
