"use client";

import { BookOpenText, Menu, RotateCcw, Send, Square, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { EvidencePanel } from "@/components/evidence-panel";
import { MessageBubble } from "@/components/message-bubble";
import { SessionList } from "@/components/session-list";
import { WorkspaceNav } from "@/components/workspace-nav";
import { extractCitations } from "@/lib/chat-utils";
import { deleteSession, getChatHistory, listSessions, streamChatMessage } from "@/services/api";
import { AgentTrace, ChatResponse, ChatSessionSummary, ConversationTurn } from "@/types/chat";

type StreamingAssistantState = { text: string; sessionId?: string };

export default function HomePage() {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [history, setHistory] = useState<ConversationTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [streamingAssistant, setStreamingAssistant] = useState<StreamingAssistantState | null>(null);
  const [completedResponse, setCompletedResponse] = useState<ChatResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("Ready");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [lastMessage, setLastMessage] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messageEndRef = useRef<HTMLDivElement | null>(null);

  // Session bootstrap intentionally runs once; later refreshes preserve the active session.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void refreshSessions(true); }, []);
  useEffect(() => { messageEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [history, streamingAssistant]);

  async function refreshSessions(selectFirst = false) {
    try {
      const data = await listSessions();
      setSessions(data.sessions);
      if (selectFirst && !activeSessionId && data.sessions.length > 0) await loadSession(data.sessions[0].session_id);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load conversations.");
    }
  }

  async function loadSession(sessionId: string) {
    try {
      setStatusMessage("Loading history");
      const data = await getChatHistory(sessionId);
      setActiveSessionId(sessionId);
      setHistory(data.history);
      setCompletedResponse(null);
      setStreamingAssistant(null);
      setSidebarOpen(false);
      setStatusMessage("Ready");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to load history.");
    }
  }

  function resetSession() {
    abortRef.current?.abort();
    setActiveSessionId(null);
    setHistory([]);
    setCompletedResponse(null);
    setStreamingAssistant(null);
    setDraft("");
    setErrorMessage(null);
    setStatusMessage("Ready");
    setSidebarOpen(false);
  }

  async function handleDeleteSession(sessionId: string) {
    try {
      await deleteSession(sessionId);
      if (activeSessionId === sessionId) resetSession();
      await refreshSessions();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to delete conversation.");
    }
  }

  async function sendMessage(message: string) {
    if (!message || streamingAssistant) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setLastMessage(message);
    setDraft("");
    setErrorMessage(null);
    setCompletedResponse(null);
    setHistory((previous) => [...previous, { role: "user", message, created_at: new Date().toISOString() }]);
    setStreamingAssistant({ text: "" });
    setStatusMessage("Connecting");

    try {
      await streamChatMessage({ message, session_id: activeSessionId }, (payload) => {
        if (payload.event === "session_started") {
          setActiveSessionId(payload.data.session_id);
          setStreamingAssistant((previous) => ({ text: previous?.text ?? "", sessionId: payload.data.session_id }));
        } else if (payload.event === "status") {
          setStatusMessage(payload.data.stage ?? payload.data.message);
        } else if (payload.event === "message_delta") {
          setStreamingAssistant((previous) => ({
            text: `${previous?.text ?? ""}${payload.data.delta}`,
            sessionId: payload.data.session_id,
          }));
        } else if (payload.event === "message_completed") {
          setCompletedResponse(payload.data);
          setHistory(payload.data.history);
          setActiveSessionId(payload.data.session_id);
          setStreamingAssistant(null);
          setStatusMessage(payload.data.response.trace?.stream_mode === "token" ? "Token stream complete" : "Response complete");
          void refreshSessions();
        } else if (payload.event === "error") {
          throw new Error(payload.data.message);
        }
      }, controller.signal);
    } catch (error) {
      setStreamingAssistant(null);
      if (error instanceof DOMException && error.name === "AbortError") {
        setStatusMessage("Generation stopped");
      } else {
        setErrorMessage(error instanceof Error ? error.message : "Request failed.");
        setStatusMessage("Failed");
      }
    } finally {
      abortRef.current = null;
    }
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(draft.trim());
  }

  function stopStreaming() {
    abortRef.current?.abort();
  }

  const assistantPreview = streamingAssistant
    ? { role: "assistant" as const, message: streamingAssistant.text, created_at: new Date().toISOString() }
    : null;
  const trace: AgentTrace | null = completedResponse?.response.trace ?? null;

  return (
    <div className="app-frame">
      <WorkspaceNav />
      <div className="sheet-backdrop" data-open={sidebarOpen} onClick={() => setSidebarOpen(false)} />
      <div className="chat-shell">
        <aside className="session-sidebar" data-open={sidebarOpen}>
          <button className="sidebar-close" type="button" title="Close" onClick={() => setSidebarOpen(false)}><X size={17} /></button>
          <SessionList sessions={sessions} activeSessionId={activeSessionId} onSelect={loadSession} onDelete={handleDeleteSession} onNewSession={resetSession} />
        </aside>
        <main className="chat-workspace">
          <header className="workspace-header">
            <button className="icon-button mobile-only" type="button" title="Conversations" onClick={() => setSidebarOpen(true)}><Menu size={18} /></button>
            <div><span>F1 operations assistant</span><h1>{activeSessionId ? sessions.find((s) => s.session_id === activeSessionId)?.title ?? "Conversation" : "New conversation"}</h1></div>
            <div className="request-state"><i data-error={!!errorMessage} />{errorMessage ?? statusMessage}</div>
            <button className="header-icon mobile-only" type="button" title="Evidence" onClick={() => setEvidenceOpen(true)}><BookOpenText size={17} /></button>
          </header>
          <div className="chat-grid">
            <section className="conversation-column">
              <div className="chat-messages">
                {history.length === 0 && !assistantPreview ? (
                  <div className="empty-chat"><strong>Ask the pit wall</strong><span>Race data, FIA clauses, news, or strategy.</span></div>
                ) : null}
                {history.map((turn, index) => <MessageBubble key={`${turn.created_at}-${index}`} turn={turn} />)}
                {assistantPreview ? <MessageBubble turn={assistantPreview} pending /> : null}
                <div ref={messageEndRef} />
              </div>
              <form className="composer" onSubmit={handleSubmit}>
                <textarea
                  aria-label="Message"
                  placeholder="Ask about parc ferme, standings, or race strategy..."
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                />
                <div className="composer-footer">
                  <span>Ctrl + Enter</span>
                  <div className="composer-buttons">
                    {errorMessage && lastMessage ? <button className="secondary-button" type="button" onClick={() => void sendMessage(lastMessage)}><RotateCcw size={15} />Retry</button> : null}
                    {streamingAssistant ? (
                      <button className="stop-button" type="button" onClick={stopStreaming}><Square size={14} />Stop</button>
                    ) : (
                      <button className="primary-button" type="submit" disabled={!draft.trim()}><Send size={15} />Send</button>
                    )}
                  </div>
                </div>
              </form>
            </section>
            <EvidencePanel trace={trace} citations={extractCitations(completedResponse)} openOnMobile={evidenceOpen} onClose={() => setEvidenceOpen(false)} />
          </div>
        </main>
      </div>
    </div>
  );
}
