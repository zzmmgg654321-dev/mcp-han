"""mcp-han 的 MCP 服务端。

只做四件事：检查、修复、数字数、报规则清单。
真正的逻辑都在 rules.py 里，这里只负责「把结果说成人话」。
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from . import rules as R

__all__ = ["server", "main"]

VERSION = "0.1.0"
REPO_URL = "https://github.com/zzmmgg654321-dev/mcp-han"

INSTRUCTIONS = """\
这个服务器负责「中文文本的校对与排版」。请在下面这些时机主动调用：

* 写完任何面向中文读者的内容（公众号、小红书、知乎、邮件、README、字幕）之后，
  先用 fix_text 把排版问题一次修掉，再用 check_text 复核剩下的需要人工判断的地方；
* 交付前需要卡字数（小红书标题 20 字、正文 1000 字、公众号摘要 120 字…）时用 count_text；
* 不确定某条规则管什么、或者想只跑部分规则时，用 list_rules 查。

要点：代码块、行内代码、URL、邮箱、HTML 标签、公式不会被改动；
规则面向大陆简体规范；判断不了的地方只报告、不自动改（例如引号不配对）。
"""

server = MCPServer(
    name="mcp-han",
    title="mcp-han 中文校对与排版",
    version=VERSION,
    instructions=INSTRUCTIONS,
    website_url=REPO_URL,
)

_SEVERITY_ORDER = ("error", "warn", "style")


# --------------------------------------------------------------------------- #
# 输出格式化
# --------------------------------------------------------------------------- #
def _severity_summary(findings: list[R.Finding]) -> str:
    parts = [f"{s} {sum(1 for f in findings if f.severity == s)}" for s in _SEVERITY_ORDER]
    return " / ".join(parts)


def _format_finding(item: R.Finding) -> str:
    head = f"第 {item.line} 行 · 第 {item.column} 列 · [{item.severity}] {item.title}"
    lines = [head, f"  {item.message}"]
    if item.suggestion:
        shown = item.suggestion if len(item.suggestion) <= 60 else item.suggestion[:60] + "…"
        lines.append(f"  建议：{shown!r}")
    elif item.fixable:
        lines.append("  建议：删除")
    lines.append(f"  上下文：{item.excerpt}")
    return "\n".join(lines)


def _format_check(findings: list[R.Finding], limit: int) -> str:
    if not findings:
        return "没有发现问题：这段中文的排版、标点和用词都符合规范。"
    head = f"发现 {len(findings)} 处问题（{_severity_summary(findings)}）"
    blocks = [_format_finding(f) for f in findings[:limit]]
    out = head + "\n\n" + "\n\n".join(blocks)
    if len(findings) > limit:
        out += f"\n\n…还有 {len(findings) - limit} 处，已省略（可传 rules 只跑某一类规则）"
    fixable = sum(1 for f in findings if f.fixable)
    if fixable:
        out += f"\n\n提示：其中 {fixable} 处可以直接用 fix_text 自动修掉。"
    return out


def _format_count(stats: dict) -> str:
    lines = [
        "字数统计",
        f"  总字符 {stats['chars_total']}（不含空白 {stats['chars_no_space']}）",
        f"  汉字 {stats['han']} · 中文标点 {stats['cjk_punctuation']} · "
        f"英文单词 {stats['latin_words']} · 拉丁字母 {stats['latin_letters']} · 数字 {stats['digits']}",
        f"  段落 {stats['paragraphs']} · 句子 {stats['sentences']} · 行 {stats['lines']}",
        f"  预计精读 {stats['reading_minutes']} 分钟（按每分钟 300 汉字估）",
        "",
        "平台字数（按非空白字符计）",
    ]
    for p in stats["platforms"]:
        if p["status"] == "over":
            tail = f"超出 {-p['remaining']}"
        else:
            tail = f"还剩 {p['remaining']}"
        mark = "✗" if p["status"] == "over" else ("△" if p["status"] == "near" else "✓")
        note = f"（{p['note']}）" if p["note"] else ""
        lines.append(f"  {mark} {p['name']:<6} {p['used']} / {p['limit']}  {tail}{note}")
    return "\n".join(lines)


def _format_rules() -> str:
    lines = [
        f"共 {len(R.RULES)} 条规则。默认跑「默认」那一列标了 ✓ 的；",
        "想点名某条规则（例如默认关闭的 quote-switch）写进 rules 参数即可。",
        "",
    ]
    for item in R.rules_table():
        flags = ["可修" if item["fixable"] else "只报告"]
        if item["auto_fix"]:
            flags.append("自动")
        if not item["default"]:
            flags.append("点名才跑")
        lines.append(
            f"  {item['id']:<18} [{item['severity']:<5}] {'/'.join(flags):<16} {item['title']}"
        )
        lines.append(f"  {'':<18} {item['detail']}")
    return "\n".join(lines)


def _json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def check_text(text: str, rules: str = "", severity: str = "", limit: int = 30) -> str:
    """检查中文文本的排版、标点、常见错别字和专有名词大小写。

    这是只读操作，不会修改任何东西。

    Args:
        text: 要检查的文本。Markdown 也行；代码块、行内代码、URL、邮箱、
            HTML 标签和公式会被自动跳过。
        rules: 只跑指定规则，逗号分隔（如 "typo,pangu-space"）；用 "-" 前缀排除
            （如 "-dup-punct"）；留空表示默认规则集（18 条里除 quote-switch 之外的全部）。
        severity: 只看某个级别，逗号分隔，可选 error / warn / style。
        limit: 最多列出多少条问题，默认 30。
    """

    try:
        findings = R.check(text, rules=rules or None, severity=severity)
    except ValueError as exc:
        return f"参数有误：{exc}"
    return _format_check(findings, max(1, limit))


def fix_text(text: str, rules: str = "", quote_style: str = "curly") -> str:
    """自动修复中文文案的排版问题，返回修复后的全文。

    默认只套用「安全」规则（不会动代码块、行内代码、URL），
    并会告诉你改了哪些地方、还有哪些需要人工确认。

    Args:
        text: 要修复的文本。
        rules: 只跑指定规则，逗号分隔；用 "-" 前缀排除。点名某条平时不自动跑的
            规则（例如 "dup-punct"）时它也会被套用。
        quote_style: 引号风格——curly（默认，“”）/ corner（「」）/ keep（不动）。
    """

    spec = rules or None
    try:
        result = R.fix(text, rules=spec, quote_style=quote_style)
        remaining = R.check(result.text, rules=spec, quote_style=quote_style)
    except ValueError as exc:
        return f"参数有误：{exc}"

    if not result.changed:
        tail = _format_check(remaining, 10) if remaining else "没有发现问题。"
        return f"没有需要自动修复的地方。\n\n{tail}"

    parts = [f"已修复 {len(result.changes)} 处。", "", "【修复后的全文】", result.text, "",
             "【改动清单】"]
    parts += [_format_finding(f) for f in result.changes[:40]]
    if len(result.changes) > 40:
        parts.append(f"…另有 {len(result.changes) - 40} 处未列出。")
    parts += ["", "【仍需人工确认】", _format_check(remaining, 10)]
    return "\n".join(parts)


def count_text(text: str, platforms: str = "") -> str:
    """统计字数、段落、句子、预计阅读时长，并检查常见平台的字数限制。

    具体平台（小红书、公众号、短信、X）的超限情况会一起返回。

    Args:
        text: 要统计的文本。
        platforms: 只看指定平台，逗号分隔，如 "xhs_title,mp_digest"；留空表示全部。
    """

    try:
        stats = R.count(text, platforms=platforms or None)
    except ValueError as exc:
        return f"参数有误：{exc}"
    return _format_count(stats)


def list_rules() -> str:
    """列出全部校对规则（id、级别、能否自动修复、说明）。

    想知道 rules 参数里能写什么，或者想了解某条规则的边界时用这个。
    """

    return _format_rules()


server.tool()(check_text)
server.tool()(fix_text)
server.tool()(count_text)
server.tool()(list_rules)


def main() -> None:
    """以 stdio 方式启动（MCP 客户端的标准接入方式）。"""

    server.run("stdio")
