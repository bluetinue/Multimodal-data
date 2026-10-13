"""媒体文件存储。对象存储实现替换这个类即可。"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from studio.config import ROOT


class LocalMediaStore:
    """把图片和视频写到按日期划分的本地目录。"""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root

    def _day_dir(self, kind: str) -> Path:
        day = datetime.now().astimezone().date().isoformat()
        folder = self.root / kind / day
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def save(self, kind: str, sample_id: str, suffix: str, content: bytes) -> str:
        """保存文件并返回相对仓库根目录的路径。"""
        if kind not in {"picture", "video"}:
            raise ValueError("媒体类型只能是 picture 或 video")
        filename = f"{sample_id}{suffix}"
        target = self._day_dir(kind) / filename
        target.write_bytes(content)
        return target.relative_to(self.root).as_posix()

    def read(self, relative_path: str) -> bytes:
        """按相对路径读取媒体。"""
        path = self.resolve(relative_path)
        return path.read_bytes()

    def resolve(self, relative_path: str) -> Path:
        """把相对路径解析到 picture 或 video 目录内。"""
        path = (self.root / relative_path).resolve()
        picture = (self.root / "picture").resolve()
        video = (self.root / "video").resolve()
        if picture not in path.parents and video not in path.parents:
            raise ValueError("媒体路径超出数据目录")
        return path

    @staticmethod
    def sha256(content: bytes) -> str:
        """计算文件哈希。"""
        return hashlib.sha256(content).hexdigest()
