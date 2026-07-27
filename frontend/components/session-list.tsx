"use client";

import { MessageSquarePlus, Trash2 } from "lucide-react";

import { ChatSessionSummary } from "@/types/chat";

type SessionListProps = {
  sessions: ChatSessionSummary[];
  activeSessionId?: string | null;
  onSelect: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
  onNewSession: () => void;
};

export function SessionList({ sessions, activeSessionId, onSelect, onDelete, onNewSession }: SessionListProps) {
  return (
    <div className="session-sidebar-content">
      <div className="sidebar-heading">
        <div><span>Workspace</span><h2>Conversations</h2></div>
        <button className="icon-button" type="button" title="New conversation" onClick={onNewSession}>
          <MessageSquarePlus size={17} />
        </button>
      </div>
      <div className="session-list">
        {sessions.length === 0 ? <div className="panel-empty">No saved conversations.</div> : null}
        {sessions.map((session) => (
          <div className="session-item" data-active={session.session_id === activeSessionId} key={session.session_id}>
            <button className="session-select" type="button" onClick={() => onSelect(session.session_id)}>
              <strong>{session.title || session.session_id.slice(0, 12)}</strong>
              <span>{session.turn_count} turns{session.last_intent ? ` | ${session.last_intent}` : ""}</span>
              <small>{new Date(session.updated_at).toLocaleString("zh-CN")}</small>
            </button>
            <button className="session-delete" type="button" title="Delete conversation" onClick={() => onDelete(session.session_id)}>
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
