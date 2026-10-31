from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.db.models import Conversation  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services import agent, knowledge, llm  # noqa: E402
from app.services.agent import AgentOptions  # noqa: E402

CASES_PATH = BACKEND_DIR / "evals" / "cases.json"
REPORT_PATH = PROJECT_ROOT / "docs" / "05-evaluation-report.md"
RAW_RESULTS_DIR = PROJECT_ROOT / "data" / "evaluation"


@dataclass(frozen=True)
class EvalConfig:
    key: str
    label: str
    options: AgentOptions


CONFIGS = {
    "baseline": EvalConfig(
        key="baseline",
        label="Baseline：vector Top-5 · threshold 0.40 · prompt v1",
        options=AgentOptions(
            top_k=5,
            min_similarity=0.40,
            use_rerank=False,
            rerank_candidates=12,
            prompt_version="v1",
        ),
    ),
    "prompt_v2": EvalConfig(
        key="prompt_v2",
        label="Prompt v2：vector Top-5 · threshold 0.40 · prompt v2",
        options=AgentOptions(
            top_k=5,
            min_similarity=0.40,
            use_rerank=False,
            rerank_candidates=12,
            prompt_version="v2",
        ),
    ),
    "optimized": EvalConfig(
        key="optimized",
        label="Optimized：Reranker(candidate 12) · Top-5 · threshold 0.40 · prompt v2",
        options=AgentOptions(
            top_k=5,
            min_similarity=0.40,
            use_rerank=True,
            rerank_candidates=12,
            prompt_version="v2",
        ),
    ),
}
CONFIG_ORDER = ("baseline", "prompt_v2", "optimized")

RETRIEVAL_CONFIGS = {
    "top5-threshold40": AgentOptions(
        top_k=5,
        min_similarity=0.40,
        use_rerank=False,
    ),
    "top8-threshold40": AgentOptions(
        top_k=8,
        min_similarity=0.40,
        use_rerank=False,
    ),
    "top5-threshold35": AgentOptions(
        top_k=5,
        min_similarity=0.35,
        use_rerank=False,
    ),
    "top5-threshold40-rerank12": AgentOptions(
        top_k=5,
        min_similarity=0.40,
        use_rerank=True,
        rerank_candidates=12,
    ),
}


def load_cases(limit: int | None = None) -> list[dict[str, Any]]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    return cases[:limit] if limit else cases


def answer_case(
    case: dict[str, Any],
    config: EvalConfig,
    settings: Any,
) -> dict[str, Any]:
    started = time.perf_counter()
    agent_outcome = None
    error: str | None = None
    answer = ""
    prompt_tokens = 0
    completion_tokens = 0

    try:
        with SessionLocal() as db:
            conversation = Conversation(
                public_id=f"eval-{uuid.uuid4().hex}",
                channel="eval",
                status="active",
            )
            db.add(conversation)
            db.flush()
            agent_outcome = agent.run_agent(
                db,
                conversation,
                case.get("history", []),
                case["query"],
                options=config.options,
                persist=False,
            )

        if agent_outcome.direct_answer is not None:
            answer = agent_outcome.direct_answer
        else:
            parts: list[str] = []
            usage = llm.LLMUsage(prompt_tokens=0, completion_tokens=0)
            for event in llm.stream_completion(
                settings, agent_outcome.llm_messages or []
            ):
                if isinstance(event, llm.LLMDelta):
                    parts.append(event.text)
                elif isinstance(event, llm.LLMUsage):
                    usage = event
            answer = "".join(parts).strip()
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
    except Exception as exc:
        error = f"{type(exc).__name__}: {str(exc)[:300]}"

    latency_ms = round((time.perf_counter() - started) * 1000)
    mode = agent_outcome.mode if agent_outcome else "error"
    sources = agent_outcome.sources if agent_outcome else []
    tool_trace = agent_outcome.tool_trace if agent_outcome else []
    expected_modes = set(case.get("expected_modes", []))
    expected_tools = set(case.get("expected_tools", []))
    actual_tools = [item.get("tool") for item in tool_trace]
    successful_tools = {
        item.get("tool") for item in tool_trace if item.get("status") == "success"
    }
    failed_tools = {
        item.get("tool") for item in tool_trace if item.get("status") == "error"
    }
    expected_source_set = set(case.get("expected_sources", []))
    actual_source_set = {
        source.get("heading") for source in sources if source.get("heading")
    }
    must_include = case.get("must_include_any", [])
    forbidden = case.get("forbidden", [])

    mode_ok = mode in expected_modes
    if expected_tools:
        tools_ok = (
            expected_tools <= failed_tools
            if case.get("expected_tool_error")
            else expected_tools <= successful_tools
        )
    else:
        tools_ok = len(actual_tools) == 0
    retrieval_ok = (
        not expected_source_set or bool(expected_source_set & actual_source_set)
    )
    has_inline_citation = bool(re.search(r"\[\d+\]", answer))
    citation_ok = True
    if case.get("expect_citation"):
        citation_ok = bool(sources) and has_inline_citation
    keyword_ok = any(keyword in answer for keyword in must_include) if must_include else True
    forbidden_hit = [keyword for keyword in forbidden if keyword in answer]
    passed = (
        error is None
        and mode_ok
        and tools_ok
        and retrieval_ok
        and citation_ok
        and keyword_ok
        and not forbidden_hit
    )

    result = {
        "id": case["id"],
        "category": case["category"],
        "query": case["query"],
        "expected_modes": sorted(expected_modes),
        "expected_tools": sorted(expected_tools),
        "expected_sources": sorted(expected_source_set),
        "expect_citation": bool(case.get("expect_citation")),
        "mode": mode,
        "tools": actual_tools,
        "tool_trace": tool_trace,
        "source_headings": sorted(item for item in actual_source_set if item),
        "answer": answer,
        "error": error,
        "latency_ms": latency_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "checks": {
            "mode": mode_ok,
            "tools": tools_ok,
            "retrieval": retrieval_ok,
            "citation": citation_ok,
            "keyword": keyword_ok,
            "forbidden": not forbidden_hit,
            "no_error": error is None,
        },
        "passed": passed,
    }
    return result


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile_value)))
    return round(ordered[index], 1)


