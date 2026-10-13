"""用 qwen38-27b-fp8 一次写成最终英文提示词。"""

from __future__ import annotations

import re
from typing import Optional

from openai import APIStatusError, OpenAIError

from studio.config import LLM_VERSION
from vllm_proxy_model import vllm_model_client

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE = re.compile(r"^```[a-zA-Z]*\n?|```$", re.MULTILINE)

_IMAGE_SYSTEM = (
    "You write one English paragraph that describes a finished square 1:1 image. "
    "Output only that paragraph. Do not add a title, bullets, or quotation marks."
)
_MOTION_SYSTEM = (
    "You write one English motion prompt for a 3-second vertical 9:16 image-to-video clip. "
    "Keep the same subject as the still. Describe what moves from 0 to 1 seconds, "
    "1 to 2 seconds, and 2 to 3 seconds. Output only the prompt."
)


def write_image_prompt(theme: str) -> str:
    """把主题扩成文生图提示词。"""
    return _complete(_IMAGE_SYSTEM, f"Theme:\n{theme.strip()}")


def write_motion_prompt(image_prompt: str, theme: Optional[str] = None) -> str:
    """根据已保存的画面提示词写运动提示词。"""
    user = f"Still image prompt:\n{image_prompt.strip()}"
    if theme and theme.strip():
        user += f"\n\nExtra direction:\n{theme.strip()}"
    return _complete(_MOTION_SYSTEM, user)


def _complete(system: str, user: str) -> str:
    client = vllm_model_client.get_client(LLM_VERSION)
    model_name = vllm_model_client.get_model_name(LLM_VERSION)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=1200,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
    except APIStatusError:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.7,
            max_tokens=1200,
        )
    except OpenAIError:
        raise
    text = response.choices[0].message.content or ""
    cleaned = _THINK.sub("", text)
    cleaned = _FENCE.sub("", cleaned).strip().strip('"')
    if not cleaned:
        raise RuntimeError("大模型没有返回提示词")
    return cleaned
