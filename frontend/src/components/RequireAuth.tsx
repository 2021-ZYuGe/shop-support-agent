import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { admin, status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div className="screen-loader" role="status">
        <span className="screen-loader__pulse" />
        <p>正在确认登录状态…</p>
      </div>
    );
  }

  if (admin === null) {
    return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
