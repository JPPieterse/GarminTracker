"use client";

import { useState, useEffect, useRef } from "react";
import { Send, Mic, MicOff, Volume2, ArrowLeft, Check, CheckCheck } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import {
  askQuestion,
  getCoaches,
  getOnboardingStatus,
  sendOnboardingMessage,
} from "@/lib/api";
import type { Coach } from "@/lib/types";

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  time: string;
}

function timeNow() {
  return new Date().toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

// ── Coach Selection Screen ──────────────────────────────────────────────

function CoachPicker({
  coaches,
  onSelect,
}: {
  coaches: Coach[];
  onSelect: (c: Coach) => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-10"
      >
        <h1 className="text-3xl font-heading font-bold text-[#e0e0e0] mb-2">
          Choose Your Coach
        </h1>
        <p className="text-[#888] max-w-md">
          Each coach has a different personality and expertise.
          Pick the one that matches your vibe.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl w-full">
        {coaches.map((coach, i) => (
          <motion.button
            key={coach.id}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1, duration: 0.4 }}
            whileHover={{ y: -6, transition: { duration: 0.2 } }}
            onClick={() => onSelect(coach)}
            className="bg-card border border-border rounded-2xl p-6 text-left hover:border-brand/30 transition-colors group"
          >
            <div className="text-5xl mb-4">{coach.avatar}</div>
            <h2
              className="text-xl font-heading font-bold mb-1 group-hover:opacity-100 transition-opacity"
              style={{ color: coach.color }}
            >
              {coach.name}
            </h2>
            <p className="text-xs text-[#888] uppercase tracking-wider mb-3">
              {coach.title}
            </p>
            <p className="text-sm text-[#999] leading-relaxed">{coach.bio}</p>
          </motion.button>
        ))}
      </div>
    </div>
  );
}

// ── WhatsApp-style Chat ─────────────────────────────────────────────────

