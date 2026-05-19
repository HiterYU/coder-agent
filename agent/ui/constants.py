from __future__ import annotations

# 文件用途：集中存放 UI 层常量、标签映射和项目根路径。

from pathlib import Path


# 项目根目录，等同于 agent/。
PROJECT_DIR = Path(__file__).resolve().parent.parent

# Streamlit 代码编辑器语言到 Ace 语言模式的映射。
EDITOR_LANGUAGE_MAP = {
    "Python": "python",
    "JavaScript": "javascript",
    "Java": "java",
    "C++": "c_cpp",
}

# 会话消息类型到中文展示名称的映射。
MESSAGE_TYPE_LABELS = {
    "thought": "思路",
    "question": "问题",
    "code": "代码",
    "hint": "提示",
    "review": "复盘",
    "note": "备注",
}

# 会话状态枚举值到中文展示名称的映射。
SESSION_STATUS_LABELS = {
    "reading": "读题",
    "thinking": "思考",
    "coding": "编码",
    "debugging": "调试",
    "submitted": "已提交",
    "reviewed": "已复盘",
    "completed": "已完成",
}

# 侧边栏对话面板允许展示的消息类型集合。
SIDEBAR_DIALOG_MESSAGE_TYPES = {"thought", "question", "hint"}

# 编辑器中可选的语言列表，保持顺序便于 selectbox 索引复用。
SUPPORTED_LANGUAGES = ["Python", "JavaScript", "Java", "C++"]

# 题库筛选与目录筛选共享的难度选项。
DIFFICULTY_FILTER_OPTIONS = ["全部", "Easy", "Medium", "Hard"]