def summarize(results: list[dict[str, Any]], settings: Any) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for result in results if result["passed"])
    mode_ok = sum(1 for result in results if result["checks"]["mode"])
    tools_ok = sum(1 for result in results if result["checks"]["tools"])
    keyword_ok = sum(1 for result in results if result["checks"]["keyword"])
    retrieval_results = [
        result for result in results if result["expected_sources"]
    ]
    retrieval_ok = sum(
        1 for result in retrieval_results if result["checks"]["retrieval"]
    )
    citation_results = [result for result in results if result["expect_citation"]]
    citation_ok = sum(
        1 for result in citation_results if result["checks"]["citation"]
    )
    expected_citation_count = len(citation_results)
    fallback_results = [
        result for result in results if result["category"] == "refusal"
    ]
    # Safe refusal counts both deterministic fallback/clarify and a grounded
    # RAG answer that explicitly refuses; the mode alone is an implementation detail.
    fallback_ok = sum(
        1
        for result in fallback_results
        if result["mode"] in {"fallback", "clarify"} or result["checks"]["keyword"]
    )
    latencies = [result["latency_ms"] for result in results]
    prompt_tokens = sum(result["prompt_tokens"] for result in results)
    completion_tokens = sum(result["completion_tokens"] for result in results)
    estimated_cost = (
        prompt_tokens
        / 1_000_000
        * settings.deepseek_input_price_cny_per_million
        + completion_tokens
        / 1_000_000
        * settings.deepseek_output_price_cny_per_million
    )

    category_stats: dict[str, dict[str, Any]] = {}
    for category in sorted({result["category"] for result in results}):
        subset = [result for result in results if result["category"] == category]
        category_stats[category] = {
            "count": len(subset),
            "passed": sum(1 for result in subset if result["passed"]),
            "pass_rate": round(
                sum(1 for result in subset if result["passed"]) / len(subset), 4
            ),
        }

    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0,
        "mode_accuracy": round(mode_ok / total, 4) if total else 0,
        "tool_accuracy": round(tools_ok / total, 4) if total else 0,
        "keyword_accuracy": round(keyword_ok / total, 4) if total else 0,
        "retrieval_cases": len(retrieval_results),
        "retrieval_hit_rate": round(retrieval_ok / len(retrieval_results), 4)
        if retrieval_results
        else 0,
        "citation_cases": expected_citation_count,
        "citation_rate": round(citation_ok / expected_citation_count, 4)
        if expected_citation_count
        else 0,
        "refusal_cases": len(fallback_results),
        "refusal_accuracy": round(fallback_ok / len(fallback_results), 4)
        if fallback_results
        else 0,
        "avg_latency_ms": round(sum(latencies) / total, 1) if total else 0,
        "p95_latency_ms": percentile(latencies, 0.95),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_cny": round(estimated_cost, 6),
        "categories": category_stats,
    }


