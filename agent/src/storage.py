from __future__ import annotations

# 文件用途：提供静态 JSON 文件存储，运行时数据由 SQLite 仓库负责。

import json
from pathlib import Path
from typing import Any


class JsonStorage:
    """普通 JSON 文件存储。

    参数:
        base_dir: 存储根目录。

    返回值:
        无。实例化后可按相对路径读写 JSON。
    """

    def __init__(self, base_dir: str | Path):
        """初始化普通 JSON 文件存储。

        参数:
            base_dir: 存储根目录。

        返回值:
            无。
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def load_json(self, relative_path: str, default: Any) -> Any:
        """读取 JSON 文件。

        参数:
            relative_path: 相对存储根目录的文件路径。
            default: 文件不存在时返回的默认值。

        返回值:
            Any: JSON 解析结果或默认值。
        """
        path = self.base_dir / relative_path
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save_json(self, relative_path: str, data: Any) -> None:
        """保存 JSON 文件。

        参数:
            relative_path: 相对存储根目录的文件路径。
            data: 可 JSON 序列化的数据。

        返回值:
            无。
        """
        path = self.base_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
