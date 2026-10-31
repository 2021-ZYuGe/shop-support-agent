import { ArrowLeft, Eye, EyeOff, LogIn, ShieldCheck, Sparkles } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { Brand } from "../components/Brand";
import { ApiError } from "../lib/api";

const DEMO_EMAIL = "admin@qinghe.local";
const DEMO_PASSWORD = "ChangeMe123!";

export function LoginPage() {
  const { admin, status, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from ?? "/admin";

  if (status === "loading") {
    return (
      <div className="screen-loader" role="status">
        <span className="screen-loader__pulse" />
        <p>正在加载运营后台…</p>
      </div>
    );
  }

  if (admin !== null) {
    return <Navigate to={from} replace />;
  }

  const fillDemoAccount = () => {
    setEmail(DEMO_EMAIL);
    setPassword(DEMO_PASSWORD);
    setError(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (submitError) {
      setError(
        submitError instanceof ApiError
          ? submitError.message
          : "登录失败，请检查后端服务是否已启动",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <aside className="login-story">
        <div className="login-story__top">
          <Brand to="/" />
          <Link className="back-link" to="/">
            <ArrowLeft size={15} />
            返回首页
          </Link>
        </div>
        <div className="login-story__content">
          <span className="eyebrow eyebrow--light">OPERATIONS CONSOLE</span>
          <h1>让客服看见 AI 每一步是怎么想的。</h1>
          <p>
            这里不是只有一个聊天窗口。运营人员可以看到订单上下文、知识引用、
            工具调用轨迹和需要人工接手的会话。
          </p>
          <ul>
            <li>
              <ShieldCheck size={17} />
              管理员会话保存在数据库，可服务端失效
            </li>
            <li>
              <Sparkles size={17} />
              当前 M1：数据底座与运营入口
            </li>
          </ul>
        </div>
        <div className="login-story__art" aria-hidden="true">
          <span className="art-ring art-ring--one" />
          <span className="art-ring art-ring--two" />
          <span className="art-leaf art-leaf--one" />
          <span className="art-leaf art-leaf--two" />
        </div>
        <p className="login-story__footnote">青禾生活 · 虚构电商售后实验室</p>
      </aside>

      <main className="login-panel">
        <div className="login-card">
          <span className="eyebrow">WELCOME BACK</span>
          <h2>登录运营后台</h2>
          <p className="login-card__intro">使用管理员账号查看店铺数据与售后工作台。</p>

          <form onSubmit={handleSubmit} className="form-stack">
            <label className="field">
              <span>邮箱</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="admin@qinghe.local"
                autoComplete="username"
                required
              />
            </label>
            <label className="field">
              <span>密码</span>
              <div className="password-field">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="输入管理员密码"
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="password-field__toggle"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "隐藏密码" : "显示密码"}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </label>

            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}

            <button className="button button--primary button--full" type="submit" disabled={submitting}>
              {submitting ? "正在登录…" : "进入工作台"}
              {!submitting && <LogIn size={17} />}
            </button>
          </form>

          <div className="demo-credentials">
            <div>
              <span>演示账号</span>
              <code>{DEMO_EMAIL}</code>
              <code>{DEMO_PASSWORD}</code>
            </div>
            <button type="button" className="text-button" onClick={fillDemoAccount}>
              一键填入
            </button>
          </div>

          <p className="login-card__note">
            演示账号来自本地种子数据；正式使用时请在 <code>.env</code> 中修改初始密码。
          </p>
        </div>
      </main>
    </div>
  );
}
