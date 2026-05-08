from __future__ import annotations

# 文件用途：渐进式加载不同 Agent 的角色说明和技能约束，并拼接到 LLM 系统提示词。

from dataclasses import dataclass
from pathlib import Path
import re


AGENT_FILE_NAME = "agent.md"
SKILL_FILE_NAMES = ("skills.md", "skills.m")
SKILL_DIR_NAME = "skills"


@dataclass(frozen=True)
class SkillMetadata:
    """Skill 元数据。

    参数:
        agent_name: Agent 名称。
        path: Skill Markdown 文件路径。
        name: Skill 名称。
        description: Skill 描述。
        keywords: 用于相似判断的关键词。
        threshold: 加载全文所需的最低相似分。

    返回值:
        无。该类用于承载内存中的 Skill 元数据索引。
    """

    # Agent 名称，对应 agents 目录下的子目录。
    agent_name: str
    # Skill 文件路径，命中后才读取全文。
    path: Path
    # Skill 展示名称，用于 UI 提示。
    name: str
    # Skill 用途描述，用于轻量相似判断。
    description: str
    # Skill 关键词，用于轻量相似判断。
    keywords: tuple[str, ...]
    # 相似分达到该值时加载 Skill 全文。
    threshold: float = 1.0


@dataclass(frozen=True)
class PromptBuildResult:
    """系统提示词构建结果。

    参数:
        system_prompt: 拼接后的系统提示词。
        used_skills: 本次命中的 Skill 名称列表。

    返回值:
        无。该类用于返回提示词和 Skill 使用信息。
    """

    # 拼接后的系统提示词。
    system_prompt: str
    # 本次命中的 Skill 名称列表。
    used_skills: list[str]


