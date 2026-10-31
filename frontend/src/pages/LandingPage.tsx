import {
  ArrowRight,
  BadgeCheck,
  BookOpenText,
  Bot,
  Database,
  MessageCircleMore,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Brand } from "../components/Brand";
import { api, type HealthResponse } from "../lib/api";

const milestones = [
  {
    id: "01",
    title: "工程底座",
    detail: "前后端、MySQL、管理员认证",
    status: "已完成",
    tone: "ready",
  },
  {
    id: "02",
    title: "知识入库",
    detail: "硅基流动 Embedding + Chroma",
    status: "已完成",
    tone: "ready",
  },
  {
    id: "03",
    title: "RAG 问答",
    detail: "DeepSeek 流式回答与引用",
    status: "已完成",
    tone: "ready",
  },
  {
    id: "04",
    title: "Agent 售后",
    detail: "订单工具、物流、人工转接",
    status: "下一里程碑",
    tone: "next",
  },
];

export function LandingPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthFailed, setHealthFailed] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .health()
      .then((result) => {
        if (active) setHealth(result);
      })
      .catch(() => {
        if (active) setHealthFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const serviceState = health?.database === "connected" ? "服务在线" : healthFailed ? "后端未连接" : "检查服务中";

  return (
    <div className="landing">
      <header className="landing-nav">
        <Brand />
        <nav className="landing-nav__links" aria-label="主导航">
          <a href="#capabilities">服务能力</a>
          <a href="#progress">工程进度</a>
        </nav>
        <div className="landing-nav__actions">
          <span className={`health-chip ${healthFailed ? "is-error" : ""}`}>
            <span className="health-chip__dot" />
            {serviceState}
          </span>
          <Link className="button button--small button--ghost" to="/admin/login">
            运营后台
            <ArrowRight size={15} />
          </Link>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero__copy">
            <div className="eyebrow-pill">
              <Sparkles size={14} />
              AI 售后已上线
            </div>
            <h1>
              每一次售后咨询，
              <span>都被认真回应。</span>
            </h1>
            <p className="hero__lede">
              面向电商售后场景的智能问答 Agent。先理解问题，再查订单与知识，
              最后给出有依据、可转人工的回答。
            </p>
            <div className="hero__actions">
              <Link className="button button--primary" to="/chat">
                开始咨询
                <ArrowRight size={16} />
              </Link>
              <Link className="button button--ghost" to="/admin/login">
                查看运营工作台
                <ArrowRight size={16} />
              </Link>
            </div>
            <ul className="trust-list">
              <li>
                <BadgeCheck size={16} />
                回答可追溯
              </li>
              <li>
                <ShieldCheck size={16} />
                高风险自动转人工
              </li>
              <li>
                <Database size={16} />
                业务数据留在 MySQL
              </li>
            </ul>
          </div>

          <div className="hero__visual" aria-label="客服界面预览">
            <div className="visual-orbit visual-orbit--one" />
            <div className="visual-orbit visual-orbit--two" />
            <div className="chat-preview">
              <div className="chat-preview__header">
                <div className="chat-avatar">
                  <Bot size={19} />
                </div>
                <div>
                  <strong>青禾售后助理</strong>
                  <span>
                    <i className="online-dot" />
                    AI 在线
                  </span>
                </div>
                <span className="chat-preview__badge">LIVE</span>
              </div>
              <div className="chat-preview__body">
                <div className="bubble bubble--user">我昨天收到的台灯有划痕，可以退换吗？</div>
                <div className="bubble bubble--assistant">
                  如果签收后十五天内出现非人为的质量问题，可以提交照片申请换货或退货；
                  确认为质量问题的，往返运费由商家承担。
                  <div className="citation-preview">
                    <BookOpenText size={15} />
                    <span>
                      <em>引用来源</em>
                      《青禾生活售后政策（2026 版）》· 质量问题处理
                    </span>
                  </div>
                </div>
              </div>
              <div className="chat-preview__footer">
                <span>AI 对话已上线 · 引用可追溯</span>
                <MessageCircleMore size={16} />
              </div>
            </div>
          </div>
        </section>

        <section className="capability-strip" id="capabilities">
          <div className="capability-strip__intro">
            <span className="eyebrow">DESIGNED FOR AFTER-SALES</span>
            <h2>不是只会聊天的机器人。</h2>
            <p>
              静态政策交给知识库，实时订单交给工具，拿不准的情况交给人。
            </p>
          </div>
          <div className="capability-list">
            <article>
              <span className="capability-list__index">01</span>
              <BookOpenText size={22} />
              <h3>有出处的回答</h3>
              <p>每次知识问答都保留命中的政策与 FAQ，方便用户与客服复核。</p>
            </article>
            <article>
              <span className="capability-list__index">02</span>
              <Database size={22} />
              <h3>业务系统联动</h3>
              <p>订单、物流和售后条件通过工具查询，而不是让模型猜。</p>
            </article>
            <article>
              <span className="capability-list__index">03</span>
              <ShieldCheck size={22} />
              <h3>人工兜底</h3>
              <p>超出范围、低置信度或高风险请求会生成工单并交给运营处理。</p>
            </article>
          </div>
        </section>

        <section className="milestone-section" id="progress">
          <div className="section-heading">
            <span className="eyebrow">BUILD IN PUBLIC</span>
            <h2>工程正在一页一页地长出来。</h2>
            <p>每个里程碑都有可运行的功能、验收记录和开发日志，而不是一次性交出的黑盒。</p>
          </div>
          <div className="milestone-grid">
            {milestones.map((item) => (
              <article className={`milestone-card milestone-card--${item.tone}`} key={item.id}>
                <span className="milestone-card__number">{item.id}</span>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.detail}</p>
                </div>
                <span className="milestone-card__status">{item.status}</span>
              </article>
            ))}
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <Brand compact />
        <p>虚构店铺演示项目 · 仅用于 AI 应用学习与作品展示</p>
        <Link to="/admin/login">
          运营入口
          <ArrowRight size={14} />
        </Link>
      </footer>
    </div>
  );
}
