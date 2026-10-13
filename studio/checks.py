"""入库前检查文件、分辨率、时长、哈希和提示词。"""

from __future__ import annotations

import json
import subprocess
import tempfile
from io import BytesIO
from typing import Any

from PIL import Image, UnidentifiedImageError

from studio.config import I2V_DURATION_SECONDS


class CheckError(ValueError):
    """样本不满足入库条件。"""


def check_image(content: bytes, prompt: str) -> dict[str, Any]:
    """检查文生图结果是正方形，并且提示词存在。"""
    if not prompt.strip():
        raise CheckError("画面提示词为空")
    if not content:
        raise CheckError("图片文件为空")
    try:
        with Image.open(BytesIO(content)) as image:
            width, height = image.size
    except UnidentifiedImageError as exc:
        raise CheckError("下载的文件不是图片") from exc
    if width <= 0 or height <= 0 or width != height:
        raise CheckError(f"分辨率不是 1:1，实际为 {width}x{height}")
    return {"width": width, "height": height, "duration": None}


def check_video(content: bytes, image_prompt: str, motion_prompt: str) -> dict[str, Any]:
    """检查图生视频是竖屏且时长接近 3 秒。"""
    if not image_prompt.strip() or not motion_prompt.strip():
        raise CheckError("画面提示词或运动提示词为空")
    if not content:
        raise CheckError("视频文件为空")
    info = _probe(content)
    width = int(info["width"])
    height = int(info["height"])
    duration = float(info["duration"])
    ratio = height / width if width else 0
    if abs(ratio - (16 / 9)) > 0.08:
        raise CheckError(f"分辨率不是 9:16，实际为 {width}x{height}")
    if abs(duration - I2V_DURATION_SECONDS) > 0.6:
        raise CheckError(f"时长不是 3 秒，实际为 {duration:.2f} 秒")
    return {"width": width, "height": height, "duration": duration}


def _probe(content: bytes) -> dict[str, Any]:
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4") as handle:
            handle.write(content)
            handle.flush()
            completed = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,duration:format=duration",
                    "-of",
                    "json",
                    handle.name,
                ],
                capture_output=True,
                check=False,
            )
    except OSError as exc:
        raise CheckError("无法读取视频信息") from exc
    if completed.returncode != 0:
        raise CheckError("视频文件无法解析")
    try:
        payload = json.loads(completed.stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise CheckError("视频信息不是有效数据") from exc
    streams = payload.get("streams") or [{}]
    stream = streams[0] if streams else {}
    duration_text = stream.get("duration") or (payload.get("format") or {}).get("duration")
    if not stream.get("width") or not stream.get("height") or not duration_text:
        raise CheckError("视频缺少分辨率或时长")
    return {
        "width": stream["width"],
        "height": stream["height"],
        "duration": duration_text,
    }