class AgentInstructionLoader:
    """Agent 指令文件加载器。

    参数:
        agents_dir: 存放不同 Agent 指令目录的根路径。

    返回值:
        无。实例化后可通过 build_system_prompt 拼接系统提示词。
    """

    def __init__(self, agents_dir: str | Path):
        """初始化 Agent 指令文件加载器。

        参数:
            agents_dir: 存放不同 Agent 指令目录的根路径。

        返回值:
            无。
        """
        self.agents_dir = Path(agents_dir)
        # 启动时只读取各 Skill Markdown 的 YAML front matter，正文按需加载。
        self.skill_index = self._load_skill_index()

    def build_system_prompt(
        self, agent_name: str | None, task_system: str, user_text: str
    ) -> PromptBuildResult:
        """按固定顺序拼接 Agent 指令、命中的技能约束和本次任务指令。

        参数:
            agent_name: Agent 名称，对应 agents_dir 下的子目录名。
            task_system: 本次 LLM 调用的系统提示词。
            user_text: 用户问题或用户上下文，用于 Skill 相似判断。

        返回值:
            PromptBuildResult: 拼接后的系统提示词和命中的 Skill 名称。
        """
        if not agent_name:
            return PromptBuildResult(system_prompt=task_system, used_skills=[])

        agent_dir = self.agents_dir / agent_name
        agent_text = self._read_optional_file(agent_dir / AGENT_FILE_NAME)
        matched_skills = self._match_skills(agent_name, user_text)
        parts: list[str] = []
        used_skills: list[str] = []

        if agent_text:
            parts.append(
                "以下内容来自 agent.md。必须先读取并遵循该 Agent 的角色、边界和工作方式。\n"
                f"{agent_text}"
            )

        for skill in matched_skills:
            skill_text = self._read_skill_body(skill.path)
            if not skill_text:
                continue
            used_skills.append(f"{agent_name}/{skill.name}")
            parts.append(
                f"以下内容来自 {skill.path.name}，Skill 名称：{skill.name}。"
                "回答时必须严格遵循这些 skill 约束；"
                "如与本次任务指令冲突，以 skill 约束为准。\n"
                f"{skill_text}"
            )

        if task_system:
            parts.append(f"以下是本次调用的任务指令。\n{task_system}")

        return PromptBuildResult(
            system_prompt="\n\n".join(parts) if parts else task_system,
            used_skills=used_skills,
        )

    def _load_skill_index(self) -> dict[str, list[SkillMetadata]]:
        skill_index: dict[str, list[SkillMetadata]] = {}
        if not self.agents_dir.exists():
            return skill_index

        for agent_dir in sorted(self.agents_dir.iterdir()):
            if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
                continue
            skills = [
                self._build_skill_metadata(agent_dir.name, path)
                for path in self._find_skill_files(agent_dir)
            ]
            skill_index[agent_dir.name] = [skill for skill in skills if skill is not None]
        return skill_index

    def _find_skill_files(self, agent_dir: Path) -> list[Path]:
        skill_files = [agent_dir / file_name for file_name in SKILL_FILE_NAMES]
        nested_skill_dir = agent_dir / SKILL_DIR_NAME
        if nested_skill_dir.exists() and nested_skill_dir.is_dir():
            skill_files.extend(sorted(nested_skill_dir.glob("*.md")))
            skill_files.extend(sorted(nested_skill_dir.glob("*.m")))
        return [path for path in skill_files if path.exists() and path.is_file()]

    def _build_skill_metadata(self, agent_name: str, path: Path) -> SkillMetadata | None:
        raw_metadata = self._read_front_matter(path)
        name = _read_string(raw_metadata, "name") or path.stem
        description = _read_string(raw_metadata, "description") or ""
        keywords = tuple(_read_string_list(raw_metadata, "keywords"))
        threshold = _read_float(raw_metadata, "threshold") or 1.0

        if not description and not keywords:
            keywords = (agent_name, name)

        return SkillMetadata(
            agent_name=agent_name,
            path=path,
            name=name,
            description=description,
            keywords=keywords,
            threshold=threshold,
        )

    def _read_front_matter(self, path: Path) -> dict:
        try:
            with path.open("r", encoding="utf-8") as file:
                first_line = file.readline()
                if first_line.strip() != "---":
                    return {}

                yaml_lines: list[str] = []
                for line in file:
                    if line.strip() == "---":
                        break
                    yaml_lines.append(line.rstrip("\n"))
        except OSError:
            return {}

        return _parse_simple_yaml(yaml_lines)

    def _match_skills(self, agent_name: str, user_text: str) -> list[SkillMetadata]:
        normalized_user_text = user_text.lower()
        user_tokens = set(_tokenize(normalized_user_text))
        scored_skills: list[tuple[float, SkillMetadata]] = []

        for skill in self.skill_index.get(agent_name, []):
            score = self._score_skill(skill, normalized_user_text, user_tokens)
            if score >= skill.threshold:
                scored_skills.append((score, skill))

        scored_skills.sort(key=lambda item: item[0], reverse=True)
        return [skill for _, skill in scored_skills]

    def _score_skill(
        self, skill: SkillMetadata, normalized_user_text: str, user_tokens: set[str]
    ) -> float:
        score = 0.0
        for keyword in skill.keywords:
            normalized_keyword = keyword.lower().strip()
            if normalized_keyword and normalized_keyword in normalized_user_text:
                score += 1.0

        description_tokens = set(_tokenize(skill.description.lower()))
        if description_tokens and user_tokens:
            score += len(description_tokens & user_tokens) / max(len(description_tokens), 1)

        return score

    def _read_skill_body(self, path: Path) -> str:
        text = self._read_optional_file(path)
        if not text.startswith("---"):
            return text

        parts = text.split("---", 2)
        if len(parts) < 3:
            return text
        return parts[2].strip()

    def _read_optional_file(self, path: Path) -> str:
        if not path.exists() or not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""


def _parse_simple_yaml(lines: list[str]) -> dict:
    data: dict[str, str | float | list[str]] = {}
    current_list_key: str | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- ") and current_list_key:
            value = _strip_yaml_quotes(stripped[2:].strip())
            if isinstance(data.get(current_list_key), list):
                data[current_list_key].append(value)
            continue

        if ":" not in stripped:
            current_list_key = None
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        if not value:
            data[key] = []
            current_list_key = key
            continue

        current_list_key = None
        data[key] = _coerce_yaml_scalar(value)

    return data


def _coerce_yaml_scalar(value: str) -> str | float | list[str]:
    value = _strip_yaml_quotes(value)
    if value.startswith("[") and value.endswith("]"):
        items = [item.strip() for item in value[1:-1].split(",") if item.strip()]
        return [_strip_yaml_quotes(item) for item in items]

    try:
        return float(value)
    except ValueError:
        return value


def _strip_yaml_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _read_string(raw_metadata: dict, key: str) -> str | None:
    value = raw_metadata.get(key)
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


def _read_string_list(raw_metadata: dict, key: str) -> list[str]:
    value = raw_metadata.get(key)
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def _read_float(raw_metadata: dict, key: str) -> float | None:
    value = raw_metadata.get(key)
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", text.lower())
