from __future__ import annotations

import re

GUARD_ANSWER = (
    "抱歉，我不能忽略、透露或修改系统指令，也不会执行越权操作。"
    "你可以继续咨询商品、订单、物流或售后问题。"
)

_INJECTION_PATTERNS = (
    re.compile(
        r"忽略.{0,16}(之前|以上|前面|所有).{0,16}(指令|提示|规则|设定)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(输出|告诉我|显示|泄露|重复|reveal|show|print).{0,16}"
        r"(系统提示词|system\s*prompt|开发者指令)",
        re.IGNORECASE,
    ),
    re.compile(
        r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts)",
        re.IGNORECASE,
    ),
    re.compile(r"(jailbreak|越狱|开发者模式|developer\s*mode)", re.IGNORECASE),
    re.compile(r"系统提示词|system\s*prompt", re.IGNORECASE),
)


def looks_like_prompt_injection(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _INJECTION_PATTERNS)
