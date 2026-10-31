import {
  BookOpenText,
  LayoutDashboard,
  LogOut,
  MessagesSquare,
  Package,
  Sparkles,
} from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { Brand } from "./Brand";

const navClassName = ({ isActive }: { isActive: boolean }) =>
  isActive ? "admin-nav__link is-active" : "admin-nav__link";

export function AdminLayout() {
  const { admin, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/admin/login", { replace: true });
  };

  const initials = admin?.display_name.trim().slice(0, 1) || "禾";

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-sidebar__brand">
          <Brand to="/admin" />
        </div>

        <div className="admin-sidebar__label">
          <span>运营工作台</span>
          <small>演示店铺 · 虚构数据</small>
        </div>

        <nav className="admin-nav" aria-label="后台导航">
          <NavLink to="/admin" end className={navClassName}>
            <LayoutDashboard size={18} />
            <span>运营概览</span>
          </NavLink>
          <NavLink to="/admin/orders" className={navClassName}>
            <Package size={18} />
            <span>订单台账</span>
          </NavLink>
          <button className="admin-nav__link" type="button" disabled>
            <BookOpenText size={18} />
            <span>知识库</span>
            <em>M2</em>
          </button>
          <button className="admin-nav__link" type="button" disabled>
            <MessagesSquare size={18} />
            <span>会话中心</span>
            <em>M3</em>
          </button>
        </nav>

        <div className="milestone-note">
          <div className="milestone-note__icon">
            <Sparkles size={16} />
          </div>
          <span className="eyebrow">MILESTONE 01</span>
          <strong>工程底座已就位</strong>
          <p>数据层、管理员认证和运营入口已经完成。</p>
        </div>

        <div className="admin-account">
          <div className="avatar" aria-hidden="true">
            {initials}
          </div>
          <div className="admin-account__identity">
            <strong>{admin?.display_name}</strong>
            <span>{admin?.email}</span>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={handleLogout}
            aria-label="退出登录"
            title="退出登录"
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>

      <div className="admin-main">
        <header className="admin-topbar">
          <div className="admin-topbar__mobile-brand">
            <Brand to="/admin" compact />
          </div>
          <span className="environment-pill">
            <span className="environment-pill__dot" />
            本地演示环境
          </span>
          <a className="text-link" href="/">
            查看消费者端
          </a>
        </header>
        <main className="admin-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
