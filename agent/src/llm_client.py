from __future__ import annotations

# 文件用途：封装 OpenAI-compatible LLM 调用，提供文本与 JSON 响应能力。

import json
import os
from typing import Any


class LlmClient:
    """LLM 客户端封装。

    参数:
        model: 可选模型名称；未传入时读取 OPENAI_MODEL。
        base_url: 可选自定义 API 地址；未传入时读取 OPENAI_BASE_URL。

    返回值:
        无。实例化后可通过 complete_text 和 complete_json 发起请求。
    """

    def __init__(self, model: str | None = None, base_url: str | None = None):
        """初始化 OpenAI-compatible 客户端。

        参数:
            model: 可选模型名称；默认使用 OPENAI_MODEL 或 gpt-4.1-mini。
            base_url: 可选自定义 API 地址；默认使用 OPENAI_BASE_URL。

        返回值:
            无。
        """
        # 模型名称，允许通过环境变量覆盖默认值。
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        # API Key，未配置时客户端不可用并自动走本地兜底逻辑。
        self.api_key = os.getenv("OPENAI_API_KEY")
        # OpenAI-compatible 服务地址，适配代理或第三方兼容接口。
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        # SDK 客户端实例；初始化失败时保持为 None。
        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI

                client_options: dict[str, Any] = {"api_key": self.api_key}
                if self.base_url:
                    client_options["base_url"] = self.base_url
                self._client = OpenAI(**client_options)
            except Exception:
                self._client = None

    @property
    def available(self) -> bool:
        """判断 LLM 客户端是否可用。

        参数:
            无。

        返回值:
            bool: True 表示已成功初始化 SDK 客户端。
        """
        return self._client is not None

    def complete_text(self, system: str, user: str) -> str | None:
        """请求模型生成文本。

        参数:
            system: 系统提示词。
            user: 用户提示词。

        返回值:
            str | None: 成功时返回模型文本，失败时返回 None。
        """
        if not self._client:
            return None
        try:
            response = self._client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return response.output_text
        except Exception:
            return None

    def complete_json(self, system: str, user: str) -> dict[str, Any] | None:
        """请求模型生成 JSON 对象。

        参数:
            system: 系统提示词。
            user: 用户提示词。

        返回值:
            dict[str, Any] | None: 成功解析时返回 JSON 字典，失败时返回 None。
        """
        text = self.complete_text(system, user)
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
                    return None
        return None
