from __future__ import annotations

# 文件用途：渲染 LLM 配置、调用诊断与本次使用的 Skill 状态。

import streamlit as st

from src.training_agent import TrainingAgent

from .state import get_agent


def render_llm_status(agent: TrainingAgent) -> None:
    """渲染 LLM 配置和调用状态。

    参数:
        agent: 训练 Agent 实例。

    返回值:
        无。
    """
    diagnostics = agent.llm.snapshot_diagnostics()
    st.subheader("LLM 状态")
    if diagnostics.available:
        st.success(diagnostics.status_message)
    else:
        st.warning(diagnostics.status_message)

    st.caption(f"配置文件: {diagnostics.config_path}")
    if diagnostics.base_url:
        st.caption(f"Base URL: {diagnostics.base_url}")
    st.caption(
        f"初始化阶段: {diagnostics.init_stage} · "
        f"最近调用阶段: {diagnostics.call_stage}"
    )
    if diagnostics.last_error:
        error_type = f" ({diagnostics.last_error_type})" if diagnostics.last_error_type else ""
        st.caption(f"最近错误{error_type}: {diagnostics.last_error}")
    if diagnostics.last_warning:
        warning_type = (
            f" ({diagnostics.last_warning_type})" if diagnostics.last_warning_type else ""
        )
        st.caption(f"最近告警{warning_type}: {diagnostics.last_warning}")
    if diagnostics.last_used_tools:
        st.caption(f"最近工具: {', '.join(diagnostics.last_used_tools)}")

    if st.button("重新加载 LLM 配置"):
        get_agent.clear()
        st.rerun()


def render_llm_call_status(agent: TrainingAgent) -> None:
    """渲染最近一次 LLM 调用状态。

    参数:
        agent: 训练 Agent 实例。

    返回值:
        无。
    """
    diagnostics = agent.llm.snapshot_diagnostics()
    if diagnostics.last_error:
        error_type = f" ({diagnostics.last_error_type})" if diagnostics.last_error_type else ""
        st.caption(
            f"LLM 未使用或调用失败: {diagnostics.last_error}"
            f"{error_type} · 阶段: {diagnostics.call_stage}"
        )
    elif diagnostics.available:
        st.caption("LLM 已参与本次生成。")
    if diagnostics.last_warning:
        warning_type = (
            f" ({diagnostics.last_warning_type})" if diagnostics.last_warning_type else ""
        )
        st.caption(f"LLM 调用告警: {diagnostics.last_warning}{warning_type}")
    if diagnostics.last_used_tools:
        st.caption(f"已调用工具: {', '.join(diagnostics.last_used_tools)}")


def render_used_skills(used_skills: list[str]) -> None:
    """渲染本次 LLM 调用实际使用的 Skill 名称。

    参数:
        used_skills: 已加载的 Skill 名称列表。

    返回值:
        无。
    """
    if used_skills:
        st.caption(f"已使用 skill: {', '.join(used_skills)}")
    else:
        st.caption("未加载额外 skill")
