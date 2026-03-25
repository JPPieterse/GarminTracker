"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import type { User } from "./types";
import { getMe, getAuthConfig } from "./api";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  login: async () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const me = await getMe();
      setUser(me);
    } catch {
      localStorage.removeItem("token");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = useCallback(async () => {
    try {
      const config = await getAuthConfig();
      if (!config.configured) {
        // Dev mode: set a dev token and load user
        localStorage.setItem("token", "dev-token");
        const me = await getMe();
        setUser(me);
        return;
      }
      // Redirect to Auth0
      const params = new URLSearchParams({
        response_type: "token",
        client_id: config.client_id!,
        redirect_uri: `${window.location.origin}/callback`,
        audience: config.audience!,
        scope: "openid profile email",
      });
      window.location.href = `https://${config.domain}/authorize?${params}`;
    } catch (err) {
      console.error("Login failed:", err);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("token");
    setUser(null);
    window.location.href = "/";
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
