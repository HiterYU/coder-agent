from __future__ import annotations

# 文件用途：回归验证 LLM 客户端会暴露清晰的初始化、调用和解析诊断信息。

import json
from pathlib import Path
from types import SimpleNamespace

from src.llm_client import LlmClient


def test_llm_client_reports_missing_api_key(tmp_path: Path) -> None:
    """验证缺少 API Key 时能暴露明确的不可用阶段。

    参数:
        tmp_path: pytest 临时目录。

    返回值:
        无。
    """
    config_path = tmp_path / "settings.json"
    config_path.write_text(json.dumps({"openai": {"model": "test-model"}}), encoding="utf-8")

    client = LlmClient(config_path=config_path)
    diagnostics = client.snapshot_diagnostics()

    assert client.complete_text("system", "user") is None
    assert not diagnostics.available
    assert diagnostics.init_stage == "api_key_missing"
    assert "openai.api_key" in diagnostics.last_error
    assert client.snapshot_diagnostics().call_stage == "client_unavailable"


def test_llm_client_reports_empty_response(tmp_path: Path) -> None:
    """验证空响应会被标记为 empty_response。

    参数:
        tmp_path: pytest 临时目录。

    返回值:
        无。
    """
    client = _available_client(tmp_path, _FakeResponsesClient(""))

    assert client.complete_text("system", "user") is None
    diagnostics = client.snapshot_diagnostics()
    assert diagnostics.call_stage == "empty_response"
    assert diagnostics.last_error_type == "empty_response"
    assert "返回内容为空" in diagnostics.last_error


def test_llm_client_reports_json_parse_failure(tmp_path: Path) -> None:
    """验证 JSON 解析失败时能保留解析阶段和错误类型。

    参数:
        tmp_path: pytest 临时目录。

    返回值:
        无。
    """
    client = _available_client(tmp_path, _FakeResponsesClient("不是 JSON"))

    assert client.complete_json("system", "user") is None
    diagnostics = client.snapshot_diagnostics()
    assert diagnostics.call_stage == "json_parse_failed"
    assert diagnostics.last_error_type == "JSONDecodeError"
    assert "不是合法 JSON" in diagnostics.last_error


def test_llm_client_preserves_tool_fallback_warning(tmp_path: Path) -> None:
    """验证工具调用链失败但无工具请求成功时会保留非致命告警。

    参数:
        tmp_path: pytest 临时目录。

    返回值:
        无。
    """
    client = _available_client(tmp_path, _FakeResponsesClient("最终文本"))

    def raise_tool_request(*args, **kwargs):
        raise RuntimeError("工具链异常")

    client._create_response_with_tools = raise_tool_request

    assert client.complete_text("system", "user") == "最终文本"
    diagnostics = client.snapshot_diagnostics()
    assert diagnostics.call_stage == "completed"
    assert diagnostics.last_error == ""
    assert diagnostics.last_warning_type == "tool_request_failed"
    assert "已回退为无工具请求" in diagnostics.last_warning


def _available_client(tmp_path: Path, fake_client: object) -> LlmClient:
    """创建一个可用但使用假 Responses 客户端的 LlmClient。

    参数:
        tmp_path: pytest 临时目录。
        fake_client: 替换 SDK 客户端的测试对象。

    返回值:
        LlmClient: 已注入假客户端的 LLM 客户端。
    """
    config_path = tmp_path / "settings.json"
    config_path.write_text(
        json.dumps({"openai": {"api_key": "test-key", "model": "test-model"}}),
        encoding="utf-8",
    )
    client = LlmClient(config_path=config_path)
    client._client = fake_client
    client._mark_available("可用：模型 test-model。")
    return client


class _FakeResponsesClient:
    """测试用 OpenAI SDK 客户端替身。

    参数:
        output_text: 模拟 Responses API 返回文本。

    返回值:
        无。实例化后提供 responses.create 接口。
    """

    def __init__(self, output_text: str):
        """初始化测试客户端替身。

        参数:
            output_text: 模拟 Responses API 返回文本。

        返回值:
            无。
        """
        self.responses = SimpleNamespace(create=self._create)
        # 模拟 Responses API 的 output_text 字段。
        self.output_text = output_text

    def _create(self, **kwargs):
        """模拟 Responses API create 调用。

        参数:
            kwargs: 调用参数，本测试不使用。

        返回值:
            SimpleNamespace: 带 output_text 和 output 的响应对象。
        """
        return SimpleNamespace(output_text=self.output_text, output=[])