function CoachChat({
  coach,
  onChangeCoach,
}: {
  coach: Coach;
  onChangeCoach: () => void;
}) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [needsOnboarding, setNeedsOnboarding] = useState<boolean | null>(null);
  const [onboardingHistory, setOnboardingHistory] = useState<
    { role: string; content: string }[]
  >([]);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  // Check onboarding status on mount
  useEffect(() => {
    getOnboardingStatus()
      .then(async (status) => {
        if (status.needs_onboarding) {
          setNeedsOnboarding(true);
          // Start onboarding with this coach's personality
          setLoading(true);
          try {
            const result = await sendOnboardingMessage("", []);
            setMessages([
              { role: "assistant", content: result.reply, time: timeNow() },
            ]);
            setOnboardingHistory([
              { role: "assistant", content: result.reply },
            ]);
          } catch {
            setNeedsOnboarding(false);
          }
          setLoading(false);
        } else {
          setNeedsOnboarding(false);
          // Greeting from chosen coach
          setMessages([
            {
              role: "assistant",
              content: `Hey! I'm ${coach.name}, your ${coach.title.toLowerCase()}. Ask me anything about your health data — I'm here to help. 💪`,
              time: timeNow(),
            },
          ]);
        }
      })
      .catch(() => setNeedsOnboarding(false));
  }, [coach]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (text?: string) => {
    const msg = text || question;
    if (!msg.trim() || loading) return;
    setQuestion("");

    const userMsg: ChatMsg = { role: "user", content: msg, time: timeNow() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      if (needsOnboarding) {
        // Onboarding flow
        const newApiHistory = [
          ...onboardingHistory,
          { role: "user", content: msg },
        ];
        const result = await sendOnboardingMessage(msg, onboardingHistory);
        setOnboardingHistory([
          ...newApiHistory,
          { role: "assistant", content: result.reply },
        ]);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: result.reply, time: timeNow() },
        ]);
        if (result.complete) {
          setNeedsOnboarding(false);
          // Add a transition message
          setTimeout(() => {
            setMessages((prev) => [
              ...prev,
              {
                role: "assistant",
                content: `Profile saved! From now on, I'll remember everything about you. Go ahead — ask me anything about your health data.`,
                time: timeNow(),
              },
            ]);
          }, 1500);
        }
      } else {
        // Regular ask with coach
        const result = await askQuestion(msg.trim(), undefined, coach.id);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: result.answer || "Hmm, I couldn't find data for that. Try rephrasing?",
            time: timeNow(),
          },
        ]);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: err instanceof Error ? err.message : "Something went wrong.",
          time: timeNow(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    const recognition = new SR();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";
    recognition.onresult = (e: any) => {
      setQuestion(e.results[0][0].transcript);
      setIsListening(false);
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  };

  const speak = (text: string) => {
    speechSynthesis.cancel();
    speechSynthesis.speak(new SpeechSynthesisUtterance(text));
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      {/* Chat header — WhatsApp style */}
      <div
        className="flex items-center gap-3 px-4 py-3 border-b border-border"
        style={{ backgroundColor: `${coach.color}08` }}
      >
        <span className="text-3xl">{coach.avatar}</span>
        <div className="flex-1">
          <p className="font-heading font-semibold text-[#e0e0e0]">
            {coach.name}
          </p>
          <p className="text-xs text-[#888]">{coach.title}</p>
        </div>
        <button
          onClick={onChangeCoach}
          className="px-3 py-1.5 text-xs border border-border rounded-lg text-[#888] hover:text-[#e0e0e0] hover:border-brand/30 transition-colors"
        >
          Change Coach
        </button>
      </div>

      {/* Chat area — WhatsApp wallpaper style */}
      <div
        className="flex-1 overflow-y-auto px-4 py-4 space-y-3"
        style={{
          backgroundImage:
            "radial-gradient(circle at 20% 50%, rgba(79,195,247,0.03) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(171,71,188,0.03) 0%, transparent 50%)",
        }}
      >
        <AnimatePresence>
          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.2 }}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[75%] rounded-2xl px-4 py-2.5 relative ${
                  msg.role === "user"
                    ? "bg-brand/15 border border-brand/20 rounded-tr-sm"
                    : "bg-card border border-border rounded-tl-sm"
                }`}
              >
                {msg.role === "assistant" && (
                  <p
                    className="text-xs font-semibold mb-1"
                    style={{ color: coach.color }}
                  >
                    {coach.name}
                  </p>
                )}
                <p className="text-sm text-[#e0e0e0] leading-relaxed whitespace-pre-wrap">
                  {msg.content}
                </p>
                <div className="flex items-center justify-end gap-1.5 mt-1">
                  <span className="text-[10px] text-[#666]">{msg.time}</span>
                  {msg.role === "user" && (
                    <CheckCheck size={12} className="text-brand/60" />
                  )}
                  {msg.role === "assistant" && (
                    <button
                      onClick={() => speak(msg.content)}
                      className="text-[#555] hover:text-brand transition-colors ml-1"
                    >
                      <Volume2 size={11} />
                    </button>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {loading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex justify-start"
          >
            <div className="bg-card border border-border rounded-2xl rounded-tl-sm px-4 py-3">
              <p className="text-xs font-semibold mb-1" style={{ color: coach.color }}>
                {coach.name}
              </p>
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-[#888] rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-2 h-2 bg-[#888] rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <div className="w-2 h-2 bg-[#888] rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </motion.div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input bar — WhatsApp style */}
      <div className="flex items-center gap-2 px-3 py-3 border-t border-border bg-card">
        <button
          onClick={toggleListening}
          className={`p-2.5 rounded-full transition-colors ${
            isListening
              ? "bg-red-500/10 text-red-400"
              : "text-[#888] hover:text-[#e0e0e0] hover:bg-border/30"
          }`}
        >
          {isListening ? <MicOff size={20} /> : <Mic size={20} />}
        </button>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Type a message..."
          disabled={loading}
          className="flex-1 bg-dark border border-border rounded-full px-4 py-2.5 text-sm text-[#e0e0e0] placeholder-[#666] focus:outline-none focus:border-brand/40 transition-colors disabled:opacity-50"
        />
        <button
          onClick={() => handleSend()}
          disabled={loading || !question.trim()}
          className="p-2.5 bg-brand rounded-full text-dark hover:bg-brand/90 transition-colors disabled:opacity-50"
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────────────

export default function AskPage() {
  const [coaches, setCoaches] = useState<Coach[]>([]);
  const [selectedCoach, setSelectedCoach] = useState<Coach | null>(null);
  const [pageLoading, setPageLoading] = useState(true);

  useEffect(() => {
    // Check localStorage for previously selected coach
    const savedCoachId =
      typeof window !== "undefined" ? localStorage.getItem("selectedCoach") : null;

    getCoaches()
      .then((c) => {
        setCoaches(c);
        if (savedCoachId) {
          const saved = c.find((coach) => coach.id === savedCoachId);
          if (saved) setSelectedCoach(saved);
        }
      })
      .catch(() => {})
      .finally(() => setPageLoading(false));
  }, []);

  const handleSelectCoach = (coach: Coach) => {
    setSelectedCoach(coach);
    localStorage.setItem("selectedCoach", coach.id);
  };

  const handleChangeCoach = () => {
    setSelectedCoach(null);
    localStorage.removeItem("selectedCoach");
  };

  if (pageLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <LoadingSpinner size={48} />
      </div>
    );
  }

  if (!selectedCoach) {
    return <CoachPicker coaches={coaches} onSelect={handleSelectCoach} />;
  }

  return <CoachChat coach={selectedCoach} onChangeCoach={handleChangeCoach} />;
}
