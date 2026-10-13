"""数据中台网页和 API。"""

from __future__ import annotations

import hmac
import logging
from contextlib import asynccontextmanager
from hashlib import sha256
from typing import Any, Optional

import httpx
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from studio.comfy import ComfyClient
from studio.config import (
    I2V_WORKFLOW_NAME,
    LLM_VERSION,
    ROOT,
    T2I_WORKFLOW_NAME,
    access_token,
    comfyui_url,
    studio_host,
    studio_port,
)
from studio.service import BatchError, StudioService
from studio.storage import LocalMediaStore
from vllm_proxy_model import vllm_model_client

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

WEB_DIR = ROOT / "web" / "dist"
COOKIE = "studio_session"
service = StudioService()


def _session_value() -> str:
    return hmac.new(access_token().encode("utf-8"), b"studio-session", sha256).hexdigest()


def require_session(request: Request) -> None:
    """校验登录 cookie。"""
    given = request.cookies.get(COOKIE, "")
    expected = _session_value()
    if not given or not hmac.compare_digest(given, expected):
        raise HTTPException(status_code=401, detail="未登录")


class ThemeBatch(BaseModel):
    """主题批次。"""

    theme: str = Field(..., min_length=1)
    count: int = Field(1, ge=1, le=200)


class ImageBatch(BaseModel):
    """按图片 id 创建图生视频。"""

    image_ids: list[str] = Field(..., min_length=1)


class SourceBatch(BaseModel):
    """按文生图批次创建图生视频。"""

    source_batch_id: str = Field(..., min_length=1)


class LoginBody(BaseModel):
    """登录口令。"""

    token: str


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动单队列渲染。"""
    access_token()
    service.start()
    yield
    service.stop()


app = FastAPI(title="多模态数据中台", lifespan=lifespan)


@app.post("/api/login")
def login(body: LoginBody, response: Response) -> dict[str, bool]:
    """用共享口令换取会话。"""
    if not hmac.compare_digest(body.token, access_token()):
        raise HTTPException(status_code=401, detail="口令不正确")
    response.set_cookie(COOKIE, _session_value(), httponly=True, samesite="lax", path="/")
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response) -> dict[str, bool]:
    """退出登录。"""
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/session")
def session(request: Request) -> dict[str, bool]:
    """当前浏览器是否已登录。"""
    try:
        require_session(request)
    except HTTPException:
        return {"ok": False}
    return {"ok": True}


@app.get("/api/settings", dependencies=[Depends(require_session)])
def settings() -> dict[str, Any]:
    """只读展示运行参数。"""
    comfy: dict[str, Any] = {"ok": False, "version": "", "device": ""}
    try:
        client = ComfyClient()
        try:
            comfy = client.health()
        finally:
            client.close()
    except httpx.HTTPError as exc:
        comfy["error"] = str(exc)
    return {
        "comfyui_url": comfyui_url(),
        "llm_version": LLM_VERSION,
        "llm_model": vllm_model_client.get_model_name(LLM_VERSION),
        "t2i_workflow": T2I_WORKFLOW_NAME,
        "i2v_workflow": I2V_WORKFLOW_NAME,
        "token_configured": True,
        "comfy": comfy,
    }


@app.post("/api/batches/t2i", dependencies=[Depends(require_session)])
def create_t2i(body: ThemeBatch) -> dict[str, Any]:
    """提交文生图主题批次。"""
    return _batch(lambda: service.create_t2i_theme(body.theme, body.count))


@app.post("/api/batches/t2i/jsonl", dependencies=[Depends(require_session)])
async def create_t2i_jsonl(file: UploadFile = File(...)) -> dict[str, Any]:
    """上传文生图 JSONL。"""
    raw = (await file.read()).decode("utf-8")
    return _batch(lambda: service.create_t2i_jsonl(raw))


@app.post("/api/batches/i2v", dependencies=[Depends(require_session)])
def create_i2v(body: ImageBatch) -> dict[str, Any]:
    """按选中的图片提交图生视频。"""
    return _batch(lambda: service.create_i2v_from_images(body.image_ids))


@app.post("/api/batches/i2v/from-batch", dependencies=[Depends(require_session)])
def create_i2v_batch(body: SourceBatch) -> dict[str, Any]:
    """把一整批文生图送去图生视频。"""
    return _batch(lambda: service.create_i2v_from_batch(body.source_batch_id))


@app.post("/api/batches/i2v/jsonl", dependencies=[Depends(require_session)])
async def create_i2v_jsonl(file: UploadFile = File(...)) -> dict[str, Any]:
    """上传图生视频 JSONL。"""
    raw = (await file.read()).decode("utf-8")
    return _batch(lambda: service.create_i2v_jsonl(raw))


@app.get("/api/batches", dependencies=[Depends(require_session)])
def list_batches(modality: Optional[str] = None) -> dict[str, Any]:
    """最近批次。"""
    return {"items": service.db.list_batches(modality=modality)}


@app.get("/api/batches/{batch_id}", dependencies=[Depends(require_session)])
def get_batch(batch_id: str) -> dict[str, Any]:
    """批次详情。"""
    try:
        return service.batch_view(batch_id)
    except BatchError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/samples", dependencies=[Depends(require_session)])
def list_samples(
    modality: Optional[str] = None,
    status: Optional[str] = None,
    batch_id: Optional[str] = None,
) -> dict[str, Any]:
    """样本列表。"""
    return {"items": service.db.list_samples(modality=modality, status=status, batch_id=batch_id)}


@app.get("/api/media/{sample_id}", dependencies=[Depends(require_session)])
def media(sample_id: str) -> FileResponse:
    """读取已保存的图片或视频。"""
    sample = service.db.get_sample(sample_id)
    if sample is None or not sample.get("file_path"):
        raise HTTPException(status_code=404, detail="文件不存在")
    try:
        path = LocalMediaStore().resolve(sample["file_path"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="文件不存在") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path)


@app.get("/api/export", dependencies=[Depends(require_session)])
def export(batch_id: Optional[str] = None) -> PlainTextResponse:
    """导出已入库样本 JSONL。"""
    return PlainTextResponse(
        service.export_jsonl(batch_id),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=samples.jsonl"},
    )


def _batch(action: Any) -> dict[str, Any]:
    try:
        return action()
    except BatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/")
def spa_index() -> FileResponse:
    """Vue 入口。"""
    index = WEB_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="前端尚未构建，请先执行 cd frontend && npm run build")
    return FileResponse(index)


@app.get("/{full_path:path}")
def spa_fallback(full_path: str) -> FileResponse:
    """静态资源或 SPA 回退。"""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="接口不存在")
    candidate = (WEB_DIR / full_path).resolve()
    root = WEB_DIR.resolve()
    if candidate.is_file() and (root == candidate or root in candidate.parents):
        return FileResponse(candidate)
    index = WEB_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=503, detail="前端尚未构建")
    return FileResponse(index)


def main() -> None:
    """启动网站。"""
    import uvicorn

    WEB_DIR.mkdir(parents=True, exist_ok=True)
    uvicorn.run(
        "studio.server:app",
        host=studio_host(),
        port=studio_port(),
        reload=False,
    )
