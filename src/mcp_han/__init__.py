"""mcp-han：让 AI 写的中文自己过一遍校对。

核心 API 不依赖 MCP SDK，可以单独当库用：

    from mcp_han import check, fix, count

    print(fix("我们用github写了个工具, 结果...").text)
    # 我们用 GitHub 写了个工具，结果……

想要 MCP 服务端，见 ``mcp_han.server``；命令行入口是 ``mcp-han`` / ``python -m mcp_han``。
"""

from .rules import (
    RULES,
    Edit,
    Finding,
    FixResult,
    Rule,
    check,
    collect,
    count,
    fix,
    mask,
    resolve_rules,
    rules_table,
)

__version__ = "0.1.0"

__all__ = [
    "RULES",
    "Edit",
    "Finding",
    "FixResult",
    "Rule",
    "__version__",
    "check",
    "collect",
    "count",
    "fix",
    "mask",
    "resolve_rules",
    "rules_table",
]
