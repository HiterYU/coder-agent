from __future__ import annotations

# 文件用途：封装 OpenAI-compatible LLM 调用，提供文本与 JSON 响应能力。

import json
from pathlib import Path
from typing import Any

from .agent_instructions import AgentInstructionLoader
from .config import load_openai_config


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
        # 最近一次 LLM 调用实际加载的 Skill 名称，用于 UI 展示。
        self.last_used_skills: list[str] = []
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
            self.last_error = self.status_message
            return None
        try:
            prompt_result = self.instruction_loader.build_system_prompt(
                agent_name, system, user
            )
            self.last_used_skills = prompt_result.used_skills
            response = self._client.responses.create(
                model=self.model,
                instructions=prompt_result.system_prompt,
                input=[
                    {"role": "user", "content": user},
                ],
            )
            self.last_error = ""
            return response.output_text
        except Exception as exc:
            self.last_used_skills = []
            self.last_error = f"LLM 调用失败：{exc}"
            return None

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
