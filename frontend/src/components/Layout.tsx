import { NavLink, Outlet, useParams } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { CHANNELS, CHANNEL_LABELS, type Channel } from "../lib/api";

export default function Layout() {
  const { logout } = useAuth();
  const { channel } = useParams<{ channel: Channel }>();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h2>Romantik · Agent</h2>

        <div className="channel-switcher">
          {CHANNELS.map((ch) => (
            <NavLink
              key={ch}
              to={`/${ch}/conversations`}
              className={({ isActive }) =>
                `channel-tab ${ch === channel ? "active" : ""} ${isActive ? "active" : ""}`
              }
            >
              {CHANNEL_LABELS[ch]}
            </NavLink>
          ))}
        </div>

        <nav>
          <NavLink to={`/${channel}/conversations`} className={({ isActive }) => (isActive ? "active" : "")}>
            Переписки
          </NavLink>
          <NavLink to={`/${channel}/knowledge-base`} className={({ isActive }) => (isActive ? "active" : "")}>
            База знаний
          </NavLink>
          <NavLink to={`/${channel}/scenarios`} className={({ isActive }) => (isActive ? "active" : "")}>
            Сценарии
          </NavLink>
          <NavLink to={`/${channel}/settings`} className={({ isActive }) => (isActive ? "active" : "")}>
            Настройки
          </NavLink>
        </nav>
        <button className="logout-button" onClick={logout}>
          Выйти
        </button>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
