import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type AgentSettings, type Channel } from "../lib/api";

export default function SettingsPage() {
  const { channel } = useParams<{ channel: Channel }>();
  const [settings, setSettings] = useState<AgentSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!channel) return;
    setLoading(true);
    try {
      const data = await api.getSettings(channel);
      setSettings(data);
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

  async function save() {
    if (!channel || !settings) return;
    setSaving(true);
    try {
      const updated = await api.updateSettings(channel, settings);
      setSettings(updated);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive() {
    if (!channel || !settings) return;
    const updated = await api.updateSettings(channel, { isActive: !settings.isActive });
    setSettings(updated);
  }

  if (loading) return <div className="page">Загрузка…</div>;
  if (error) return <div className="page error-text">{error}</div>;
  if (!settings) return null;

  return (
    <div className="page">
      <h1>Настройки агента</h1>
      <p className="hint">
        Профиль и база знаний агента для этого канала. Те же настройки можно менять через Telegram-бота.
      </p>

      <div className="card">
        <label className="toggle-field">
          <input type="checkbox" checked={settings.isActive} onChange={toggleActive} />
          {settings.isActive ? "Агент включён" : "Агент на паузе"}
        </label>
      </div>

      <div className="card">
        <h3>Профиль</h3>
        <label className="inline-field">
          Имя
          <input
            value={settings.name}
            onChange={(e) => setSettings({ ...settings, name: e.target.value })}
          />
        </label>
        <label className="inline-field">
          Компания
          <input
            value={settings.company}
            onChange={(e) => setSettings({ ...settings, company: e.target.value })}
          />
        </label>
        <label className="inline-field">
          Товары/услуги
          <textarea
            rows={2}
            value={settings.products}
            onChange={(e) => setSettings({ ...settings, products: e.target.value })}
          />
        </label>
        <label className="inline-field">
          Цель общения
          <textarea
            rows={2}
            value={settings.goal}
            onChange={(e) => setSettings({ ...settings, goal: e.target.value })}
          />
        </label>
      </div>

      <div className="card">
        <h3>База знаний (свободный текст)</h3>
        <textarea
          rows={10}
          placeholder="Любой текст с фактами о бизнесе — агент использует его как дополнительный контекст."
          value={settings.knowledgeBaseText}
          onChange={(e) => setSettings({ ...settings, knowledgeBaseText: e.target.value })}
        />
      </div>

      <button onClick={save} disabled={saving}>
        {saving ? "Сохранение…" : "Сохранить"}
      </button>
    </div>
  );
}
