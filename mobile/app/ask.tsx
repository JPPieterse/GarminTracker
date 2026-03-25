import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";

const MODELS = ["claude-sonnet-4-20250514", "claude-haiku-4-20250414"];

export default function AskScreen() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedModel, setSelectedModel] = useState(MODELS[0]);

  const handleAsk = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setAnswer("");

    try {
      // TODO: Call backend /api/ask endpoint with Bearer token from SecureStore
      // const response = await fetchApi("/api/ask", {
      //   method: "POST",
      //   body: JSON.stringify({ question, model: selectedModel }),
      // });
      // setAnswer(response.answer);
      setAnswer(
        "AI responses will appear here once the backend is connected and Auth0 is configured."
      );
    } catch (error) {
      setAnswer("Error: Could not get a response. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Ask about your health data</Text>

      <View style={styles.modelSelector}>
        {MODELS.map((model) => (
          <TouchableOpacity
            key={model}
            style={[
              styles.modelChip,
              selectedModel === model && styles.modelChipActive,
            ]}
            onPress={() => setSelectedModel(model)}
          >
            <Text
              style={[
                styles.modelChipText,
                selectedModel === model && styles.modelChipTextActive,
              ]}
            >
              {model.includes("sonnet") ? "Sonnet" : "Haiku"}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TextInput
        style={styles.input}
        placeholder="e.g. How has my sleep quality changed this week?"
        placeholderTextColor="#666"
        value={question}
        onChangeText={setQuestion}
        multiline
        numberOfLines={3}
      />

      <TouchableOpacity
        style={[styles.askButton, loading && styles.askButtonDisabled]}
        onPress={handleAsk}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#0f1117" />
        ) : (
          <Text style={styles.askButtonText}>Ask</Text>
        )}
      </TouchableOpacity>

      {answer ? (
        <View style={styles.answerCard}>
          <Text style={styles.answerLabel}>Answer</Text>
          <Text style={styles.answerText}>{answer}</Text>
        </View>
      ) : null}
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
  title: {
    fontSize: 22,
    fontWeight: "bold",
    color: "#e0e0e0",
    marginBottom: 16,
  },
  modelSelector: {
    flexDirection: "row",
    gap: 10,
    marginBottom: 16,
  },
  modelChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: "#1a1d27",
    borderWidth: 1,
    borderColor: "#2a2d37",
  },
  modelChipActive: {
    backgroundColor: "#4fc3f7",
    borderColor: "#4fc3f7",
  },
  modelChipText: {
    color: "#888",
    fontSize: 14,
    fontWeight: "600",
  },
  modelChipTextActive: {
    color: "#0f1117",
  },
  input: {
    backgroundColor: "#1a1d27",
    borderRadius: 12,
    padding: 16,
    color: "#e0e0e0",
    fontSize: 16,
    borderWidth: 1,
    borderColor: "#2a2d37",
    minHeight: 80,
    textAlignVertical: "top",
    marginBottom: 16,
  },
  askButton: {
    backgroundColor: "#4fc3f7",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    marginBottom: 24,
  },
  askButtonDisabled: {
    opacity: 0.6,
  },
  askButtonText: {
    color: "#0f1117",
    fontSize: 16,
    fontWeight: "bold",
  },
  answerCard: {
    backgroundColor: "#1a1d27",
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: "#2a2d37",
  },
  answerLabel: {
    fontSize: 14,
    fontWeight: "600",
    color: "#4fc3f7",
    marginBottom: 8,
  },
  answerText: {
    fontSize: 15,
    color: "#e0e0e0",
    lineHeight: 22,
  },
});
