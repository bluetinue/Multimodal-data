"""ComfyUI 队列客户端。一次只由上层提交一个任务。"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from studio.config import comfyui_url

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_VIDEO_EXT = {".mp4", ".webm", ".mov"}


class ComfyError(RuntimeError):
    """ComfyUI 返回了无法继续的结果。"""


class ComfyClient:
    """提交工作流、等待历史并下载输出。"""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or comfyui_url()).rstrip("/")
        self._http = httpx.Client(timeout=httpx.Timeout(60.0, read=120.0), trust_env=True)

    def close(self) -> None:
        """关闭连接。"""
        self._http.close()

    def health(self) -> dict[str, Any]:
        """读取 ComfyUI 系统状态。"""
        response = self._http.get(f"{self.base_url}/system_stats")
        response.raise_for_status()
        payload = response.json()
        devices = payload.get("devices") or []
        name = devices[0].get("name", "") if devices else ""
        return {
            "ok": True,
            "version": (payload.get("system") or {}).get("comfyui_version", ""),
            "device": name,
        }

    def upload_image(self, filename: str, content: bytes) -> str:
        """把参考图上传到 ComfyUI input，返回服务端文件名。"""
        response = self._http.post(
            f"{self.base_url}/upload/image",
            files={"image": (filename, content, "application/octet-stream")},
            data={"type": "input", "overwrite": "true"},
        )
        response.raise_for_status()
        payload = response.json()
        name = payload.get("name") or filename
        if not isinstance(name, str):
            raise ComfyError("上传图片没有返回文件名")
        return name

    def submit(self, workflow: dict[str, Any]) -> str:
        """提交一张 API 工作流，返回 prompt_id。"""
        response = self._http.post(f"{self.base_url}/prompt", json={"prompt": workflow})
        if response.status_code >= 400:
            raise ComfyError(response.text[:800] or f"提交失败 HTTP {response.status_code}")
        payload = response.json()
        if payload.get("node_errors"):
            raise ComfyError(str(payload["node_errors"])[:800])
        prompt_id = payload.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyError("ComfyUI 没有返回 prompt_id")
        return prompt_id

    def wait(self, prompt_id: str, timeout_seconds: float) -> dict[str, Any]:
        """等到该任务写入 history。"""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            response = self._http.get(f"{self.base_url}/history/{prompt_id}")
            response.raise_for_status()
            payload = response.json()
            item = payload.get(prompt_id)
            if isinstance(item, dict):
                status = item.get("status") or {}
                status_text = str(status.get("status_str", ""))
                if status_text == "error":
                    raise ComfyError(str(status.get("messages", "ComfyUI 执行失败"))[:800])
                if status.get("completed") or status_text == "success" or item.get("outputs"):
                    return item
            time.sleep(2)
        raise TimeoutError(f"等待 ComfyUI 超时: {prompt_id}")

    def download_output(self, history_item: dict[str, Any], kind: str) -> tuple[str, bytes]:
        """下载第一张图片或第一条视频。"""
        wanted = _IMAGE_EXT if kind == "picture" else _VIDEO_EXT
        for file_info in _iter_files(history_item.get("outputs") or {}):
            filename = str(file_info.get("filename", ""))
            suffix = _suffix(filename)
            if suffix not in wanted:
                continue
            content = self._download_file(file_info)
            return suffix, content
        raise ComfyError("ComfyUI 历史里没有找到输出文件")

    def _download_file(self, file_info: dict[str, Any]) -> bytes:
        response = self._http.get(
            f"{self.base_url}/view",
            params={
                "filename": file_info.get("filename", ""),
                "subfolder": file_info.get("subfolder", ""),
                "type": file_info.get("type", "output"),
            },
        )
        response.raise_for_status()
        if not response.content:
            raise ComfyError("下载到的文件是空的")
        return response.content


def _suffix(filename: str) -> str:
    dot = filename.rfind(".")
    if dot < 0:
        return ""
    return filename[dot:].lower()


def _iter_files(outputs: dict[str, Any]) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for value in node_output.values():
            if isinstance(value, list):
                files.extend(item for item in value if isinstance(item, dict) and item.get("filename"))
    return files
