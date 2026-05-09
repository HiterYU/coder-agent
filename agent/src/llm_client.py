from __future__ import annotations

# 文件用途：封装 OpenAI-compatible LLM 调用，提供文本与 JSON 响应能力。

import json
from pathlib import Path
from typing import Any

from .agent_instructions import AgentInstructionLoader
from .config import load_openai_config
from .tools import ToolRegistry, build_default_tool_registry


class LlmClient:
    """LLM 客户端封装。

    参数:
        config_path: 可选配置文件路径；未传入时读取项目根目录 config.toml。
        agents_dir: 可选 Agent 指令目录；未传入时读取项目根目录 agents。
        model: 可选模型名称；未传入时读取配置文件。
        base_url: 可选自定义 API 地址；未传入时读取配置文件。
        api_key: 可选 API Key；未传入时读取配置文件。

    返回值:
        无。实例化后可通过 complete_text 和 complete_json 发起请求。
    """

    def __init__(
        self,
        config_path: str | Path | None = None,
        agents_dir: str | Path | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        """初始化 OpenAI-compatible 客户端。

        参数:
            config_path: 可选配置文件路径；默认使用项目根目录 config.toml。
            agents_dir: 可选 Agent 指令目录；默认使用项目根目录 agents。
            model: 可选模型名称；默认使用配置文件中的 openai.model。
            base_url: 可选自定义 API 地址；默认使用配置文件中的 openai.base_url。
            api_key: 可选 API Key；默认使用配置文件中的 openai.api_key。

        返回值:
            无。
        """
        project_dir = Path(__file__).resolve().parents[1]
        if config_path is None:
            config_path = project_dir / "config.toml"
        if agents_dir is None:
            agents_dir = project_dir / "agents"
        self.config_path = Path(config_path)
        config = load_openai_config(self.config_path)
        self.instruction_loader = AgentInstructionLoader(agents_dir)
        self.tool_registry: ToolRegistry = build_default_tool_registry(project_dir)
        # 最近一次 LLM 调用实际加载的 Skill 名称，用于 UI 展示。
        self.last_used_skills: list[str] = []
        # 最近一次 LLM 调用实际执行的工具名称，用于 UI 展示和审计。
        self.last_used_tools: list[str] = []
        # LLM 初始化状态说明，用于 UI 展示和排查配置问题。
        self.status_message = "未初始化。"
        # 最近一次 LLM 调用失败原因。
        self.last_error = ""

        # 模型名称，来自 config.toml，允许测试或调用方通过参数覆盖。
        self.model = model or config.model
        # API Key，未配置时客户端不可用并自动走本地兜底逻辑。
        self.api_key = api_key or config.api_key
        # OpenAI-compatible 服务地址，适配代理或第三方兼容接口。
        self.base_url = base_url or config.base_url
        # SDK 客户端实例；初始化失败时保持为 None。
        self._client = None
        if not self.config_path.exists() and api_key is None:
            self.status_message = f"未启用：缺少配置文件 {self.config_path.name}。"
            return
        if not self.api_key:
            self.status_message = "未启用：config.toml 中没有 openai.api_key。"
            return

        try:
            from openai import OpenAI

            client_options: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                client_options["base_url"] = self.base_url
            self._client = OpenAI(**client_options)
            self.status_message = f"可用：模型 {self.model}。"
        except Exception as exc:
            self._client = None
            self.status_message = f"不可用：OpenAI SDK 初始化失败：{exc}"

    @property
    def available(self) -> bool:
        """判断 LLM 客户端是否可用。

        参数:
            无。

        返回值:
            bool: True 表示已成功初始化 SDK 客户端。
        """
        return self._client is not None

    def complete_text(self, system: str, user: str, agent_name: str | None = None) -> str | None:
        """请求模型生成文本。

        参数:
            system: 系统提示词。
            user: 用户提示词。
            agent_name: 可选 Agent 名称；传入时会先加载对应 agent.md 和 skills.md。

        返回值:
            str | None: 成功时返回模型文本，失败时返回 None。
        """
        if not self._client:
            self.last_used_skills = []
            self.last_used_tools = []
            self.last_error = self.status_message
            return None
        try:
            prompt_result = self.instruction_loader.build_system_prompt(
                agent_name, system, user
            )
            self.last_used_skills = prompt_result.used_skills
            self.last_used_tools = []
            try:
                response = self._create_response_with_tools(
                    prompt_result.system_prompt, user, agent_name
                )
            except Exception:
                self.last_used_tools = []
                response = self._client.responses.create(
                    model=self.model,
                    instructions=prompt_result.system_prompt,
                    input=[
                        {"role": "user", "content": user},
                    ],
                )
            self.last_error = ""
            return _response_output_text(response)
        except Exception as exc:
            self.last_used_skills = []
            self.last_used_tools = []
            self.last_error = f"LLM 调用失败：{exc}"
            return None

    def _create_response_with_tools(self, system_prompt: str, user: str, agent_name: str | None):
        """调用 Responses API，并在模型请求时执行本地工具。

        参数:
            system_prompt: 拼接后的系统提示词。
            user: 用户提示词。
            agent_name: 当前 Agent 名称。

        返回值:
            Any: 最终模型响应对象。
        """
        tools = self.tool_registry.schemas_for_agent(agent_name)
        conversation: list[Any] = [{"role": "user", "content": user}]

        for _ in range(4):
            request_args: dict[str, Any] = {
                "model": self.model,
                "instructions": system_prompt,
                "input": conversation,
            }
            if tools:
                request_args["tools"] = tools

            response = self._client.responses.create(**request_args)
            tool_calls = _extract_tool_calls(response)
            if not tool_calls:
                return response

            for call in tool_calls:
                conversation.append(
                    {
                        "type": "function_call",
                        "call_id": call["call_id"],
                        "name": call["name"],
                        "arguments": call["arguments"],
                    }
                )
                tool_result = self.tool_registry.execute(call["name"], call["arguments"])
                self.last_used_tools.append(call["name"])
                conversation.append(
                    {
                        "type": "function_call_output",
                        "call_id": call["call_id"],
                        "output": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

        raise RuntimeError("工具调用轮次超过限制。")

    def complete_json(
        self, system: str, user: str, agent_name: str | None = None
    ) -> dict[str, Any] | None:
        """请求模型生成 JSON 对象。

        参数:
            system: 系统提示词。
            user: 用户提示词。
            agent_name: 可选 Agent 名称；传入时会先加载对应 agent.md 和 skills.md。

        返回值:
            dict[str, Any] | None: 成功解析时返回 JSON 字典，失败时返回 None。
        """
        text = self.complete_text(system, user, agent_name=agent_name)
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    self.last_error = "LLM 返回内容不是合法 JSON。"
                    return None
        self.last_error = "LLM 返回内容不是合法 JSON。"
        return None


def _response_output_text(response) -> str:
    """提取 Responses API 响应文本。

    参数:
        response: OpenAI SDK 响应对象。

    返回值:
        str: 响应文本；无法提取时返回空字符串。
    """
    output_text = _read_field(response, "output_text")
    if isinstance(output_text, str):
        return output_text

    texts: list[str] = []
    for item in _read_field(response, "output") or []:
        if _read_field(item, "type") == "message":
            for content in _read_field(item, "content") or []:
                text = _read_field(content, "text")
                if isinstance(text, str):
                    texts.append(text)
        elif _read_field(item, "type") in {"output_text", "text"}:
            text = _read_field(item, "text")
            if isinstance(text, str):
                texts.append(text)
    return "\n".join(texts)


def _extract_tool_calls(response) -> list[dict[str, str]]:
    """从 Responses API 响应中提取 function call。

    参数:
        response: OpenAI SDK 响应对象。

    返回值:
        list[dict[str, str]]: 工具调用列表，每项包含 call_id、name 和 arguments。
    """
    tool_calls: list[dict[str, str]] = []
    for item in _read_field(response, "output") or []:
        if _read_field(item, "type") != "function_call":
            continue
        name = _read_field(item, "name")
        arguments = _read_field(item, "arguments") or "{}"
        call_id = _read_field(item, "call_id") or _read_field(item, "id")
        if isinstance(name, str) and isinstance(arguments, str) and isinstance(call_id, str):
            tool_calls.append(
                {
                    "call_id": call_id,
                    "name": name,
                    "arguments": arguments,
                }
            )
    return tool_calls


def _read_field(value, key: str):
    """兼容读取 SDK 对象或字典字段。

    参数:
        value: SDK 对象或字典。
        key: 字段名。

    返回值:
        Any: 字段值；不存在时返回 None。
    """
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
