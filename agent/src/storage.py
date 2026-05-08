from __future__ import annotations

# 文件用途：提供普通 JSON 文件存储和运行时单文件 JSON 存储。

import json
import shutil
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


class RuntimeJsonStorage(JsonStorage):
    """运行时单文件 JSON 存储。

    参数:
        base_dir: 运行时目录，默认写入该目录下的 runtime.json。

    返回值:
        无。实例化后按原相对路径接口读写，但底层集中保存到 runtime.json。
    """

    def __init__(self, base_dir: str | Path):
        """初始化运行时单文件 JSON 存储。

        参数:
            base_dir: 运行时目录。

        返回值:
            无。
        """
        super().__init__(base_dir)
        self.runtime_path = self.base_dir / "runtime.json"

    def load_json(self, relative_path: str, default: Any) -> Any:
        """从 runtime.json 的分区中读取数据。

        参数:
            relative_path: 兼容旧目录结构的相对路径，如 profiles/demo.json。
            default: 数据不存在时返回的默认值。

        返回值:
            Any: JSON 数据或默认值。
        """
        section, item_id = self._split_relative_path(relative_path)
        if section and item_id:
            runtime_data = self._load_runtime_data()
            if item_id in runtime_data.get(section, {}):
                return runtime_data[section][item_id]

        # 兼容旧版本的小文件存储，只读不再写。
        return super().load_json(relative_path, default)

    def save_json(self, relative_path: str, data: Any) -> None:
        """把运行时数据保存到 runtime.json。

        参数:
            relative_path: 兼容旧目录结构的相对路径，如 sessions/<id>.json。
            data: 可 JSON 序列化的数据。

        返回值:
            无。
        """
        section, item_id = self._split_relative_path(relative_path)
        if not section or not item_id:
            super().save_json(relative_path, data)
            return

        runtime_data = self._load_runtime_data()
        runtime_data.setdefault(section, {})
        runtime_data[section][item_id] = data
        self._save_runtime_data(runtime_data)

    def load_section(self, section: str) -> dict[str, Any]:
        """读取 runtime.json 中的完整分区。

        参数:
            section: 分区名称，如 problems、profiles、sessions、reviews。

        返回值:
            dict[str, Any]: 该分区下按 id 存储的数据。
        """
        runtime_data = self._load_runtime_data()
        values = runtime_data.get(section, {})
        return values if isinstance(values, dict) else {}

    def compact_legacy_files(self) -> None:
        """合并旧版小 JSON 文件并删除旧目录。

        参数:
            无。

        返回值:
            无。
        """
        runtime_data = self._load_runtime_data()
        changed = False

        for section in ("problems", "sessions", "profiles", "reviews"):
            section_dir = self.base_dir / section
            if not section_dir.exists() or not section_dir.is_dir():
                continue

            runtime_data.setdefault(section, {})
            for path in section_dir.glob("*.json"):
                item_id = path.stem
                if item_id in runtime_data[section]:
                    continue
                try:
                    with path.open("r", encoding="utf-8") as file:
                        runtime_data[section][item_id] = json.load(file)
                    changed = True
                except (OSError, json.JSONDecodeError):
                    continue

            shutil.rmtree(section_dir)
            changed = True

        if changed:
            self._save_runtime_data(runtime_data)

    def _split_relative_path(self, relative_path: str) -> tuple[str | None, str | None]:
        path = Path(relative_path)
        parts = path.parts
        if len(parts) != 2 or path.suffix != ".json":
            return None, None
        return parts[0], path.stem

    def _load_runtime_data(self) -> dict[str, Any]:
        if not self.runtime_path.exists():
            return self._empty_runtime_data()
        with self.runtime_path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        if not isinstance(raw, dict):
            return self._empty_runtime_data()
        for section in ("problems", "sessions", "profiles", "reviews"):
            raw.setdefault(section, {})
        return raw

    def _save_runtime_data(self, data: dict[str, Any]) -> None:
        with self.runtime_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def _empty_runtime_data(self) -> dict[str, dict]:
        return {
            "problems": {},
            "sessions": {},
            "profiles": {},
            "reviews": {},
        }