def retrieval_sweep(
    cases: list[dict[str, Any]],
    settings: Any,
) -> dict[str, Any]:
    source_cases = [case for case in cases if case.get("expected_sources")]
    sweep: dict[str, Any] = {}
    for name, options in RETRIEVAL_CONFIGS.items():
        hits = 0
        top1_hits = 0
        reciprocal_rank = 0.0
        errors = 0
        with SessionLocal() as db:
            for case in source_cases:
                try:
                    sources = knowledge.search_knowledge(
                        db,
                        case["query"],
                        top_k=options.top_k,
                        min_similarity=options.min_similarity,
                        use_rerank=options.use_rerank,
                        candidate_k=options.rerank_candidates,
                    )
                    expected = set(case["expected_sources"])
                    rank = next(
                        (
                            index
                            for index, source in enumerate(sources, start=1)
                            if source.get("heading") in expected
                        ),
                        None,
                    )
                    if rank is not None:
                        hits += 1
                        reciprocal_rank += 1 / rank
                        if rank == 1:
                            top1_hits += 1
                except Exception:
                    errors += 1
            db.rollback()
        sweep[name] = {
            "cases": len(source_cases),
            "hits": hits,
            "top1_hits": top1_hits,
            "mrr": round(reciprocal_rank / len(source_cases), 4) if source_cases else 0,
            "errors": errors,
            "hit_rate": round(hits / len(source_cases), 4) if source_cases else 0,
        }
    return sweep


