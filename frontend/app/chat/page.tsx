"use client";

import { useEffect, useRef, useState } from "react";
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
    const subheading = /^\s*###\s+(.*)/.exec(line);
    if (subheading) {
      return (
        <div
          key={i}
          style={{ fontSize: 14, fontWeight: 700, marginTop: i === 0 ? 0 : 10, marginBottom: 4 }}
        >
          {renderInline(subheading[1], `l${i}`)}
        </div>
      );
    }
    const heading = /^\s*##\s+(.*)/.exec(line);
    if (heading) {
      return (
        <div
          key={i}
          style={{ fontSize: 15.5, fontWeight: 700, marginTop: i === 0 ? 0 : 14, marginBottom: 4 }}
        >
          {renderInline(heading[1], `l${i}`)}
        </div>
      );
    }
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
  followUps?: string[];
}

interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
}

const SUGGESTED_QUESTIONS = [
  "한류 관심 대비 방한 의향이 낮은 국가는?",
  "동남아 국가들의 주요 방한 장벽은 무엇인가요?",
  "UAE와 일본 방한 전환 차이는 왜 발생할까?",
];

const STORAGE_KEY = "hallyu-chat-conversations";
const TITLE_MAX_LEN = 28;

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function makeTitle(question: string): string {
  const trimmed = question.trim();
  return trimmed.length > TITLE_MAX_LEN ? `${trimmed.slice(0, TITLE_MAX_LEN)}…` : trimmed;
}

