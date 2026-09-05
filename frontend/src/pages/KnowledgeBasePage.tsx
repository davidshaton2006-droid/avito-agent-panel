import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type Channel, type KnowledgeBaseEntry } from "../lib/api";

export default function KnowledgeBasePage() {
  const { channel } = useParams<{ channel: Channel }>();
  const [entries, setEntries] = useState<KnowledgeBaseEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newQuestion, setNewQuestion] = useState("");
  const [newAnswer, setNewAnswer] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editQuestion, setEditQuestion] = useState("");
  const [editAnswer, setEditAnswer] = useState("");

  async function load() {
    if (!channel) return;
    setLoading(true);
    try {
      const data = await api.listKnowledgeBase(channel);
      setEntries(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channel]);

  async function handleAdd() {
    if (!channel || !newQuestion.trim() || !newAnswer.trim()) return;
    await api.createKnowledgeBaseEntry(channel, newQuestion.trim(), newAnswer.trim());
    setNewQuestion("");
    setNewAnswer("");
    load();
  }

  function startEdit(entry: KnowledgeBaseEntry) {
    setEditingId(entry.id);
    setEditQuestion(entry.question);
    setEditAnswer(entry.answer);
  }

  async function saveEdit(id: string) {
    if (!channel) return;
    await api.updateKnowledgeBaseEntry(channel, id, editQuestion.trim(), editAnswer.trim());
    setEditingId(null);
    load();
  }

  async function remove(id: string) {
    if (!channel || !confirm("Удалить эту пару вопрос-ответ?")) return;
    await api.deleteKnowledgeBaseEntry(channel, id);
    load();
  }

  return (
    <div className="page">
      <h1>База знаний</h1>
      <p className="hint">
        Эти пары вопрос-ответ дополняют системный промпт агента и помогают ему точнее отвечать гостям.
      </p>

      <div className="card">
        <h3>Добавить пару</h3>
        <input
          placeholder="Вопрос"
          value={newQuestion}
          onChange={(e) => setNewQuestion(e.target.value)}
        />
        <textarea
          placeholder="Ответ"
          value={newAnswer}
          onChange={(e) => setNewAnswer(e.target.value)}
          rows={3}
        />
        <button onClick={handleAdd}>Добавить</button>
      </div>

      {loading && <p>Загрузка…</p>}
      {error && <p className="error-text">{error}</p>}

      <div className="kb-list">
        {entries.map((entry) => (
          <div className="card" key={entry.id}>
            {editingId === entry.id ? (
              <>
                <input value={editQuestion} onChange={(e) => setEditQuestion(e.target.value)} />
                <textarea value={editAnswer} onChange={(e) => setEditAnswer(e.target.value)} rows={3} />
                <div className="row-actions">
                  <button onClick={() => saveEdit(entry.id)}>Сохранить</button>
                  <button className="secondary" onClick={() => setEditingId(null)}>
                    Отмена
                  </button>
                </div>
              </>
            ) : (
              <>
                <strong>{entry.question}</strong>
                <p>{entry.answer}</p>
                <div className="row-actions">
                  <button onClick={() => startEdit(entry)}>Изменить</button>
                  <button className="danger" onClick={() => remove(entry.id)}>
                    Удалить
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