def write_report(
    summaries: dict[str, dict[str, Any]],
    results: dict[str, list[dict[str, Any]]],
    sweep: dict[str, Any],
    cases: list[dict[str, Any]],
) -> None:
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    category_counts: dict[str, int] = {}
    for case in cases:
        category_counts[case["category"]] = category_counts.get(case["category"], 0) + 1

    lines = [
        "# M6 评测报告",
        "",
        f"> 生成时间：{generated}",
        "> 数据：合成售后知识、订单和商品；所有评测事务均回滚，不修改演示库。",
        f"> 样本数：{len(cases)}；类别：" + "、".join(
            f"{key} {value}" for key, value in sorted(category_counts.items())
        ),
        "",
        "## 评测方法",
        "",
        "- 运行与线上聊天相同的 LangGraph Agent、工具和 Prompt 管线；",
        "- 知识检索使用真实 Chroma；Embedding/Reranker 使用 SiliconFlow；回答使用 DeepSeek `deepseek-flash`；",
        "- baseline：Top-5、阈值 0.40、无 Reranker、Prompt v1；",
        "- prompt_v2：Top-5、阈值 0.40、无 Reranker、Prompt v2，用于分离 Prompt 的影响；",
        "- optimized：Reranker 从 12 个候选中重排、Top-5、阈值 0.40、Prompt v2；",
        "- 通过条件同时检查模式、工具、检索来源、引用、关键词和无错误；",
        "- 安全拒答/澄清按行为统计：确定性 fallback/clarify，或 RAG 回答中明确拒答，均视为安全处理；",
        "- 评测价格仅用于演示成本估算，实际账单以供应商为准。",
        "",
        "## 结果对比",
        "",
        "| 配置 | 通过率 | 模式正确 | 工具正确 | 检索命中 | 引用覆盖 | 关键词命中 | 安全拒答/澄清 | P95 延迟 | 平均延迟 | 总 tokens | 估算成本 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    config_keys = [key for key in CONFIG_ORDER if key in summaries]
    for key in config_keys:
        metric = summaries[key]
        lines.append(
            "| {label} | {pass_rate}/{total} ({pass_pct}) | {mode:.1%} | {tool:.1%} | "
            "{retrieval:.1%} | {citation:.1%} | {keyword:.1%} | {refusal:.1%} | "
            "{p95:.0f}ms | {avg:.0f}ms | {tokens} | ¥{cost:.6f} |".format(
                label=key,
                pass_rate=metric["passed"],
                total=metric["total"],
                pass_pct=f"{metric['pass_rate']:.1%}",
                mode=metric["mode_accuracy"],
                tool=metric["tool_accuracy"],
                retrieval=metric["retrieval_hit_rate"],
                citation=metric["citation_rate"],
                keyword=metric["keyword_accuracy"],
                refusal=metric["refusal_accuracy"],
                p95=metric["p95_latency_ms"],
                avg=metric["avg_latency_ms"],
                tokens=metric["prompt_tokens"] + metric["completion_tokens"],
                cost=metric["estimated_cost_cny"],
            )
        )
    lines.extend(
        [
            "",
            "### 分类通过率",
            "",
            "| 类别 | 样本 | " + " | ".join(config_keys) + " |",
            "|---|---:|" + "---:|" * len(config_keys),
        ]
    )
    for category in sorted(category_counts):
        cells = []
        for key in config_keys:
            stat = summaries.get(key, {}).get("categories", {}).get(category)
            cells.append(
                f"{stat['passed']}/{stat['count']} ({stat['pass_rate']:.1%})"
                if stat
                else "-"
            )
        lines.append(
            f"| {category} | {category_counts[category]} | " + " | ".join(cells) + " |"
        )

    lines.extend(
        [
            "",
            "## 检索参数对比（仅含需要知识来源的样本）",
            "",
            "| 配置 | 样本 | 命中 | Top-1 命中 | MRR | 错误 | 命中率 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, stat in sweep.items():
        lines.append(
            f"| {name} | {stat['cases']} | {stat['hits']} | {stat['top1_hits']} | "
            f"{stat['mrr']:.4f} | {stat['errors']} | {stat['hit_rate']:.1%} |"
        )

    lines.extend(
        [
            "",
            "## 失败样例（最多每配置 10 条）",
            "",
        ]
    )
    for key in config_keys:
        if key not in results:
            continue
        failures = [item for item in results[key] if not item["passed"]][:10]
        lines.append(f"### {key}（{sum(1 for item in results[key] if not item['passed'])} 条失败）")
        if not failures:
            lines.append("无。")
            lines.append("")
            continue
        for item in failures:
            failed_checks = ", ".join(
                name for name, ok in item["checks"].items() if not ok
            ) or "error"
            lines.append(
                f"- **{item['id']}** `{item['query']}` · 期望模式 {item['expected_modes']} / 实际 {item['mode']} · "
                f"工具 {item['tools'] or '-'} · 失败检查：{failed_checks} · "
                f"{item['latency_ms']}ms"
            )
        lines.append("")

    lines.extend(
        [
            "## 解释与限制",
            "",
            "- 这是一次单轮离线评测，不等同于真实用户分布或统计显著性；",
            "- 关键词和引用检查是规则评分，可能低估表达多样性，也不会判断回答是否完全忠实；",
            "- 检索命中指任一期望标题出现在返回来源中；Top-1 与 MRR 用于观察排序质量；",
            "- 个别越界问题会进入 RAG 分支但回答明确拒答；这类样本按安全行为通过，路由效率另作优化项；",
            "- Prompt v2 与 Reranker 已拆分为不同配置，但仍为单次运行，结论需要在更多样本中复核；",
            "- 评测不会修改演示库会话或工单，Agent 运行在回滚事务中。",
            "",
        ]
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    RAW_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_RESULTS_DIR.joinpath("results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"report={REPORT_PATH}")
    print(f"raw_results={RAW_RESULTS_DIR / 'results.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the M6 evaluation set.")
    parser.add_argument(
        "--config",
        choices=[*CONFIG_ORDER, "all"],
        default="all",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    settings = get_settings()
    if not settings.has_siliconflow_key or not settings.has_deepseek_key:
        raise SystemExit("SILICONFLOW_API_KEY and DEEPSEEK_API_KEY are required.")
    cases = load_cases(args.limit)
    selected = list(CONFIG_ORDER) if args.config == "all" else [args.config]

    results: dict[str, list[dict[str, Any]]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for key in selected:
        config = CONFIGS[key]
        print(f"=== {config.label} ===")
        config_results: list[dict[str, Any]] = []
        for index, case in enumerate(cases, start=1):
            result = answer_case(case, config, settings)
            config_results.append(result)
            mark = "PASS" if result["passed"] else "FAIL"
            print(
                f"[{index:02d}/{len(cases)}] {case['id']} {mark} "
                f"mode={result['mode']} latency={result['latency_ms']}ms"
            )
        results[key] = config_results
        summaries[key] = summarize(config_results, settings)
        print(json.dumps(summaries[key], ensure_ascii=False, indent=2))

    sweep = retrieval_sweep(cases, settings) if args.config == "all" else {}
    write_report(summaries, results, sweep, cases)


if __name__ == "__main__":
    main()
