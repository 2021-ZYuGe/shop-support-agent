from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from openai import OpenAI

from app.core.config import Settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """The upstream chat model failed."""


@dataclass(frozen=True)
class LLMDelta:
    text: str


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int
    completion_tokens: int


def stream_completion(
    settings: Settings,
    messages: Sequence[dict[str, str]],
) -> Iterator[LLMDelta | LLMUsage]:
    if not settings.has_deepseek_key:
        raise LLMError("尚未配置 DEEPSEEK_API_KEY，无法生成回答。")

    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        timeout=settings.deepseek_timeout_seconds,
    )

    try:
        stream = client.chat.completions.create(
            model=settings.deepseek_model,
            messages=list(messages),
            stream=True,
            stream_options={"include_usage": True},
            temperature=settings.deepseek_temperature,
            max_tokens=settings.deepseek_max_tokens,
        )
        for chunk in stream:
            if chunk.usage is not None:
                yield LLMUsage(
                    prompt_tokens=int(chunk.usage.prompt_tokens or 0),
                    completion_tokens=int(chunk.usage.completion_tokens or 0),
                )
            if not chunk.choices:
                continue
            text = chunk.choices[0].delta.content
            if text:
                yield LLMDelta(text)
    except Exception as exc:
        logger.warning("DeepSeek stream failed: %s", type(exc).__name__)
        raise LLMError("DeepSeek 服务暂时不可用，请稍后再试。") from exc
