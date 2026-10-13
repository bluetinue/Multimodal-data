"""运行配置。口令和 ComfyUI 地址只从环境变量读取。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

T2I_WORKFLOW = ROOT / "picture" / "image_qwen_image_2_1_turbo_t2i-1.json"
I2V_WORKFLOW = ROOT / "video" / "video_minimax_h3_i2v_lightx2v_turbo.json"
T2I_WORKFLOW_NAME = T2I_WORKFLOW.name
I2V_WORKFLOW_NAME = I2V_WORKFLOW.name

DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "studio.sqlite"
MANIFEST_DIR = DATA_DIR / "manifests"

LLM_VERSION = "qwen38-27b-fp8"
MAX_ATTEMPTS = 3
T2I_ASPECT = "1:1"
I2V_ASPECT = "9:16"
I2V_DURATION_SECONDS = 3.0
T2I_TIMEOUT_SECONDS = 900
I2V_TIMEOUT_SECONDS = 1800


def access_token() -> str:
    """读取共享访问口令。"""
    token = os.getenv("STUDIO_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("请设置环境变量 STUDIO_ACCESS_TOKEN")
    return token


def comfyui_url() -> str:
    """读取 ComfyUI 地址。"""
    url = os.getenv("COMFYUI_URL", "").strip().rstrip("/")
    if not url:
        raise RuntimeError("请设置环境变量 COMFYUI_URL")
    return url


def studio_host() -> str:
    """服务监听地址。"""
    return os.getenv("STUDIO_HOST", "0.0.0.0")


def studio_port() -> int:
    """服务监听端口。"""
    return int(os.getenv("STUDIO_PORT", "8765"))
