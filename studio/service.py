"""批次创建与单队列渲染。"""

from __future__ import annotations

import json
import logging
import secrets
import threading
from typing import Any, Optional

import httpx
from openai import OpenAIError

from studio.checks import CheckError, check_image, check_video
from studio.comfy import ComfyClient, ComfyError
from studio.config import (
    I2V_TIMEOUT_SECONDS,
    I2V_WORKFLOW_NAME,
    MANIFEST_DIR,
    MAX_ATTEMPTS,
    T2I_TIMEOUT_SECONDS,
    T2I_WORKFLOW_NAME,
)
from studio.db import Database
from studio.prompts import write_image_prompt, write_motion_prompt
from studio.storage import LocalMediaStore
from studio.workflows import build_i2v, build_t2i

logger = logging.getLogger(__name__)


class BatchError(ValueError):
    """批次参数不合法。"""


class StudioService:
    """数据中台的任务入口。"""

    def __init__(self, database: Optional[Database] = None, store: Optional[LocalMediaStore] = None) -> None:
        self.db = database or Database()
        self.store = store or LocalMediaStore()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """启动唯一的渲染线程。"""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="studio-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止渲染线程。"""
        self._stop.set()

    def create_t2i_theme(self, theme: str, count: int) -> dict[str, Any]:
        """用一个主题创建文生图批次。"""
        theme = theme.strip()
        if not theme:
            raise BatchError("主题不能为空")
        if count < 1:
            raise BatchError("数量至少为 1")
        batch_id = _new_id()
        self.db.insert_batch(batch_id, "t2i", "theme", count, theme=theme)
        for _ in range(count):
            self.db.insert_sample(_new_id(), batch_id, "t2i", T2I_WORKFLOW_NAME, theme=theme)
        return self.batch_view(batch_id)

    def create_t2i_jsonl(self, raw: str) -> dict[str, Any]:
        """从 JSONL 创建文生图批次。一行一条。"""
        prepared: list[dict[str, str]] = []
        for item in _parse_jsonl(raw):
            prompt = str(item.get("prompt") or "").strip()
            theme = str(item.get("theme") or "").strip()
            if not prompt and not theme:
                raise BatchError("每一行都要有 prompt 或 theme")
            prepared.append({"prompt": prompt, "theme": theme})
        batch_id = _new_id()
        self.db.insert_batch(batch_id, "t2i", "jsonl", len(prepared))
        for item in prepared:
            self.db.insert_sample(
                _new_id(),
                batch_id,
                "t2i",
                T2I_WORKFLOW_NAME,
                image_prompt=item["prompt"] or None,
                theme=item["theme"] or None,
            )
        return self.batch_view(batch_id)

    def create_i2v_from_images(self, image_ids: list[str]) -> dict[str, Any]:
        """为每张已入库图片创建一条图生视频。"""
        images = [self._require_source_image(image_id) for image_id in image_ids]
        if not images:
            raise BatchError("请至少选择一张图片")
        batch_id = _new_id()
        self.db.insert_batch(batch_id, "i2v", "images", len(images))
        for image in images:
            self.db.insert_sample(
                _new_id(),
                batch_id,
                "i2v",
                I2V_WORKFLOW_NAME,
                source_image_id=image["id"],
            )
        return self.batch_view(batch_id)

    def create_i2v_from_batch(self, source_batch_id: str) -> dict[str, Any]:
        """把一整批已成功的文生图送去图生视频。"""
        images = self.db.succeeded_t2i_in_batch(source_batch_id)
        if not images:
            raise BatchError("这批文生图里还没有可使用的图片")
        batch_id = _new_id()
        self.db.insert_batch(batch_id, "i2v", "batch", len(images), source_batch_id=source_batch_id)
        for image in images:
            self.db.insert_sample(
                _new_id(),
                batch_id,
                "i2v",
                I2V_WORKFLOW_NAME,
                source_image_id=image["id"],
            )
        return self.batch_view(batch_id)

    def create_i2v_jsonl(self, raw: str) -> dict[str, Any]:
        """从 JSONL 创建图生视频。每行指定一张已入库图片。"""
        items = _parse_jsonl(raw)
        prepared: list[dict[str, str]] = []
        for item in items:
            source_id = str(item.get("source_image_id") or "").strip()
            if not source_id:
                raise BatchError("图生视频每一行都要有 source_image_id")
            self._require_source_image(source_id)
            prepared.append(
                {
                    "source_image_id": source_id,
                    "prompt": str(item.get("prompt") or "").strip(),
                    "theme": str(item.get("theme") or "").strip(),
                }
            )
        batch_id = _new_id()
        self.db.insert_batch(batch_id, "i2v", "jsonl", len(prepared))
        for item in prepared:
            self.db.insert_sample(
                _new_id(),
                batch_id,
                "i2v",
                I2V_WORKFLOW_NAME,
                source_image_id=item["source_image_id"],
                motion_prompt=item["prompt"] or None,
                theme=item["theme"] or None,
            )
        return self.batch_view(batch_id)

    def batch_view(self, batch_id: str) -> dict[str, Any]:
        """批次加上它的样本。"""
        batch = self.db.get_batch(batch_id)
        if batch is None:
            raise BatchError("批次不存在")
        batch["samples"] = self.db.list_samples(batch_id=batch_id, limit=500)
        return batch

    def export_jsonl(self, batch_id: Optional[str] = None) -> str:
        """导出已入库样本。"""
        samples = self.db.list_samples(status="succeeded", batch_id=batch_id, limit=5000)
        lines = [json.dumps(_manifest_row(sample), ensure_ascii=False) for sample in samples]
        return "\n".join(lines) + ("\n" if lines else "")

    def _require_source_image(self, sample_id: str) -> dict[str, Any]:
        sample = self.db.get_sample(sample_id)
        if sample is None or sample["modality"] != "t2i" or sample["status"] != "succeeded":
            raise BatchError(f"找不到已入库图片: {sample_id}")
        if not sample.get("file_path"):
            raise BatchError(f"图片没有文件: {sample_id}")
        return sample

    def _loop(self) -> None:
        while not self._stop.is_set():
            sample = self.db.claim_next()
            if sample is None:
                self._stop.wait(1.5)
                continue
            try:
                self._run(sample)
            except (BatchError, CheckError, ComfyError, OpenAIError, OSError, TimeoutError, httpx.HTTPError, RuntimeError, ValueError) as exc:
                logger.warning("样本失败 %s: %s", sample["id"], exc)
                self._fail(sample["id"], sample["batch_id"], str(exc))

    def _fail(self, sample_id: str, batch_id: str, message: str) -> None:
        current = self.db.get_sample(sample_id)
        attempts = int(current["attempts"]) if current else MAX_ATTEMPTS
        status = "failed" if attempts >= MAX_ATTEMPTS else "queued"
        self.db.update_sample(sample_id, status=status, error=message[:1000])
        self.db.refresh_batch(batch_id)
        self._write_manifest(batch_id)

    def _run(self, sample: dict[str, Any]) -> None:
        seed = secrets.randbits(48)
        self.db.update_sample(sample["id"], seed=seed)
        client = ComfyClient()
        try:
            if sample["modality"] == "t2i":
                self._run_t2i(client, sample, seed)
            else:
                self._run_i2v(client, sample, seed)
        finally:
            client.close()
        self.db.refresh_batch(sample["batch_id"])
        self._write_manifest(sample["batch_id"])

    def _run_t2i(self, client: ComfyClient, sample: dict[str, Any], seed: int) -> None:
        prompt = (sample.get("image_prompt") or "").strip()
        if not prompt:
            prompt = write_image_prompt(sample.get("theme") or "")
            self.db.update_sample(sample["id"], image_prompt=prompt)
        workflow = build_t2i(prompt, seed, sample["id"])
        prompt_id = client.submit(workflow)
        self.db.update_sample(sample["id"], comfy_prompt_id=prompt_id)
        history = client.wait(prompt_id, T2I_TIMEOUT_SECONDS)
        suffix, content = client.download_output(history, "picture")
        measured = check_image(content, prompt)
        relative = self.store.save("picture", sample["id"], suffix, content)
        self.db.update_sample(
            sample["id"],
            status="succeeded",
            file_path=relative,
            sha256=self.store.sha256(content),
            error=None,
            **measured,
        )

    def _run_i2v(self, client: ComfyClient, sample: dict[str, Any], seed: int) -> None:
        source = self._require_source_image(sample["source_image_id"])
        motion = (sample.get("motion_prompt") or "").strip()
        if not motion:
            motion = write_motion_prompt(source.get("image_prompt") or "", sample.get("theme"))
            self.db.update_sample(sample["id"], motion_prompt=motion, image_prompt=source.get("image_prompt"))
        else:
            self.db.update_sample(sample["id"], image_prompt=source.get("image_prompt"))
        image_bytes = self.store.read(source["file_path"])
        suffix = _suffix(source["file_path"])
        uploaded = client.upload_image(f"{sample['id']}{suffix}", image_bytes)
        workflow = build_i2v(motion, seed, sample["id"], uploaded)
        prompt_id = client.submit(workflow)
        self.db.update_sample(sample["id"], comfy_prompt_id=prompt_id)
        history = client.wait(prompt_id, I2V_TIMEOUT_SECONDS)
        out_suffix, content = client.download_output(history, "video")
        image_prompt = source.get("image_prompt") or ""
        measured = check_video(content, image_prompt, motion)
        relative = self.store.save("video", sample["id"], out_suffix, content)
        self.db.update_sample(
            sample["id"],
            status="succeeded",
            file_path=relative,
            sha256=self.store.sha256(content),
            error=None,
            **measured,
        )

    def _write_manifest(self, batch_id: str) -> None:
        MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        samples = self.db.list_samples(batch_id=batch_id, limit=5000)
        lines = [
            json.dumps(_manifest_row(sample), ensure_ascii=False)
            for sample in samples
            if sample["status"] == "succeeded"
        ]
        text = "\n".join(lines) + ("\n" if lines else "")
        (MANIFEST_DIR / f"{batch_id}.jsonl").write_text(text, encoding="utf-8")


