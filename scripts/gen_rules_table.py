"""从 RULES 重新生成 README 里的规则表，避免文档和代码不同步。

用法：

    uv run python scripts/gen_rules_table.py          # 写回 README.md
    uv run python scripts/gen_rules_table.py --check  # 只检查是否一致（CI 用）
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from mcp_han import rules as R

START = "<!-- RULES-TABLE:START -->"
END = "<!-- RULES-TABLE:END -->"
README = Path(__file__).resolve().parent.parent / "README.md"


def _default_cell(rule: R.Rule) -> str:
    if not rule.default:
        return "点名才跑"
    if rule.fixable and rule.auto:
        return "✅ 自动修"
    return "只报告"


def _title(rule: R.Rule) -> str:
    from mcp_han.data import LATIN_CASE_TERMS, TYPOS

    sizes = {"typo": len(TYPOS), "latin-case": len(LATIN_CASE_TERMS)}
    if rule.id in sizes:
        return f"{rule.title}（{sizes[rule.id]} 条词表）"
    return rule.title


def build_table() -> str:
    rows = ["| 规则 id | 检查项 | 级别 | 默认 |", "| --- | --- | --- | :---: |"]
    for rule in R.RULES.values():
        rows.append(
            f"| `{rule.id}` | {_title(rule)} | {rule.severity} | {_default_cell(rule)} |"
        )
    return "\n".join(rows)


def main() -> int:
    text = README.read_text(encoding="utf-8")
    table = build_table()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        print(f"README 里找不到 {START} / {END} 标记", file=sys.stderr)
        return 2
    updated = pattern.sub(f"{START}\n{table}\n{END}", text)

    if "--check" in sys.argv:
        if updated != text:
            print("README 的规则表和 RULES 不一致，请跑一次 scripts/gen_rules_table.py")
            return 1
        print(f"规则表与代码一致（{len(R.RULES)} 条）")
        return 0

    if updated == text:
        print(f"规则表已是最新（{len(R.RULES)} 条），无需改动")
        return 0
    README.write_text(updated, encoding="utf-8")
    print(f"已更新 README 规则表：{len(R.RULES)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
