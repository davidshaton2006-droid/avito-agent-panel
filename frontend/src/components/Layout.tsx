import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth";

export default function Layout() {
  const { logout } = useAuth();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h2>Romantik · Avito Agent</h2>
        <nav>
          <NavLink to="/knowledge-base" className={({ isActive }) => (isActive ? "active" : "")}>
            База знаний
          </NavLink>
          <NavLink to="/conversations" className={({ isActive }) => (isActive ? "active" : "")}>
            Переписки
          </NavLink>
          <NavLink to="/scenarios" className={({ isActive }) => (isActive ? "active" : "")}>
            Сценарии
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
