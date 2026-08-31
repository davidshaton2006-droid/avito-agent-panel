import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { api, clearToken, getToken, setToken } from "./api";

interface AuthContextValue {
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!getToken());

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated,
      login: async (username: string, password: string) => {
        const { token } = await api.login(username, password);
        setToken(token);
        setIsAuthenticated(true);
      },
      logout: () => {
        clearToken();
        setIsAuthenticated(false);
      },
    }),
    [isAuthenticated],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
