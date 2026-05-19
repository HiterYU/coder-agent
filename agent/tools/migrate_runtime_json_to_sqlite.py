from __future__ import annotations

# 文件用途：命令行迁移旧版运行时 JSON 数据到 projects/agent.db。

import argparse
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.runtime_migration import migrate_project_runtime


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    参数:
        无。

    返回值:
        argparse.ArgumentParser: 迁移命令参数解析器。
    """
    parser = argparse.ArgumentParser(
        description="把旧版 projects/runtime.json 和 .runtime JSON 数据迁移到 projects/agent.db。"
    )
    parser.add_argument(
        "--project-dir",
        default=str(PROJECT_DIR),
        help="agent 项目目录，默认是当前脚本所在项目。",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="覆盖 SQLite 中已存在的同 ID 记录；默认跳过已有记录。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """执行运行时数据迁移命令。

    参数:
        argv: 可选命令行参数列表；为空时读取 sys.argv。

    返回值:
        int: 进程退出码，0 表示成功。
    """
    args = build_parser().parse_args(argv)
    project_dir = Path(args.project_dir).resolve()
    summary = migrate_project_runtime(project_dir, overwrite=args.overwrite)

    print(f"项目目录: {project_dir}")
    print(f"目标数据库: {project_dir / 'projects' / 'agent.db'}")
    print(f"扫描来源: {', '.join(summary.sources) if summary.sources else '无旧数据目录'}")
    print(f"导入数量: {summary.imported}")
    print(f"跳过数量: {summary.skipped}")
    if summary.errors:
        print("错误:")
        for error in summary.errors:
            print(f"- {error}")
        return 1
    print(f"迁移完成: 写入 {summary.total_imported()} 条记录")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
