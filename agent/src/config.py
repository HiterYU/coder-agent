from __future__ import annotations

# 文件用途：读取项目本地配置文件，集中管理 OpenAI-compatible LLM 配置。

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class OpenAiConfig:
    """OpenAI-compatible 服务配置。

    参数:
        model: 模型名称。
        base_url: 可选自定义 API 地址。
        api_key: 可选 API Key。

    返回值:
        无。该类用于承载配置数据。
    """

    # 模型名称，用于 OpenAI Responses API 调用。
    model: str = "gpt-4.1-mini"
    # OpenAI-compatible 服务地址，适配代理或第三方兼容接口。
    base_url: str | None = None
    # API Key，未配置时客户端不可用并自动走本地兜底逻辑。
    api_key: str | None = None


def load_openai_config(config_path: str | Path) -> OpenAiConfig:
    """从 TOML 配置文件读取 OpenAI-compatible 服务配置。

    参数:
        config_path: 项目配置文件路径。

    返回值:
        OpenAiConfig: 解析后的 OpenAI-compatible 服务配置。
    """
    path = Path(config_path)
    if not path.exists():
        return OpenAiConfig()

    with path.open("rb") as file:
        raw_config = tomllib.load(file)

    raw_openai = raw_config.get("openai", {})
    if not isinstance(raw_openai, dict):
        return OpenAiConfig()

    return OpenAiConfig(
        model=_read_string(raw_openai, "model") or "gpt-4.1-mini",
        base_url=_read_string(raw_openai, "base_url"),
        api_key=_read_string(raw_openai, "api_key"),
    )


def _read_string(raw_config: dict, key: str) -> str | None:
    """读取配置中的非空字符串字段。

    参数:
        raw_config: 配置字典。
        key: 字段名称。

    返回值:
        str | None: 非空字符串；字段缺失、类型不匹配或为空时返回 None。
    """
    value = raw_config.get(key)
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
