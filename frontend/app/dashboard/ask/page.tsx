"use client";

import { useState, useEffect, useRef } from "react";
import { Send, Mic, MicOff, Volume2, VolumeX, Bot } from "lucide-react";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import { askQuestion, getModels } from "@/lib/api";
import type { AskResponse, ModelInfo } from "@/lib/types";

const SUGGESTED_CHIPS = [
  "How did I sleep last week?",
  "What's my average heart rate?",
  "Am I more stressed than usual?",
  "How many steps this month?",
  "Compare my activity to last week",
];

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  useEffect(() => {
    getModels()
      .then((m) => {
        setModels(m);
        if (m.length > 0) setSelectedModel(m[0].id);
      })
      .catch(() => {});
  }, []);

  const handleAsk = async (q?: string) => {
    const text = q || question;
    if (!text.trim()) return;

    setLoading(true);
    setError("");
    setAnswer(null);

    try {
      const result = await askQuestion(
        text.trim(),
        selectedModel || undefined
      );
      setAnswer(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get answer");
    } finally {
      setLoading(false);
    }
  };

  // Speech-to-Text
  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }

    const SpeechRecognition =
      (window as unknown as { SpeechRecognition?: typeof window.SpeechRecognition }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: typeof window.SpeechRecognition }).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setError("Speech recognition is not supported in this browser.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0][0].transcript;
      setQuestion(transcript);
      setIsListening(false);
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  };

  // Text-to-Speech
  const toggleSpeaking = () => {
    if (isSpeaking) {
      speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    if (!answer?.answer) return;

    const utterance = new SpeechSynthesisUtterance(answer.answer);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    speechSynthesis.speak(utterance);
    setIsSpeaking(true);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-[#e0e0e0]">Ask AI</h1>
      <p className="text-[#888]">
        Ask questions about your health data and get AI-powered insights.
      </p>

      {/* Model Selector */}
      {models.length > 0 && (
        <div>
          <label className="block text-sm text-[#888] mb-1">Model</label>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="bg-card border border-border rounded-lg px-3 py-2 text-[#e0e0e0] text-sm focus:outline-none focus:border-brand w-full max-w-xs"
          >
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Input Area */}
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
            placeholder="Ask about your health data..."
            className="w-full bg-card border border-border rounded-lg px-4 py-3 text-[#e0e0e0] placeholder-[#888] focus:outline-none focus:border-brand"
          />
        </div>
        <button
          onClick={toggleListening}
          className={`p-3 rounded-lg border transition-colors ${
            isListening
              ? "bg-red-500/10 border-red-500/30 text-red-400"
              : "bg-card border-border text-[#888] hover:text-[#e0e0e0]"
          }`}
          title={isListening ? "Stop listening" : "Voice input"}
        >
          {isListening ? <MicOff size={20} /> : <Mic size={20} />}
        </button>
        <button
          onClick={() => handleAsk()}
          disabled={loading || !question.trim()}
          className="px-5 py-3 bg-brand text-dark font-semibold rounded-lg hover:bg-brand/90 transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          <Send size={16} />
          Ask
        </button>
      </div>

      {/* Suggested Chips */}
      <div className="flex flex-wrap gap-2">
        {SUGGESTED_CHIPS.map((chip) => (
          <button
            key={chip}
            onClick={() => {
              setQuestion(chip);
              handleAsk(chip);
            }}
            className="px-3 py-1.5 text-sm rounded-full border border-border text-[#888] hover:text-brand hover:border-brand/30 transition-colors"
          >
            {chip}
          </button>
        ))}
      </div>

      {/* Loading */}
      {loading && <LoadingSpinner />}

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Answer Display */}
      {answer && (
        <div className="bg-card border border-border rounded-lg p-6 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-brand">
              <Bot size={20} />
              <span className="text-sm font-medium">
                {answer.model || "AI"}
              </span>
            </div>
            <button
              onClick={toggleSpeaking}
              className={`p-2 rounded-lg transition-colors ${
                isSpeaking
                  ? "text-brand bg-brand/10"
                  : "text-[#888] hover:text-[#e0e0e0]"
              }`}
              title={isSpeaking ? "Stop speaking" : "Read aloud"}
            >
              {isSpeaking ? <VolumeX size={18} /> : <Volume2 size={18} />}
            </button>
          </div>
          <p className="text-[#e0e0e0] leading-relaxed whitespace-pre-wrap">
            {answer.answer}
          </p>
          {answer.sources && answer.sources.length > 0 && (
            <div className="pt-2 border-t border-border">
              <p className="text-xs text-[#888]">
                Sources: {answer.sources.join(", ")}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
