"""SQLite 任务与样本。换 MySQL 时保持这组方法的入参和返回字典。"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from typing import Any, Optional

from studio.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id TEXT PRIMARY KEY,
    modality TEXT NOT NULL,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    theme TEXT,
    requested_count INTEGER NOT NULL,
    source_batch_id TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS samples (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    modality TEXT NOT NULL,
    seed INTEGER,
    image_prompt TEXT,
    motion_prompt TEXT,
    source_image_id TEXT,
    theme TEXT,
    workflow_filename TEXT,
    comfy_prompt_id TEXT,
    file_path TEXT,
    width INTEGER,
    height INTEGER,
    duration REAL,
    sha256 TEXT,
    status TEXT NOT NULL,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_samples_status ON samples(status, created_at);
CREATE INDEX IF NOT EXISTS idx_samples_batch ON samples(batch_id);
"""


def now_iso() -> str:
    """本地时间的 ISO 字符串。"""
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Database:
    """样本与批次存储。"""

    def __init__(self, path: Optional[Any] = None) -> None:
        self.path = path or DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _one(self, sql: str, params: tuple[Any, ...] = ()) -> Optional[dict[str, Any]]:
        row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        return [dict(row) for row in self._conn.execute(sql, params).fetchall()]

    def insert_batch(
        self,
        batch_id: str,
        modality: str,
        source: str,
        requested_count: int,
        theme: Optional[str] = None,
        source_batch_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """写入批次。"""
        created_at = now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO batches
                (id, modality, status, source, theme, requested_count, source_batch_id, created_at)
                VALUES (?, ?, 'queued', ?, ?, ?, ?, ?)
                """,
                (batch_id, modality, source, theme, requested_count, source_batch_id, created_at),
            )
            self._conn.commit()
        batch = self.get_batch(batch_id)
        if batch is None:
            raise RuntimeError("批次写入后无法读取")
        return batch

    def insert_sample(
        self,
        sample_id: str,
        batch_id: str,
        modality: str,
        workflow_filename: str,
        theme: Optional[str] = None,
        image_prompt: Optional[str] = None,
        motion_prompt: Optional[str] = None,
        source_image_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """写入一条待渲染样本。"""
        created_at = now_iso()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO samples (
                    id, batch_id, modality, image_prompt, motion_prompt, source_image_id,
                    theme, workflow_filename, status, attempts, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', 0, ?)
                """,
                (
                    sample_id,
                    batch_id,
                    modality,
                    image_prompt,
                    motion_prompt,
                    source_image_id,
                    theme,
                    workflow_filename,
                    created_at,
                ),
            )
            self._conn.commit()
        sample = self.get_sample(sample_id)
        if sample is None:
            raise RuntimeError("样本写入后无法读取")
        return sample

    def get_batch(self, batch_id: str) -> Optional[dict[str, Any]]:
        """按 id 读取批次。"""
        with self._lock:
            return self._one("SELECT * FROM batches WHERE id = ?", (batch_id,))

    def get_sample(self, sample_id: str) -> Optional[dict[str, Any]]:
        """按 id 读取样本。"""
        with self._lock:
            return self._one("SELECT * FROM samples WHERE id = ?", (sample_id,))

    def list_batches(self, modality: Optional[str] = None, limit: int = 50) -> list[dict[str, Any]]:
        """列出最近批次。"""
        with self._lock:
            if modality:
                return self._all(
                    "SELECT * FROM batches WHERE modality = ? ORDER BY created_at DESC LIMIT ?",
                    (modality, limit),
                )
            return self._all("SELECT * FROM batches ORDER BY created_at DESC LIMIT ?", (limit,))

    def list_samples(
        self,
        modality: Optional[str] = None,
        status: Optional[str] = None,
        batch_id: Optional[str] = None,
        limit: int = 80,
    ) -> list[dict[str, Any]]:
        """按条件列出样本。"""
        clauses = ["1 = 1"]
        params: list[Any] = []
        if modality:
            clauses.append("modality = ?")
            params.append(modality)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if batch_id:
            clauses.append("batch_id = ?")
            params.append(batch_id)
        params.append(limit)
        sql = f"SELECT * FROM samples WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT ?"
        with self._lock:
            return self._all(sql, tuple(params))

    def claim_next(self) -> Optional[dict[str, Any]]:
        """取出最早的排队样本并标为运行中。"""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    "SELECT id FROM samples WHERE status = 'queued' ORDER BY created_at LIMIT 1"
                ).fetchone()
                if row is None:
                    self._conn.commit()
                    return None
                sample_id = row["id"]
                self._conn.execute(
                    """
                    UPDATE samples
                    SET status = 'running', attempts = attempts + 1, error = NULL
                    WHERE id = ? AND status = 'queued'
                    """,
                    (sample_id,),
                )
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                raise
        sample = self.get_sample(sample_id)
        if sample:
            self.refresh_batch(sample["batch_id"])
        return sample

    def update_sample(self, sample_id: str, **fields: Any) -> None:
        """更新样本字段。"""
        if not fields:
            return
        keys = list(fields.keys())
        sql = "UPDATE samples SET " + ", ".join(f"{key} = ?" for key in keys) + " WHERE id = ?"
        with self._lock:
            self._conn.execute(sql, tuple(fields[key] for key in keys) + (sample_id,))
            self._conn.commit()

    def refresh_batch(self, batch_id: str) -> None:
        """按样本状态回写批次状态。"""
        with self._lock:
            rows = self._all("SELECT status FROM samples WHERE batch_id = ?", (batch_id,))
            if not rows:
                return
            statuses = {row["status"] for row in rows}
            if statuses & {"queued", "running"}:
                status = "running"
            elif statuses <= {"succeeded"}:
                status = "done"
            else:
                status = "failed"
            self._conn.execute("UPDATE batches SET status = ? WHERE id = ?", (status, batch_id))
            self._conn.commit()

    def succeeded_t2i_in_batch(self, batch_id: str) -> list[dict[str, Any]]:
        """读取一批里已经入库的文生图。"""
        with self._lock:
            return self._all(
                """
                SELECT * FROM samples
                WHERE batch_id = ? AND modality = 't2i' AND status = 'succeeded'
                ORDER BY created_at
                """,
                (batch_id,),
            )
