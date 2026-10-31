import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import { Brand } from "../components/Brand";

export function NotFoundPage() {
  return (
    <div className="not-found">
      <Brand />
      <span className="eyebrow">404 · LOST LEAF</span>
      <h1>这片叶子飘到了页面之外。</h1>
      <p>你访问的地址不存在，回到首页继续看看。</p>
      <Link className="button button--primary" to="/">
        <ArrowLeft size={16} />
        返回首页
      </Link>
    </div>
  );
}
