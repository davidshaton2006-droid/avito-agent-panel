import { useEffect, useState } from "react";
import { api, type Conversation } from "../lib/api";

const STATUS_LABELS: Record<Conversation["status"], string> = {
  open: "Открыт",
  escalated: "Требует внимания",
  closed: "Закрыт",
};

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);

  async function load() {
    setLoading(true);
    const data = await api.listConversations();
    setConversations(data);
    setLoading(false);
    if (!selectedId && data.length > 0) setSelectedId(data[0].id);
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selected = conversations.find((c) => c.id === selectedId) || null;

  async function handleSend() {
    if (!selected || !replyText.trim()) return;
    setSending(true);
    try {
      const updated = await api.sendAdminMessage(selected.id, replyText.trim());
      setReplyText("");
      setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    } finally {
      setSending(false);
    }
  }

  async function handleStatusChange(status: Conversation["status"]) {
    if (!selected) return;
    const updated = await api.setConversationStatus(selected.id, status);
    setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }

  return (
    <div className="page conversations-page">
      <h1>Переписки</h1>
      <div className="conversations-layout">
        <div className="conversation-list">
          {loading && <p>Загрузка…</p>}
          {conversations.map((c) => (
            <button
              key={c.id}
              className={`conversation-row ${c.id === selectedId ? "active" : ""} status-${c.status}`}
              onClick={() => setSelectedId(c.id)}
            >
              <strong>{c.guestName || c.chatId}</strong>
              <span className={`status-badge status-${c.status}`}>{STATUS_LABELS[c.status]}</span>
              <small>{c.messages[c.messages.length - 1]?.text?.slice(0, 60) || "—"}</small>
            </button>
          ))}
          {!loading && conversations.length === 0 && <p className="hint">Пока нет диалогов.</p>}
        </div>

        <div className="conversation-detail">
          {selected ? (
            <>
              <div className="conversation-header">
                <h2>{selected.guestName || selected.chatId}</h2>
                <select
                  value={selected.status}
                  onChange={(e) => handleStatusChange(e.target.value as Conversation["status"])}
                >
                  <option value="open">Открыт</option>
                  <option value="escalated">Требует внимания</option>
                  <option value="closed">Закрыт</option>
                </select>
              </div>

              <div className="message-list">
                {selected.messages.map((m, i) => (
                  <div key={i} className={`message-bubble role-${m.role}`}>
                    <span className="message-role">
                      {m.role === "guest" ? "Гость" : m.role === "agent" ? "Агент" : m.role === "admin" ? "Вы" : "Система"}
                    </span>
                    <p>{m.text}</p>
                    {m.imageUrl && (
                      <a href={m.imageUrl} target="_blank" rel="noreferrer">
                        📎 вложение
                      </a>
                    )}
                    <time>{new Date(m.timestamp).toLocaleString("ru-RU")}</time>
                  </div>
                ))}
              </div>

              <div className="reply-box">
                <textarea
                  placeholder="Ручное сообщение гостю (например, финальное подтверждение брони)…"
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  rows={2}
                />
                <button onClick={handleSend} disabled={sending || !replyText.trim()}>
                  {sending ? "Отправка…" : "Отправить"}
                </button>
              </div>
            </>
          ) : (
            <p className="hint">Выберите диалог слева.</p>
          )}
        </div>
      </div>
    </div>
  );
}
