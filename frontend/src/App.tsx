import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage";
import ConversationsPage from "./pages/ConversationsPage";
import ScenariosPage from "./pages/ScenariosPage";

function RequireAuth({ children }: { children: React.ReactElement }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
        <Route path="/conversations" element={<ConversationsPage />} />
        <Route path="/scenarios" element={<ScenariosPage />} />
        <Route path="/" element={<Navigate to="/conversations" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
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
