from __future__ import annotations

# 文件用途：读取项目本地配置文件，集中管理 OpenAI-compatible LLM 和 LeetCode 抓题配置。

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


@dataclass(frozen=True)
class LeetCodeConfig:
    """LeetCode 抓题配置。

    参数:
        csrftoken: LeetCode 中国站 csrftoken。
        prefer_cn: 是否优先使用 LeetCode 中国站。
        retry_count: 请求失败时的重试次数。
        timeout: HTTP 请求超时时间，单位秒。
        category_slug: 中国站题库列表分类 slug。
        page_size: 抓题列表分页大小。

    返回值:
        无。该类用于承载 LeetCode 抓题配置。
    """

    # LeetCode 中国站 csrftoken；为空时按匿名请求处理。
    csrftoken: str | None = None
    # 是否优先请求 leetcode.cn；关闭时优先 leetcode.com。
    prefer_cn: bool = False
    # 网络失败时的最大尝试次数。
    retry_count: int = 5
    # 单次 HTTP 请求超时时间。
    timeout: int = 15
    # 中国站题库列表分类。
    category_slug: str = "all-code-essentials"
    # 中国站题库列表每页数量。
    page_size: int = 50


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


def load_leetcode_config(config_path: str | Path) -> LeetCodeConfig:
    """从 TOML 配置文件读取 LeetCode 抓题配置。

    参数:
        config_path: 项目配置文件路径。

    返回值:
        LeetCodeConfig: 解析后的 LeetCode 抓题配置。
    """
    path = Path(config_path)
    if not path.exists():
        return LeetCodeConfig()

    with path.open("rb") as file:
        raw_config = tomllib.load(file)

    raw_leetcode = raw_config.get("leetcode", {})
    if not isinstance(raw_leetcode, dict):
        return LeetCodeConfig()

    return LeetCodeConfig(
        csrftoken=_read_string(raw_leetcode, "csrftoken"),
        prefer_cn=_read_bool(raw_leetcode, "prefer_cn", False),
        retry_count=_read_int(raw_leetcode, "retry_count", 5, minimum=1),
        timeout=_read_int(raw_leetcode, "timeout", 15, minimum=1),
        category_slug=_read_string(raw_leetcode, "category_slug") or "all-code-essentials",
        page_size=_read_int(raw_leetcode, "page_size", 50, minimum=1),
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


def _read_bool(raw_config: dict, key: str, default: bool) -> bool:
    """读取配置中的布尔字段。

    参数:
        raw_config: 配置字典。
        key: 字段名称。
        default: 字段缺失或类型不匹配时的默认值。

    返回值:
        bool: 解析后的布尔值。
    """
    value = raw_config.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _read_int(raw_config: dict, key: str, default: int, minimum: int | None = None) -> int:
    """读取配置中的整数字段。

    参数:
        raw_config: 配置字典。
        key: 字段名称。
        default: 字段缺失、类型不匹配或越界时的默认值。
        minimum: 可选最小值。

    返回值:
        int: 解析后的整数。
    """
    value = raw_config.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
    else:
        return default
    if minimum is not None and parsed < minimum:
        return default
    return parsed