function formatRelativeTime(timestamp: number): string {
  const diffMs = Date.now() - timestamp;
  const diffMin = Math.round(diffMs / 60000);
  if (diffMin < 1) return "방금 전";
  if (diffMin < 60) return `${diffMin}분 전`;
  const diffHour = Math.round(diffMin / 60);
  if (diffHour < 24) return `${diffHour}시간 전`;
  const diffDay = Math.round(diffHour / 24);
  return `${diffDay}일 전`;
}

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());
  const [hydrated, setHydrated] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 대화 목록은 이 브라우저(localStorage)에만 저장된다 - 서버에는 저장하지 않음.
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setConversations(JSON.parse(raw));
    } catch {
      // 저장된 값이 손상됐으면 그냥 빈 상태로 시작
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations, hydrated]);

  const activeMessages = conversations.find((c) => c.id === activeId)?.messages ?? [];
  const isActivePending = activeId !== null && pendingIds.has(activeId);

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  };

  const appendMessage = (conversationId: string, message: ChatMessage) => {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === conversationId
          ? { ...c, messages: [...c.messages, message], updatedAt: Date.now() }
          : c,
      ),
    );
  };

  const sendQuestion = async (question: string) => {
    const trimmed = question.trim();
    // activeId가 null이면(새 대화) 아직 pendingIds에 있을 수 없으므로 항상 허용된다 -
    // 대화별로 독립적으로 로딩 상태를 추적해서, 한 대화가 응답을 기다리는 동안에도
    // 다른 대화(또는 새 대화)에서는 자유롭게 질문을 보낼 수 있다.
    if (!trimmed || (activeId !== null && pendingIds.has(activeId))) return;

    const history = activeMessages
      .filter((m) => !m.error)
      .map(({ role, content }) => ({ role, content }));

    let conversationId = activeId;
    if (!conversationId) {
      conversationId = makeId();
      const newConversation: Conversation = {
        id: conversationId,
        title: makeTitle(trimmed),
        messages: [],
        updatedAt: Date.now(),
      };
      setConversations((prev) => [newConversation, ...prev]);
      setActiveId(conversationId);
    }

    appendMessage(conversationId, { role: "user", content: trimmed });
    setInput("");
    setPendingIds((prev) => new Set(prev).add(conversationId!));
    scrollToBottom();

    try {
      const res = await postChat(trimmed, history);
      appendMessage(conversationId, {
        role: "assistant",
        content: res.answer,
        followUps: res.follow_up_questions,
      });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "알 수 없는 오류가 발생했습니다.";
      appendMessage(conversationId, { role: "assistant", content: message, error: true });
    } finally {
      setPendingIds((prev) => {
        const next = new Set(prev);
        next.delete(conversationId!);
        return next;
      });
      scrollToBottom();
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendQuestion(input);
  };

  const startNewChat = () => {
    setActiveId(null);
    setInput("");
  };

  const deleteConversation = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeId === id) setActiveId(null);
  };

  const sortedConversations = [...conversations].sort((a, b) => b.updatedAt - a.updatedAt);

  return (
    <main
      style={{
        maxWidth: 1140,
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
          AI Business Analyst
        </p>
        <h1 style={{ fontSize: 22, margin: "0 0 6px" }}>AI 애널리스트에게 직접 물어보세요</h1>
        <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: 0, maxWidth: 720 }}>
          직접 수집한 정량/정성 데이터를 근거로만 답변하는 AI챗봇입니다.
          <br />
          같은 대화창 안에서는 이전 질문 맥락을 기억하고, 대화 목록은 이 브라우저에 저장되어 나중에 다시 열어볼 수 있습니다.
        </p>
      </header>

      <div style={{ flex: 1, minHeight: 0, display: "flex", gap: 16 }}>
        <aside
          className="card"
          style={{
            width: 220,
            flexShrink: 0,
            padding: 12,
            display: "flex",
            flexDirection: "column",
            gap: 10,
            overflowY: "auto",
          }}
        >
          <button
            onClick={startNewChat}
            style={{
              border: "1px solid var(--border-hairline)",
              borderRadius: "var(--radius-md)",
              background: activeId === null ? "var(--accent-primary)" : "var(--card-bg-soft)",
              color: activeId === null ? "#fff" : "var(--text-primary)",
              padding: "9px 12px",
              fontSize: 12.5,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            + 새 대화
          </button>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {sortedConversations.length === 0 && (
              <p style={{ fontSize: 11.5, color: "var(--text-muted)", margin: "4px 2px" }}>
                저장된 대화가 없습니다
              </p>
            )}
            {sortedConversations.map((c) => (
              <div
                key={c.id}
                onClick={() => setActiveId(c.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 6,
                  borderRadius: "var(--radius-md)",
                  padding: "8px 10px",
                  cursor: "pointer",
                  background: c.id === activeId ? "var(--card-bg-soft)" : "transparent",
                  border:
                    c.id === activeId
                      ? "1px solid var(--accent-primary-soft)"
                      : "1px solid transparent",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 12.5,
                      color: "var(--text-primary)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {c.title}
                  </div>
                  <div style={{ fontSize: 10.5, color: "var(--text-muted)" }}>
                    {formatRelativeTime(c.updatedAt)}
                  </div>
                </div>
                <button
                  onClick={(e) => deleteConversation(c.id, e)}
                  title="대화 삭제"
                  aria-label="대화 삭제"
                  style={{
                    border: "none",
                    background: "transparent",
                    color: "var(--text-muted)",
                    fontSize: 13,
                    cursor: "pointer",
                    padding: "2px 4px",
                    flexShrink: 0,
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </aside>

        <div
          style={{
            flex: 1,
            minWidth: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
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
            {activeMessages.length === 0 && (
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

            {activeMessages.map((msg, i) => (
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

                {msg.role === "assistant" &&
                  !msg.error &&
                  i === activeMessages.length - 1 &&
                  !!msg.followUps?.length && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 2 }}>
                      {msg.followUps.map((q) => (
                        <button
                          key={q}
                          onClick={() => sendQuestion(q)}
                          disabled={isActivePending}
                          style={{
                            textAlign: "left",
                            border: "1px solid var(--accent-primary-soft)",
                            borderRadius: "var(--radius-md)",
                            background: "transparent",
                            padding: "8px 12px",
                            fontSize: 12.5,
                            color: "var(--accent-primary)",
                            cursor: isActivePending ? "default" : "pointer",
                            opacity: isActivePending ? 0.5 : 1,
                          }}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  )}
              </div>
            ))}

            {isActivePending && (
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

          <form onSubmit={handleSubmit} style={{ display: "flex", gap: 10, marginTop: 14 }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={activeMessages.length === 0 ? "어느 나라를 분석해볼까요?🔍" : ""}
              disabled={isActivePending}
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
              disabled={isActivePending || !input.trim()}
              style={{
                border: "none",
                borderRadius: 999,
                background:
                  isActivePending || !input.trim() ? "var(--baseline)" : "var(--accent-primary)",
                color: "#fff",
                padding: "0 24px",
                fontSize: 13.5,
                fontWeight: 600,
                cursor: isActivePending || !input.trim() ? "default" : "pointer",
              }}
            >
              전송
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
