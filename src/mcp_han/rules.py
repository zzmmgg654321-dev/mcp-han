"""mcp-han 的中文校对与排版引擎 —— 纯标准库，零第三方依赖。

三条设计原则
------------
1. **掩码（mask）**：先把围栏代码块、行内代码、URL、邮箱、HTML 标签、公式替换成
   同长度的 ``\\x00`` 占位符（换行保留）。规则只在掩码文本上匹配，所以
   offset / 行号 / 列号与原文严格对齐，而且永远不会去改你的代码。
2. **Edit**：每条规则只产出 ``Edit(start, end, replacement)``，自己不动文本。
   ``fix()`` 统一从后往前套用，并丢掉互相重叠的编辑，因此结果稳定且幂等。
3. **replacement=None** 表示「只能报告、不能自动修」（例如引号不配对）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterator, Sequence

from .data import LATIN_CASE_TERMS, PLATFORMS, TYPOS

__all__ = [
    "Edit",
    "Finding",
    "FixResult",
    "Rule",
    "RULES",
    "check",
    "count",
    "fix",
    "mask",
    "rules_table",
]


# --------------------------------------------------------------------------- #
# 规则清单
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rule:
    """一条规则的元信息。"""

    id: str
    title: str
    severity: str  # error | warn | style
    fixable: bool  # 是否能给出自动修复
    auto: bool  # 是否属于「默认自动修复」集合
    detail: str
    default: bool = True  # 是否属于默认规则集；False = 必须点名才跑


RULES: dict[str, Rule] = {
    r.id: r
    for r in (
        Rule("typo", "常见错别字 / 成语误写", "error", True, True,
             "对照内置的保守词表；只收录高置信度的错误写法，减少误报。"),
        Rule("latin-case", "专有名词大小写", "warn", True, True,
             "GitHub / JavaScript / Wi-Fi 这类专有名词的规范大小写。"),
        Rule("pangu-space", "中英文之间空格", "style", True, True,
             "汉字与拉丁字母、数字之间补一个半角空格（盘古之白）。"),
        Rule("punct-halfwidth", "半角标点", "style", True, True,
             "中文语境里用了 , . ! ? : ; 这些半角标点。"),
        Rule("paren-halfwidth", "半角括号", "style", True, True,
             "中文语境里用了半角圆括号。"),
        Rule("ellipsis", "省略号写法", "style", True, True,
             "中文省略号是「……」，即两个 U+2026；「...」「。。。」都不对。"),
        Rule("dash", "破折号写法", "style", True, True,
             "中文破折号是「——」，即两个 U+2014。"),
        Rule("quote-style", "引号风格", "style", True, True,
             "半角直引号 \" \" 应改成中文弯引号“ ”；用 quote_style 可改成「」。"),
        Rule("quote-switch", "引号风格切换", "style", True, False,
             "把已经写成“ ”或「」的引号整体切换成另一种风格。默认不跑，"
             "避免把有意使用直角引号的文档误报一遍；需要时点名 rules=\"quote-switch\"。",
             default=False),
        Rule("fullwidth-alnum", "全角字母数字", "style", True, True,
             "从 PDF、微信、邮件里复制来的全角 ＡＢＣ１２３ 应转半角。"),
        Rule("punct-space", "标点前多余空格", "style", True, True,
             "「你好 ，世界」这类中文标点前的空格。"),
        Rule("space-after-punct", "标点后多余空格", "style", True, True,
             "「你好， 世界」这类中文标点后的空格（半角逗号习惯留下的）。"),
        Rule("bracket-padding", "括号内多余空格", "style", True, True,
             "「（ 内容 ）」内侧的空格。"),
        Rule("percent-space", "百分号前空格", "style", True, True,
             "「50 %」应写成「50%」。"),
        Rule("trailing-space", "行尾空白", "style", True, True,
             "行尾多余的空格或制表符。"),
        Rule("dup-punct", "重复标点", "style", True, False,
             "「！！」「？？」这类连用。默认只报告不自动改，因为网文里可能是刻意的。"),
        Rule("fullwidth-space", "全角空格", "style", False, False,
             "U+3000；如果是有意做段首缩进，可以忽略。"),
        Rule("unpaired-quote", "引号不配对", "warn", False, False,
             "整段里直引号数量是奇数。跨行的引号不会被自动转换，需要人工确认。"),
    )
}

#: 默认参与 `fix()` 的规则
DEFAULT_FIX: frozenset[str] = frozenset(
    rid for rid, r in RULES.items() if r.fixable and r.auto
)


# --------------------------------------------------------------------------- #
# 掩码：把不该动的区域盖住
# --------------------------------------------------------------------------- #
_NULL = "\x00"
_HAN = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3005\u3007"
_HAN_RE = re.compile(f"[{_HAN}]")
_HAN_END = re.compile(f"[{_HAN}]$")

#: (正则, 是否要求匹配内容里不能出现汉字)
_PROTECTED: tuple[tuple[re.Pattern[str], bool], ...] = (
    (re.compile(r"```.*?```", re.S), False),  # 围栏代码块
    (re.compile(r"~~~.*?~~~", re.S), False),
    (re.compile(r"`[^`\n]*`"), False),  # 行内代码
    (re.compile(rf"https?://[^\s<>\"'，。；！？（）【】{_HAN}]+"), False),  # URL
    (re.compile(rf"www\.[^\s<>\"'，。；！？（）【】{_HAN}]+"), False),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), False),  # 邮箱
    (re.compile(r"<[^<>\n]{1,300}>"), False),  # HTML / XML 标签
    (re.compile(r"\$[^$\n]{1,200}\$"), True),  # 行内公式（含汉字则不当公式）
)


def mask(text: str) -> str:
    """把不该被规则碰的区域替换成同长度占位符，换行保留。

    这样规则的 offset 与原文一一对应，行号列号不用做任何换算。
    """

    chars = list(text)
    for pattern, ascii_only in _PROTECTED:
        for m in pattern.finditer(text):
            if ascii_only and _HAN_RE.search(m.group()):
                continue
            for i in range(m.start(), m.end()):
                if chars[i] != "\n":
                    chars[i] = _NULL
    return "".join(chars)


#: 全角字母数字 → 半角。长度一一对应，所以折叠后 offset 依然对齐原文。
_WIDE_ALNUM = str.maketrans(
    {
        chr(code): chr(code - 0xFEE0)
        for code in (
            list(range(0xFF21, 0xFF3B))  # Ａ-Ｚ
            + list(range(0xFF41, 0xFF5B))  # ａ-ｚ
            + list(range(0xFF10, 0xFF1A))  # ０-９
        )
    }
)


def _fold_wide(s: str) -> str:
    """把全角字母数字折成半角（只折字母数字，标点保持原样）。

    给「中英文空格」「专有名词大小写」两条规则用，这样 ``ＧＩＴＨＵＢ中文``
    一轮就能同时修好大小写和空格，不需要跑第二遍。
    """

    return s.translate(_WIDE_ALNUM)


# --------------------------------------------------------------------------- #
# 编辑 / 发现
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Edit:
    """一处修改建议。``replacement is None`` 表示不可自动修。"""

    start: int
    end: int
    replacement: str | None
    rule: str
    message: str


@dataclass(frozen=True)
class Finding:
    """面向读者的一处问题。"""

    rule: str
    title: str
    severity: str
    line: int
    column: int
    excerpt: str
    message: str
    suggestion: str | None
    fixable: bool


@dataclass(frozen=True)
class FixResult:
    """``fix()`` 的返回值。"""

    text: str
    changes: list[Finding] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.changes)


# --------------------------------------------------------------------------- #
# 各条规则的实现：签名统一为 (text, masked, opts) -> Iterator[Edit]
# --------------------------------------------------------------------------- #
def _rule_typo(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    for bad, good in TYPOS.items():
        pos = 0
        while True:
            i = masked.find(bad, pos)
            if i < 0:
                break
            pos = i + 1
            msg = f"「{bad}」应为「{good}」"
            yield Edit(i, i + len(bad), good, "typo", msg)


_LATIN_KEYS = sorted(LATIN_CASE_TERMS, key=len, reverse=True)
# 前后都不能紧挨着字母数字、下划线、连字符或点：
# 「mcp-han」「node.js」「my-github-fork」这类名字不该被改，「用github」才该被改
_LATIN_RE = re.compile(
    r"(?<![A-Za-z0-9_.\-])("
    + "|".join(re.escape(k) for k in _LATIN_KEYS)
    + r")(?![A-Za-z0-9_.\-])",
    re.IGNORECASE,
)


def _rule_latin_case(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    for m in _LATIN_RE.finditer(_fold_wide(masked)):
        raw = m.group(1)
        want = LATIN_CASE_TERMS.get(raw.lower())
        if want is None or raw == want:
            continue
        yield Edit(m.start(1), m.end(1), want, "latin-case", f"「{raw}」应写作「{want}」")


_RE_PANGU_RIGHT = re.compile(f"([{_HAN}])([A-Za-z0-9])")
_RE_PANGU_LEFT = re.compile(f"([A-Za-z0-9])([{_HAN}])")


def _rule_pangu_space(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    keep_digits = bool(opts.get("space_digits", True))
    view = _fold_wide(masked)  # 全角字母数字先折成半角，一轮到位
    msg = "中英文之间应加一个空格"
    for m in _RE_PANGU_RIGHT.finditer(view):
        if m.group(2).isdigit() and not keep_digits:
            continue
        yield Edit(m.start(2), m.start(2), " ", "pangu-space", msg)
    for m in _RE_PANGU_LEFT.finditer(view):
        if m.group(1).isdigit() and not keep_digits:
            continue
        yield Edit(m.start(2), m.start(2), " ", "pangu-space", msg)


_HALF_TO_FULL = {",": "，", ".": "。", "!": "！", "?": "？", ":": "：", ";": "；"}


def _rule_punct_halfwidth(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    n = len(masked)
    for i, ch in enumerate(masked):
        full = _HALF_TO_FULL.get(ch)
        if full is None or i == 0:
            continue
        prev = masked[i - 1]
        nxt = masked[i + 1] if i + 1 < n else ""
        if prev == _NULL or nxt == _NULL:
            continue
        if not _HAN_END.match(prev):  # 只处理中文后面紧跟的标点
            continue
        if ch == "." and (nxt == "." or (nxt and nxt.isalnum())):
            continue  # 省略号 / 3.5 / 文件.js 放过
        if ch in ",:" and nxt.isdigit():
            continue  # 1,000 / 比例 1:2 放过
        yield Edit(i, i + 1, full, "punct-halfwidth", f"中文里应使用全角标点「{full}」")


def _rule_paren_halfwidth(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    n = len(masked)
    for i, ch in enumerate(masked):
        if ch == "(":
            nxt = masked[i + 1] if i + 1 < n else ""
            if _HAN_END.match(nxt):
                yield Edit(i, i + 1, "（", "paren-halfwidth", "中文语境应使用全角括号「（」")
        elif ch == ")":
            prev = masked[i - 1] if i else ""
            if prev and _HAN_END.match(prev):
                yield Edit(i, i + 1, "）", "paren-halfwidth", "中文语境应使用全角括号「）」")


def _rule_ellipsis(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    msg = "中文省略号是「……」（两个字符），不是「...」"
    for m in re.finditer(r"\.{3,}", masked):
        yield Edit(m.start(), m.end(), "……", "ellipsis", msg)
    for m in re.finditer(r"。。+", masked):
        yield Edit(m.start(), m.end(), "……", "ellipsis", msg)
    for m in re.finditer(r"…+", masked):
        if len(m.group()) != 2:
            yield Edit(m.start(), m.end(), "……", "ellipsis",
                       "中文省略号是「……」，两个 U+2026")


def _rule_dash(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    n = len(masked)
    msg = "中文破折号是「——」（两个 U+2014）"
    for m in re.finditer(r"-{2,}", masked):
        prev = masked[m.start() - 1] if m.start() else ""
        nxt = masked[m.end()] if m.end() < n else ""
        if (prev and _HAN_END.match(prev)) or _HAN_END.match(nxt):
            yield Edit(m.start(), m.end(), "——", "dash", msg)
    for m in re.finditer(r"—+", masked):
        if len(m.group()) == 2:
            continue
        prev = masked[m.start() - 1] if m.start() else ""
        nxt = masked[m.end()] if m.end() < n else ""
        if prev and _HAN_END.match(prev) and _HAN_END.match(nxt):
            yield Edit(m.start(), m.end(), "——", "dash", msg)


_QUOTE_PAIRS = {"curly": ("\u201c", "\u201d"), "corner": ("\u300c", "\u300d")}


def _rule_quote(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    style = str(opts.get("quote_style") or "curly")
    if style == "keep":
        return
    open_q, close_q = _QUOTE_PAIRS.get(style, _QUOTE_PAIRS["curly"])
    n = len(masked)

    # 1) 半角直引号 "..." → 目标风格
    for m in re.finditer(r'"([^"\n]*)"', masked):
        inner = m.group(1)
        if not inner.strip():
            continue
        left = masked[m.start() - 1] if m.start() else ""
        right = masked[m.end()] if m.end() < n else ""
        if not (_HAN_RE.search(inner) or _HAN_END.match(left) or _HAN_END.match(right)):
            continue  # 纯英文里的引号不动
        yield Edit(m.start(), m.start() + 1, open_q, "quote-style",
                   f"中文里的直引号应改为 {open_q}（左引号）")
        yield Edit(m.end() - 1, m.end(), close_q, "quote-style",
                   f"中文里的直引号应改为 {close_q}（右引号）")


def _rule_quote_switch(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    """把已经是中文引号的“ ”或「」整体换成另一种风格。

    单独做成一条默认关闭的规则：文档里有意用直角引号是合法风格，
    默认去把它们报一遍只会变成噪音。
    """

    style = str(opts.get("quote_style") or "curly")
    if style == "keep":
        return
    open_q, close_q = _QUOTE_PAIRS.get(style, _QUOTE_PAIRS["curly"])
    for pattern, current in (
        (r"\u201c([^\u201d\n]*)\u201d", "curly"),
        (r"\u300c([^\u300d\n]*)\u300d", "corner"),
    ):
        if current == style:
            continue
        for m in re.finditer(pattern, masked):
            yield Edit(m.start(), m.start() + 1, open_q, "quote-switch",
                       f"引号风格切换为 {open_q}（左引号）")
            yield Edit(m.end() - 1, m.end(), close_q, "quote-switch",
                       f"引号风格切换为 {close_q}（右引号）")


_RE_FULLWIDTH_ALNUM = re.compile(r"[Ａ-Ｚａ-ｚ０-９]+")


def _rule_fullwidth_alnum(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    for m in _RE_FULLWIDTH_ALNUM.finditer(masked):
        fixed = "".join(chr(ord(c) - 0xFEE0) for c in m.group())
        yield Edit(m.start(), m.end(), fixed, "fullwidth-alnum",
                   f"全角应写成半角：{m.group()} → {fixed}")


def _rule_punct_space(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    for m in re.finditer(r"[ \t]+(?=[，。！？：；、））」』”’】》…])", masked):
        yield Edit(m.start(), m.end(), "", "punct-space", "中文标点前不应有空格")


def _rule_space_after_punct(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    # 只在这一格后面跟汉字、或其他全角标点时删空格，
    # 这样「比例是： 1:2」这种后面跟数字的写法不会被误伤。
    # 半角标点那一支要求它前面是汉字，否则会把 "Hello, world" 也误伤。
    tail = rf"(?=[{_HAN}，。！？：；、））」』”’】》…])"
    for pattern in (
        re.compile(rf"([，。！？：；、…])([ \t]+){tail}"),
        re.compile(rf"(?<=[{_HAN}])([,.;:!?])([ \t]+){tail}"),
        # 省略号的点串后面也常带一个空格（「结果... 他说」）
        re.compile(rf"(\.{{3,}}|。{{2,}}|…{{1,}})([ \t]+){tail}"),
    ):
        for m in pattern.finditer(masked):
            yield Edit(m.start(2), m.end(2), "", "space-after-punct", "中文标点后不应有空格")


def _rule_bracket_padding(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    for m in re.finditer(r"([（「『“‘【])([ \t]+)", masked):
        yield Edit(m.start(2), m.end(2), "", "bracket-padding", "括号 / 引号内侧不应有空格")


def _rule_percent_space(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    for m in re.finditer(r"([0-9])([ \t]+)([%‰])", masked):
        yield Edit(m.start(2), m.end(2), "", "percent-space", "百分号要紧贴数字，中间不加空格")


def _rule_trailing_space(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    for m in re.finditer(r"[ \t]+(?=\n)|[ \t]+\Z", masked):
        yield Edit(m.start(), m.end(), "", "trailing-space", "行尾多余空白")


def _rule_dup_punct(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    # 注意：省略号（…… / 。。。）归 ellipsis 管，这里不碰「。」，避免两条规则打架
    for m in re.finditer(r"([！？，、；：])\1+", masked):
        yield Edit(m.start(), m.end(), m.group(1), "dup-punct", "标点重复，留一个就够")


def _rule_fullwidth_space(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    for m in re.finditer(r"\u3000", masked):
        yield Edit(m.start(), m.end(), None, "fullwidth-space",
                   "这里用了全角空格（U+3000）；如果是有意做缩进可以忽略")


def _rule_unpaired_quote(text: str, masked: str, opts: dict) -> Iterator[Edit]:
    positions = [i for i, ch in enumerate(masked) if ch == '"']
    if len(positions) % 2 == 1:
        i = positions[-1]
        yield Edit(i, i + 1, None, "unpaired-quote",
                   "直引号数量是奇数，有一处没有闭合（跨行引号不会自动转换）")


_HANDLERS: dict[str, Callable[[str, str, dict], Iterator[Edit]]] = {
    "typo": _rule_typo,
    "latin-case": _rule_latin_case,
    "pangu-space": _rule_pangu_space,
    "punct-halfwidth": _rule_punct_halfwidth,
    "paren-halfwidth": _rule_paren_halfwidth,
    "ellipsis": _rule_ellipsis,
    "dash": _rule_dash,
    "quote-style": _rule_quote,
    "quote-switch": _rule_quote_switch,
    "fullwidth-alnum": _rule_fullwidth_alnum,
    "punct-space": _rule_punct_space,
    "space-after-punct": _rule_space_after_punct,
    "bracket-padding": _rule_bracket_padding,
    "percent-space": _rule_percent_space,
    "trailing-space": _rule_trailing_space,
    "dup-punct": _rule_dup_punct,
    "fullwidth-space": _rule_fullwidth_space,
    "unpaired-quote": _rule_unpaired_quote,
}


# --------------------------------------------------------------------------- #
# 规则选择
# --------------------------------------------------------------------------- #
def _split_spec(spec: Sequence[str] | str | None) -> list[str]:
    if spec is None:
        return []
    if isinstance(spec, str):
        return [p for p in re.split(r"[,\s]+", spec.strip()) if p]
    return [str(p).strip() for p in spec if str(p).strip()]


def resolve_rules(spec: Sequence[str] | str | None = None) -> list[str]:
    """把 ``"typo,pangu-space"`` / ``"-dup-punct"`` 这类写法解析成规则 id 列表。

    * 空 → 默认规则集（``default=True`` 的那些）
    * ``-id`` → 从结果里排除
    * 出现未知 id → 抛 ``ValueError``（由调用方转成友好提示）
    """

    parts = _split_spec(spec)
    selected = [p for p in parts if not p.startswith("-")]
    excluded = {p[1:] for p in parts if p.startswith("-")}
    unknown = sorted({p for p in selected + list(excluded) if p not in RULES})
    if unknown:
        raise ValueError(
            "未知规则 id: " + ", ".join(unknown) + "；可用规则：" + ", ".join(RULES)
        )
    ids = selected or [rid for rid, rule in RULES.items() if rule.default]
    return [rid for rid in ids if rid not in excluded]


def collect(text: str, rules: Sequence[str] | str | None = None, **opts) -> list[Edit]:
    """跑规则，返回所有 Edit（未去重、未排序）。"""

    masked = mask(text)
    edits: list[Edit] = []
    for rid in resolve_rules(rules):
        handler = _HANDLERS.get(rid)
        if handler is not None:
            edits.extend(handler(text, masked, opts))
    return edits


# --------------------------------------------------------------------------- #
# 报告
# --------------------------------------------------------------------------- #
def _locate(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_nl = text.rfind("\n", 0, offset)
    return line, offset - last_nl


def _excerpt(text: str, start: int, end: int, width: int = 18) -> str:
    a = max(0, start - width)
    b = min(len(text), end + width)
    frag = text[a:b].replace("\n", "⏎").replace(_NULL, "")
    return ("…" if a > 0 else "") + frag + ("…" if b < len(text) else "")


def _to_finding(text: str, edit: Edit) -> Finding:
    rule = RULES[edit.rule]
    line, column = _locate(text, edit.start)
    return Finding(
        rule=edit.rule,
        title=rule.title,
        severity=rule.severity,
        line=line,
        column=column,
        excerpt=_excerpt(text, edit.start, max(edit.end, edit.start + 1)),
        message=edit.message,
        suggestion=edit.replacement,
        fixable=rule.fixable and edit.replacement is not None,
    )


def check(
    text: str,
    rules: Sequence[str] | str | None = None,
    severity: str = "",
    **opts,
) -> list[Finding]:
    """检查文本，返回按位置排序的问题列表。"""

    findings = [_to_finding(text, e) for e in collect(text, rules, **opts)]
    if severity:
        want = {s.strip() for s in severity.split(",") if s.strip()}
        findings = [f for f in findings if f.severity in want]
    unique: dict[tuple, Finding] = {}
    for f in findings:
        unique.setdefault((f.rule, f.line, f.column, f.message, f.suggestion), f)
    return sorted(unique.values(), key=lambda f: (f.line, f.column, f.rule))


def fix(
    text: str,
    rules: Sequence[str] | str | None = None,
    quote_style: str = "curly",
    **opts,
) -> FixResult:
    """自动修复文本。

    * 默认只套用「安全」规则（``DEFAULT_FIX``）；
    * 如果你显式点名了某条规则（例如 ``rules="dup-punct"``），它也会被套用，
      即使它平时不在默认集合里；
    * 互相重叠的编辑只保留第一个能落地的，保证结果幂等。
    """

    opts = {**opts, "quote_style": quote_style}
    spec = _split_spec(rules)
    explicit = {p for p in spec if not p.startswith("-")}

    edits: list[Edit] = []
    for edit in collect(text, rules, **opts):
        rule = RULES[edit.rule]
        if edit.replacement is None or not rule.fixable:
            continue
        if not (rule.auto or edit.rule in explicit):
            continue
        edits.append(edit)

    # 从后往前套用：start 降序；同一位置先做替换、再做插入
    ordered = sorted(edits, key=lambda e: (-e.start, 0 if e.end > e.start else 1))
    spans: list[tuple[int, int]] = []
    seen: set[tuple[int, int, str]] = set()
    chosen: list[Edit] = []
    for edit in ordered:
        key = (edit.start, edit.end, edit.replacement or "")
        if key in seen:
            continue
        if any(not (edit.end <= s or edit.start >= t) for s, t in spans):
            continue
        seen.add(key)
        spans.append((edit.start, max(edit.end, edit.start)))
        chosen.append(edit)

    out = text
    for edit in chosen:  # chosen 已按 start 降序，倒着改不会互相影响
        out = out[: edit.start] + (edit.replacement or "") + out[edit.end:]

    changes = sorted(
        (_to_finding(text, e) for e in chosen), key=lambda f: (f.line, f.column, f.rule)
    )
    return FixResult(text=out, changes=changes)


# --------------------------------------------------------------------------- #
# 字数统计
# --------------------------------------------------------------------------- #
_PUNCT_CJK = "，。！？：；、（）「」『』“”‘’【】《》〈〉——……·～"
_READ_CHARS_PER_MIN = 300  # 精读速度（汉字 / 分钟）


def count(text: str, platforms: Sequence[str] | str | None = None) -> dict:
    """统计字词数、阅读时长，并对常见平台做字数合规检查。"""

    han = len(re.findall(f"[{_HAN}]", text))
    cjk_punct = sum(1 for ch in text if ch in _PUNCT_CJK)
    latin_letters = len(re.findall(r"[A-Za-z]", text))
    latin_words = len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text))
    digits = len(re.findall(r"[0-9]", text))
    no_space = sum(1 for ch in text if not ch.isspace())
    lines = text.splitlines()
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    sentences = [s for s in re.split(r"[。！？…]+|\n{2,}", text) if s.strip()]

    picked = None
    spec = _split_spec(platforms)
    if spec:
        picked = []
        for pid in spec:
            match = next((p for p in PLATFORMS if p["id"] == pid), None)
            if match is None:
                raise ValueError(
                    "未知平台 id: " + pid + "；可用：" + ", ".join(str(p["id"]) for p in PLATFORMS)
                )
            picked.append(match)
    platforms_out = []
    for plat in picked if picked is not None else PLATFORMS:
        limit = int(plat["limit"])  # type: ignore[arg-type]
        remain = limit - no_space
        platforms_out.append(
            {
                "id": plat["id"],
                "name": plat["name"],
                "limit": limit,
                "used": no_space,
                "remaining": remain,
                "status": "over" if remain < 0 else ("near" if remain <= limit * 0.1 else "ok"),
                "note": plat["note"],
            }
        )

    return {
        "chars_total": len(text),
        "chars_no_space": no_space,
        "han": han,
        "cjk_punctuation": cjk_punct,
        "latin_letters": latin_letters,
        "latin_words": latin_words,
        "digits": digits,
        "lines": len(lines),
        "paragraphs": len(paragraphs),
        "sentences": len(sentences),
        "reading_minutes": round(han / _READ_CHARS_PER_MIN, 1) if han else 0.0,
        "platforms": platforms_out,
    }


def rules_table() -> list[dict]:
    """给 `list_rules` 工具用的规则清单。"""

    return [
        {
            "id": r.id,
            "title": r.title,
            "severity": r.severity,
            "fixable": r.fixable,
            "auto_fix": r.auto,
            "default": r.default,
            "detail": r.detail,
        }
        for r in RULES.values()
    ]
