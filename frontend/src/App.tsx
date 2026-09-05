import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import ConversationsPage from "./pages/ConversationsPage";
import ScenariosPage from "./pages/ScenariosPage";
import SettingsPage from "./pages/SettingsPage";
import { CHANNELS } from "./lib/api";

function RequireAuth({ children }: { children: React.ReactElement }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

function RequireValidChannel({ children }: { children: React.ReactElement }) {
  const { channel } = useParams();
  if (!CHANNELS.includes(channel as (typeof CHANNELS)[number])) {
    return <Navigate to="/avito/conversations" replace />;
  }
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/:channel"
        element={
          <RequireAuth>
            <RequireValidChannel>
              <Layout />
            </RequireValidChannel>
          </RequireAuth>
        }
      >
        <Route path="knowledge-base" element={<KnowledgeBasePage />} />
        <Route path="conversations" element={<ConversationsPage />} />
        <Route path="scenarios" element={<ScenariosPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route index element={<Navigate to="conversations" replace />} />
      </Route>
      <Route path="/" element={<Navigate to="/avito/conversations" replace />} />
      <Route path="*" element={<Navigate to="/avito/conversations" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

export default App;
