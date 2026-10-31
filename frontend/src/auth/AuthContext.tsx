import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, ApiError, type Admin } from "../lib/api";

type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthContextValue {
  admin: Admin | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<Admin | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let active = true;

    api
      .me()
      .then((currentAdmin) => {
        if (!active) return;
        setAdmin(currentAdmin);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (!(error instanceof ApiError) || error.status !== 401) {
          console.warn("无法确认登录状态", error);
        }
        setAdmin(null);
        setStatus("anonymous");
      });

    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await api.login(email, password);
    setAdmin(response.admin);
    setStatus("authenticated");
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setAdmin(null);
      setStatus("anonymous");
    }
  }, []);

  const value = useMemo(
    () => ({ admin, status, login, logout }),
    [admin, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth 必须在 AuthProvider 内使用");
  }
  return context;
}
