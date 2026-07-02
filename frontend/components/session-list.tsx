"use client";

import { ChatSessionSummary } from "@/types/chat";

type SessionListProps = {
  sessions: ChatSessionSummary[];
  activeSessionId?: string | null;
  onSelect: (sessionId: string) => void;
  onDelete: (sessionId: string) => void;
  onNewSession: () => void;
};

export function SessionList({
  sessions,
  activeSessionId,
  onSelect,
  onDelete,
  onNewSession,
}: SessionListProps) {
  return (
    <>
      <div>
        <h2 style={{ margin: 0 }}>会话</h2>
        <p className="pitwall-subtitle" style={{ marginTop: 6 }}>
          保留上下文的聊天历史，会自动继续追问。
        </p>
      </div>
      <div className="sidebar-actions">
        <button className="primary-button" type="button" onClick={onNewSession}>
          新建会话
        </button>
      </div>
      <div className="session-list">
        {sessions.length === 0 ? (
          <div className="empty-state">还没有会话，先发送第一条消息。</div>
        ) : (
          sessions.map((session) => (
            <div
              className="session-item"
              key={session.session_id}
              data-active={session.session_id === activeSessionId}
              onClick={() => onSelect(session.session_id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(session.session_id);
                }
              }}
              role="button"
              tabIndex={0}
            >
              <div className="session-item-title">{session.session_id.slice(0, 12)}</div>
              <div className="session-item-meta">
                {session.turn_count} turns
                {session.last_intent ? ` · ${session.last_intent}` : ""}
              </div>
              <div className="session-item-meta">
                {new Date(session.updated_at).toLocaleString("zh-CN")}
              </div>
              <div style={{ marginTop: 10 }}>
                <button
                  className="danger-button"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDelete(session.session_id);
                  }}
                >
                  删除
                </button>
              </div>
            </div>
          ))
        )}
      </div>
      <div className="sidebar-footer">
        当前界面覆盖 Phase 6 的聊天主流程、Markdown、citation 和响应式布局。
      </div>
    </>
  );
}
