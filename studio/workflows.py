"""把最终提示词和种子写进现有 ComfyUI API 工作流。"""

from __future__ import annotations

import json
from typing import Any

from studio.config import I2V_WORKFLOW, T2I_WORKFLOW

T2I_SWITCH = "459:474"
T2I_SAMPLER = "459:458"
T2I_SAVE = "461"
I2V_PROMPT = "105_104"
I2V_NOISE = "105_15"
I2V_LOAD = "114"
I2V_SAVE = "128"


def _load(path: Any) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        graph = json.load(handle)
    if not isinstance(graph, dict):
        raise ValueError(f"工作流格式不正确: {path}")
    return graph


def build_t2i(prompt: str, seed: int, sample_id: str) -> dict[str, Any]:
    """文生图：关闭图内改写，写入最终英文提示词。"""
    graph = _load(T2I_WORKFLOW)
    graph[T2I_SWITCH]["inputs"]["switch"] = False
    graph[T2I_SWITCH]["inputs"]["on_false"] = prompt
    graph[T2I_SAMPLER]["inputs"]["seed"] = seed
    graph[T2I_SAVE]["inputs"]["filename_prefix"] = f"dataset/t2i/{sample_id}"
    return graph


def build_i2v(motion_prompt: str, seed: int, sample_id: str, image_name: str) -> dict[str, Any]:
    """图生视频：写入运动提示词、种子和已上传的参考图。"""
    graph = _load(I2V_WORKFLOW)
    graph[I2V_PROMPT]["inputs"]["prompt"] = motion_prompt
    graph[I2V_NOISE]["inputs"]["noise_seed"] = seed
    graph[I2V_LOAD]["inputs"]["image"] = image_name
    graph[I2V_SAVE]["inputs"]["filename_prefix"] = f"dataset/i2v/{sample_id}"
    return graph
