"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { ApiError, postChat } from "@/lib/api";

function renderInline(text: string, keyPrefix: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={`${keyPrefix}-${i}`}>{part.slice(2, -2)}</strong>
    ) : (
      <span key={`${keyPrefix}-${i}`}>{part}</span>
    ),
  );
}

function renderAnswer(content: string) {
  const lines = content.split("\n");
  return lines.map((line, i) => {
    const bullet = /^\s*-\s+(.*)/.exec(line);
    if (bullet) {
      return (
        <div key={i} style={{ display: "flex", gap: 6 }}>
          <span aria-hidden>·</span>
          <span>{renderInline(bullet[1], `l${i}`)}</span>
        </div>
      );
    }
    if (line.trim() === "") return <div key={i} style={{ height: 4 }} />;
    return <div key={i}>{renderInline(line, `l${i}`)}</div>;
  });
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  error?: boolean;
}

const SUGGESTED_QUESTIONS = [
  "관찰된 Gap이 가장 큰 국가는 어디인가요?",
  "동남아 국가들의 주요 방한 장벽은 무엇인가요?",
  "인지-행동 Gap과 조건부 Gap의 차이를 설명해주세요.",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  };

  const sendQuestion = async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setLoading(true);
    scrollToBottom();

    try {
      const res = await postChat(trimmed);
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer }]);
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "알 수 없는 오류가 발생했습니다.";
      setMessages((prev) => [...prev, { role: "assistant", content: message, error: true }]);
    } finally {
      setLoading(false);
      scrollToBottom();
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendQuestion(input);
  };

  return (
    <main
      style={{
        maxWidth: 860,
        margin: "0 auto",
        padding: "24px 24px 40px",
        display: "flex",
        flexDirection: "column",
        height: "100vh",
      }}
    >
      <header style={{ marginBottom: 16 }}>
        <Link
          href="/"
          style={{ fontSize: 12.5, color: "var(--text-secondary)", textDecoration: "none" }}
        >
          ← Overview로 돌아가기
        </Link>
        <p
          style={{
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.06em",
            color: "var(--accent-primary)",
            margin: "10px 0 6px",
            textTransform: "uppercase",
          }}
        >
          AI Analyst
        </p>
        <h1 style={{ fontSize: 22, margin: "0 0 6px" }}>데이터에게 직접 물어보세요</h1>
        <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0, maxWidth: 720 }}>
          정량 데이터를 근거로만 답변하는 챗봇입니다. 질문마다 독립적으로 답변하며, 이전 대화 맥락은 참고하지 않습니다.
        </p>
      </header>

      <div
        ref={scrollRef}
        className="card scroll-panel"
        style={{
          flex: 1,
          minHeight: 0,
          padding: 20,
          display: "flex",
          flexDirection: "column",
          gap: 14,
        }}
      >
        {messages.length === 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <p style={{ fontSize: 13, color: "var(--text-muted)", margin: 0 }}>
              이런 질문으로 시작해보세요
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => sendQuestion(q)}
                  style={{
                    textAlign: "left",
                    border: "1px solid var(--border-hairline)",
                    borderRadius: "var(--radius-md)",
                    background: "var(--card-bg-soft)",
                    padding: "10px 14px",
                    fontSize: 13,
                    color: "var(--text-primary)",
                    cursor: "pointer",
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "85%",
              display: "flex",
              flexDirection: "column",
              gap: 4,
            }}
          >
            <span
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "var(--text-muted)",
                textAlign: msg.role === "user" ? "right" : "left",
              }}
            >
              {msg.role === "user" ? "나" : "AI Analyst"}
            </span>
            <div
              style={{
                borderRadius: "var(--radius-md)",
                padding: "10px 14px",
                fontSize: 13.5,
                lineHeight: 1.6,
                whiteSpace: "pre-wrap",
                background:
                  msg.role === "user"
                    ? "var(--accent-primary)"
                    : msg.error
                      ? "rgba(211, 71, 71, 0.08)"
                      : "var(--card-bg-soft)",
                color:
                  msg.role === "user"
                    ? "#fff"
                    : msg.error
                      ? "#a13d3d"
                      : "var(--text-primary)",
                border: msg.role === "assistant" ? "1px solid var(--border-hairline)" : "none",
              }}
            >
              {msg.role === "assistant" && !msg.error ? renderAnswer(msg.content) : msg.content}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ alignSelf: "flex-start", display: "flex", alignItems: "center", gap: 8 }}>
            <div
              aria-hidden
              style={{
                width: 16,
                height: 16,
                borderRadius: "50%",
                border: "2px solid var(--accent-primary-soft)",
                borderTopColor: "var(--accent-primary)",
                animation: "spin 0.8s linear infinite",
              }}
            />
            <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>
              데이터를 분석하고 있습니다…
            </span>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", gap: 10, marginTop: 14 }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="질문을 입력하세요…"
          disabled={loading}
          style={{
            flex: 1,
            border: "1px solid var(--border-hairline)",
            borderRadius: 999,
            padding: "12px 18px",
            fontSize: 13.5,
            outline: "none",
            background: "var(--card-bg)",
            color: "var(--text-primary)",
          }}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            border: "none",
            borderRadius: 999,
            background: loading || !input.trim() ? "var(--baseline)" : "var(--accent-primary)",
            color: "#fff",
            padding: "0 24px",
            fontSize: 13.5,
            fontWeight: 600,
            cursor: loading || !input.trim() ? "default" : "pointer",
          }}
        >
          전송
        </button>
      </form>
    </main>
  );
}
