"use client";

import { Menu, Plus, RefreshCcw } from "lucide-react";
import { useEffect, useRef, useState, useTransition } from "react";

import { MessageBubble } from "@/components/message-bubble";
import { SessionList } from "@/components/session-list";
import {
  deleteSession,
  getChatHistory,
  listSessions,
  sendChatMessage,
  streamChatMessage,
} from "@/services/api";
import { ChatResponse, ChatSessionSummary, Citation, ConversationTurn } from "@/types/chat";

type StreamingAssistantState = {
  text: string;
  sessionId?: string;
};

function extractCitations(response: ChatResponse | null): Citation[] {
  if (!response) {
    return [];
  }

  const result = response.response.result as {
    response?: { citations?: Citation[] };
  };
  return result.response?.citations ?? [];
}

export default function HomePage() {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [history, setHistory] = useState<ConversationTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [streamingAssistant, setStreamingAssistant] = useState<StreamingAssistantState | null>(null);
  const [completedResponse, setCompletedResponse] = useState<ChatResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("等待输入。");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isPending, startTransition] = useTransition();
  const messageEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    startTransition(() => {
      refreshSessions();
    });
  }, []);

  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, streamingAssistant]);

  async function refreshSessions() {
    try {
      const data = await listSessions();
      setSessions(data.sessions);
      if (!activeSessionId && data.sessions.length > 0) {
        await loadSession(data.sessions[0].session_id);
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "加载会话失败。");
    }
  }

  async function loadSession(sessionId: string) {
    try {
      setStatusMessage("正在加载会话历史...");
      const data = await getChatHistory(sessionId);
      setActiveSessionId(sessionId);
      setHistory(data.history);
      setCompletedResponse(null);
      setStreamingAssistant(null);
      setSidebarOpen(false);
      setStatusMessage(`已载入 ${sessionId.slice(0, 12)}。`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "加载会话失败。");
    }
  }

  function resetSession() {
    setActiveSessionId(null);
    setHistory([]);
    setCompletedResponse(null);
    setStreamingAssistant(null);
    setDraft("");
    setErrorMessage(null);
    setStatusMessage("新会话已准备好。");
    setSidebarOpen(false);
  }

  async function handleDeleteSession(sessionId: string) {
    try {
      await deleteSession(sessionId);
      if (activeSessionId === sessionId) {
        resetSession();
      }
      await refreshSessions();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "删除会话失败。");
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const message = draft.trim();
    if (!message || isPending || streamingAssistant) {
      return;
    }

    const userTurn: ConversationTurn = {
      role: "user",
      message,
      created_at: new Date().toISOString(),
    };

    setDraft("");
    setErrorMessage(null);
    setCompletedResponse(null);
    setHistory((previous) => [...previous, userTurn]);
    setStreamingAssistant({ text: "" });
    setStatusMessage("正在等待 PitWall 响应...");

    try {
      await streamChatMessage(
        {
          message,
          session_id: activeSessionId,
        },
        (eventPayload) => {
          if (eventPayload.event === "session_started") {
            setActiveSessionId(eventPayload.data.session_id);
            setStreamingAssistant((previous) => ({
              text: previous?.text ?? "",
              sessionId: eventPayload.data.session_id,
            }));
          }

          if (eventPayload.event === "message_delta") {
            setStreamingAssistant((previous) => ({
              text: `${previous?.text ?? ""}${eventPayload.data.delta}`,
              sessionId: eventPayload.data.session_id,
            }));
          }

          if (eventPayload.event === "message_completed") {
            setCompletedResponse(eventPayload.data);
            setHistory(eventPayload.data.history);
            setActiveSessionId(eventPayload.data.session_id);
            setStreamingAssistant(null);
            setStatusMessage("响应完成。");
            startTransition(() => {
              refreshSessions();
            });
          }

          if (eventPayload.event === "error") {
            throw new Error(eventPayload.data.message);
          }
        },
      );
    } catch (error) {
      try {
        const fallback = await sendChatMessage({
          message,
          session_id: activeSessionId,
        });
        setCompletedResponse(fallback);
        setHistory(fallback.history);
        setActiveSessionId(fallback.session_id);
        setStreamingAssistant(null);
        setStatusMessage("已回退到同步接口。");
        startTransition(() => {
          refreshSessions();
        });
      } catch (fallbackError) {
        setStreamingAssistant(null);
        setErrorMessage(
          fallbackError instanceof Error
            ? fallbackError.message
            : error instanceof Error
              ? error.message
              : "发送消息失败。",
        );
        setStatusMessage("请求失败。");
      }
    }
  }

  const assistantPreview =
    streamingAssistant && streamingAssistant.text
      ? {
          role: "assistant" as const,
          message: streamingAssistant.text,
          created_at: new Date().toISOString(),
        }
      : null;

  return (
    <>
      <div className="sheet-backdrop" data-open={sidebarOpen} onClick={() => setSidebarOpen(false)} />
      <div className="pitwall-shell">
        <aside className="pitwall-sidebar" data-open={sidebarOpen}>
          <SessionList
            sessions={sessions}
            activeSessionId={activeSessionId}
            onSelect={loadSession}
            onDelete={handleDeleteSession}
            onNewSession={resetSession}
          />
        </aside>

        <main className="pitwall-main">
          <header className="pitwall-header">
            <div>
              <button
                className="menu-button mobile-session-toggle"
                type="button"
                onClick={() => setSidebarOpen(true)}
              >
                <Menu size={18} />
                会话
              </button>
              <h1 className="pitwall-title">PitWall Agent</h1>
              <p className="pitwall-subtitle">
                面向 Formula 1 的聊天前端，支持会话记忆、Markdown 输出、规则类 citation 和流式响应。
              </p>
            </div>
            <div className="sidebar-actions">
              <button className="ghost-button" type="button" onClick={resetSession}>
                <Plus size={16} style={{ verticalAlign: "middle", marginRight: 6 }} />
                新会话
              </button>
              <button
                className="ghost-button"
                type="button"
                disabled={isPending}
                onClick={() => startTransition(() => refreshSessions())}
              >
                <RefreshCcw size={16} style={{ verticalAlign: "middle", marginRight: 6 }} />
                刷新
              </button>
            </div>
          </header>

          <div className="pitwall-content">
            <section className="pitwall-card chat-panel">
              <div className="chat-messages">
                {history.length === 0 && !assistantPreview ? (
                  <div className="empty-state">
                    <div>
                      <h3 style={{ marginTop: 0 }}>从这里开始</h3>
                      <p>你可以直接问 PitWall：下一站比赛、积分榜、FIA 规则、或策略问题。</p>
                    </div>
                  </div>
                ) : null}

                {history.map((turn, index) => {
                  const isLastAssistant =
                    turn.role === "assistant" && index === history.length - 1 && completedResponse;
                  return (
                    <MessageBubble
                      key={`${turn.created_at}-${index}`}
                      turn={turn}
                      citations={isLastAssistant ? extractCitations(completedResponse) : []}
                    />
                  );
                })}

                {assistantPreview ? <MessageBubble turn={assistantPreview} pending /> : null}
                <div ref={messageEndRef} />
              </div>
            </section>

            <section className="pitwall-card composer">
              <form className="composer-form" onSubmit={handleSubmit}>
                <textarea
                  className="composer-input"
                  placeholder="例如：What is parc ferme? / Who leads the championship? / Should Ferrari pit under safety car?"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                />
                <div className="composer-actions">
                  <div className="status-line">{errorMessage ?? statusMessage}</div>
                  <button
                    className="primary-button"
                    type="submit"
                    disabled={isPending || !!streamingAssistant || !draft.trim()}
                  >
                    {streamingAssistant ? "Streaming..." : "发送"}
                  </button>
                </div>
              </form>
            </section>
          </div>
        </main>
      </div>
    </>
  );
}
