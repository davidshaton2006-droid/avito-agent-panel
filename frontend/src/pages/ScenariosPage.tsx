import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type Channel, type Scenario } from "../lib/api";

const STEP_LABELS: Record<Scenario["steps"][number]["type"], string> = {
  message: "Сообщение гостю",
  wait_photo: "Ждём фото от гостя",
  wait_text: "Ждём текст от гостя",
  notify_admin: "Уведомление администратору",
};

export default function ScenariosPage() {
  const { channel } = useParams<{ channel: Channel }>();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [drafts, setDrafts] = useState<Record<string, Scenario>>({});
  const [savingId, setSavingId] = useState<string | null>(null);

  async function load() {
    if (!channel) return;
    setLoading(true);
    const data = await api.listScenarios(channel);
    setScenarios(data);
    setDrafts(Object.fromEntries(data.map((s) => [s.id, s])));
    setLoading(false);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channel]);

  function updateDraft(id: string, updater: (s: Scenario) => Scenario) {
    setDrafts((prev) => ({ ...prev, [id]: updater(prev[id]) }));
  }

  async function toggle(id: string) {
    if (!channel) return;
    const updated = await api.toggleScenario(channel, id);
    setScenarios((prev) => prev.map((s) => (s.id === id ? updated : s)));
    setDrafts((prev) => ({ ...prev, [id]: updated }));
  }

  async function save(id: string) {
    if (!channel) return;
    setSavingId(id);
    try {
      const draft = drafts[id];
      const updated = await api.updateScenario(channel, id, draft);
      setScenarios((prev) => prev.map((s) => (s.id === id ? updated : s)));
      setDrafts((prev) => ({ ...prev, [id]: updated }));
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="page">
      <h1>Сценарии</h1>
      <p className="hint">
        Пошаговые диалоги, которые запускаются точным словом-триггером (например «оплатил»). Тексты шагов и
        включение/выключение можно менять здесь без правки кода.
      </p>

      {loading && <p>Загрузка…</p>}

      {scenarios.map((scenario) => {
        const draft = drafts[scenario.id] || scenario;
        return (
          <div className="card scenario-card" key={scenario.id}>
            <div className="scenario-header">
              <div>
                <h3>{draft.name || draft.scenarioId}</h3>
                <label className="inline-field">
                  Триггер (точное совпадение сообщения гостя):
                  <input
                    value={draft.triggerKeyword}
                    onChange={(e) =>
                      updateDraft(scenario.id, (s) => ({ ...s, triggerKeyword: e.target.value }))
                    }
                  />
                </label>
              </div>
              <label className="toggle-field">
                <input
                  type="checkbox"
                  checked={draft.isActive}
                  onChange={() => toggle(scenario.id)}
                />
                {draft.isActive ? "Включён" : "Выключен"}
              </label>
            </div>

            <ol className="scenario-steps">
              {draft.steps.map((step, index) => (
                <li key={index}>
                  <span className="step-type">{STEP_LABELS[step.type]}</span>
                  {(step.type === "message" || step.type === "notify_admin") && step.type === "message" && (
                    <textarea
                      value={step.text || ""}
                      rows={2}
                      onChange={(e) =>
                        updateDraft(scenario.id, (s) => {
                          const steps = [...s.steps];
                          steps[index] = { ...steps[index], text: e.target.value };
                          return { ...s, steps };
                        })
                      }
                    />
                  )}
                  {step.saveToField && <small>сохраняется в поле: {step.saveToField}</small>}
                </li>
              ))}
            </ol>

            <button onClick={() => save(scenario.id)} disabled={savingId === scenario.id}>
              {savingId === scenario.id ? "Сохранение…" : "Сохранить тексты"}
            </button>
          </div>
        );
      })}

      {!loading && scenarios.length === 0 && (
        <p className="hint">
          Сценариев пока нет — запустите backend/scripts/seed_scenarios.py, чтобы создать стартовый сценарий
          «ОПЛАТИЛ».
        </p>
      )}
    </div>
  );
}