def _manifest_row(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": sample["id"],
        "batch_id": sample["batch_id"],
        "type": sample["modality"],
        "seed": sample.get("seed"),
        "image_prompt": sample.get("image_prompt") or "",
        "motion_prompt": sample.get("motion_prompt") or "",
        "source_image_id": sample.get("source_image_id") or "",
        "workflow_filename": sample.get("workflow_filename") or "",
        "comfy_prompt_id": sample.get("comfy_prompt_id") or "",
        "file_path": sample.get("file_path") or "",
        "width": sample.get("width"),
        "height": sample.get("height"),
        "duration": sample.get("duration"),
        "sha256": sample.get("sha256") or "",
        "status": sample.get("status"),
        "created_at": sample.get("created_at"),
    }


def _parse_jsonl(raw: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except json.JSONDecodeError as exc:
            raise BatchError(f"第 {line_number} 行不是 JSON") from exc
        if not isinstance(item, dict):
            raise BatchError(f"第 {line_number} 行必须是对象")
        items.append(item)
    if not items:
        raise BatchError("JSONL 是空的")
    return items


def _new_id() -> str:
    return secrets.token_hex(8)


def _suffix(path: str) -> str:
    dot = path.rfind(".")
    if dot < 0:
        return ".png"
    return path[dot:].lower()
