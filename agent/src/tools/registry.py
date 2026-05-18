from __future__ import annotations

# 文件用途：定义 LLM 可调用工具的上下文、元数据、注册表和执行入口。

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ToolHandler = Callable[[dict[str, Any], "ToolContext"], dict[str, Any]]


@dataclass(frozen=True)
class ToolContext:
    """工具执行上下文。

    参数:
        project_dir: 项目根目录。

    返回值:
        无。该类用于向工具提供数据目录和运行时目录路径。
    """

    # 项目根目录。
    project_dir: Path

    @property
    def data_dir(self) -> Path:
        """返回内置数据目录。

        参数:
            无。

        返回值:
            Path: `data/` 目录路径。
        """
        return self.project_dir / "data"

    @property
    def runtime_dir(self) -> Path:
        """返回运行时数据目录。

        参数:
            无。

        返回值:
            Path: `projects/` 目录路径。
        """
        return self.project_dir / "projects"

    @property
    def legacy_runtime_dir(self) -> Path:
        """返回旧版运行时数据目录。

        参数:
            无。

        返回值:
            Path: `.runtime/` 目录路径，用于迁移旧数据。
        """
        return self.project_dir / ".runtime"


@dataclass(frozen=True)
class ToolDefinition:
    """LLM 工具定义。

    参数:
        name: 工具名称。
        description: 工具描述。
        parameters: JSON Schema 参数定义。
        handler: 本地执行函数。
        agent_names: 允许使用该工具的 Agent 名称集合；为空表示所有 Agent 可用。

    返回值:
        无。该类用于承载工具 schema 和本地 handler。
    """

    # 工具名称，必须和模型返回的 function call 名称一致。
    name: str
    # 给模型看的工具用途说明。
    description: str
    # 工具参数 JSON Schema。
    parameters: dict[str, Any]
    # 本地工具执行函数。
    handler: ToolHandler
    # 允许使用该工具的 Agent 名称；为空时不限制。
    agent_names: set[str] = field(default_factory=set)

    def to_openai_tool(self) -> dict[str, Any]:
        """转换为 Responses API function tool schema。

        参数:
            无。

        返回值:
            dict[str, Any]: OpenAI-compatible Responses API 工具定义。
        """
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def is_available_for(self, agent_name: str | None) -> bool:
        """判断工具是否对指定 Agent 可用。

        参数:
            agent_name: 当前调用的 Agent 名称。

        返回值:
            bool: 可用时返回 True。
        """
        return not self.agent_names or (agent_name in self.agent_names)


class ToolRegistry:
    """LLM 工具注册表。

    参数:
        context: 工具执行上下文。

    返回值:
        无。实例化后可注册工具、导出 schema 并执行工具调用。
    """

    def __init__(self, context: ToolContext):
        """初始化工具注册表。

        参数:
            context: 工具执行上下文。

        返回值:
            无。
        """
        self.context = context
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """注册一个工具。

        参数:
            tool: 工具定义。

        返回值:
            无。
        """
        self._tools[tool.name] = tool

    def schemas_for_agent(self, agent_name: str | None) -> list[dict[str, Any]]:
        """返回指定 Agent 可用的工具 schema。

        参数:
            agent_name: 当前调用的 Agent 名称。

        返回值:
            list[dict[str, Any]]: 可传给 LLM 的工具 schema 列表。
        """
        return [
            tool.to_openai_tool()
            for tool in self._tools.values()
            if tool.is_available_for(agent_name)
        ]

    def execute(self, name: str, raw_arguments: str | dict[str, Any]) -> dict[str, Any]:
        """执行模型请求的工具调用。

        参数:
            name: 工具名称。
            raw_arguments: 模型返回的 JSON 字符串或参数字典。

        返回值:
            dict[str, Any]: 标准化工具执行结果。
        """
        tool = self._tools.get(name)
        if not tool:
            return {
                "ok": False,
                "error": f"未知工具: {name}",
            }

        try:
            arguments = self._parse_arguments(raw_arguments)
            data = tool.handler(arguments, self.context)
            return {
                "ok": True,
                "tool": name,
                "data": data,
            }
        except Exception as exc:
            return {
                "ok": False,
                "tool": name,
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _parse_arguments(self, raw_arguments: str | dict[str, Any]) -> dict[str, Any]:
        """解析工具调用参数。

        参数:
            raw_arguments: 模型返回的 JSON 字符串或参数字典。

        返回值:
            dict[str, Any]: 参数字典。
        """
        if isinstance(raw_arguments, dict):
            return raw_arguments
        if not raw_arguments:
            return {}
        parsed = json.loads(raw_arguments)
        if not isinstance(parsed, dict):
            raise ValueError("工具参数必须是 JSON object。")
        return parsed
