"""规则引擎的测试。

一条经验：断言里写「期望的最终文本」，而不是「期望触发了哪条规则」——
排版类工具最怕的就是改动超出预期，而只有全文比对才能抓到这点。
"""

from __future__ import annotations

import pytest

from mcp_han import rules as R


# --------------------------------------------------------------------------- #
# 保护区域
# --------------------------------------------------------------------------- #
def test_mask_keeps_length_and_newlines():
    src = "第一行\n```py\ncode...\n```\n第二行..."
    masked = R.mask(src)
    assert len(masked) == len(src)
    assert masked.count("\n") == src.count("\n")


def test_fix_never_touches_code_or_urls():
    src = "看 `例子...` 和\n\n```py\nx = '中文...'\n```\n\n参考 https://a.com/x... 吧\n"
    assert R.fix(src).text == src


def test_fix_never_touches_inline_math():
    src = "公式 $a_1, b_2$ 里的逗号是半角。"
    assert R.fix(src).text == src


# --------------------------------------------------------------------------- #
# 中英文空格
# --------------------------------------------------------------------------- #
def test_pangu_inserts_space_around_latin():
    assert R.fix("在github上使用Python开发").text == "在 GitHub 上使用 Python 开发"


def test_pangu_digits_can_be_disabled():
    assert R.fix("第3章").text == "第 3 章"
    assert R.fix("第3章", space_digits=False).text == "第3章"


# --------------------------------------------------------------------------- #
# 标点
# --------------------------------------------------------------------------- #
def test_halfwidth_punctuation_becomes_fullwidth():
    assert R.fix("你好,世界!").text == "你好，世界！"


def test_decimal_and_filename_untouched():
    assert R.fix("价格是3.5元").text == "价格是 3.5 元"
    assert R.fix("打开文件.js").text == "打开文件.js"


def test_ellipsis():
    assert R.fix("等等...").text == "等等……"
    assert R.fix("等等。。。").text == "等等……"
    assert R.fix("等等…").text == "等等……"
    assert R.fix("等等……").text == "等等……"


def test_dash():
    assert R.fix("他说--其实不对").text == "他说——其实不对"
    assert R.fix("---\n标题\n---").text == "---\n标题\n---"


def test_spaces_around_chinese_punctuation():
    assert R.fix("你好 ，世界 。").text == "你好，世界。"
    assert R.fix("你好， 世界").text == "你好，世界"
    # 后面跟数字时不删空格，避免误伤「：1:2」这类写法
    assert R.fix("比例是： 1:2").text == "比例是： 1:2"


def test_bracket_padding_and_percent():
    assert R.fix("（ 内容 ）").text == "（内容）"
    assert R.fix("增长了50 %。").text == "增长了 50%。"


# --------------------------------------------------------------------------- #
# 引号
# --------------------------------------------------------------------------- #
def test_quotes_default_to_curly():
    assert R.fix('他说"你好, 世界"。').text == "他说“你好，世界”。"


def test_quote_style_switch():
    assert R.fix('他说"你好"。', quote_style="corner").text == "他说「你好」。"
    assert R.fix("他说“你好”。", quote_style="corner").text == "他说「你好」。"
    assert R.fix("他说「你好」。", quote_style="curly").text == "他说“你好”。"
    assert R.fix("他说「你好」。", quote_style="keep").text == "他说「你好」。"
    assert R.fix('He said "hello" loudly.').text == 'He said "hello" loudly.'


def test_unpaired_quote_is_reported_but_not_fixed():
    src = '他说"你好，我走了。'
    assert R.fix(src).text == src
    assert any(f.rule == "unpaired-quote" for f in R.check(src))


# --------------------------------------------------------------------------- #
# 全角 / 大小写 / 错别字
# --------------------------------------------------------------------------- #
def test_fullwidth_alnum_and_latin_case_in_one_pass():
    assert R.fix("ＡＢＣ１２３").text == "ABC123"
    # 全角 + 大小写 + 空格 一轮到位（不需要跑第二遍）
    assert R.fix("用ＧＩＴＨＵＢ管理代码").text == "用 GitHub 管理代码"


def test_latin_case():
    assert R.fix("用github和javascript写的").text == "用 GitHub 和 JavaScript 写的"


def test_typo():
    assert R.fix("既使这样，因该也没问题").text == "即使这样，应该也没问题"


def test_fullwidth_space_only_reported():
    src = "　用了全角空格缩进"
    assert R.fix(src).text == src
    assert any(f.rule == "fullwidth-space" for f in R.check(src))


def test_trailing_space():
    assert R.fix("你好   \n世界").text == "你好\n世界"


# --------------------------------------------------------------------------- #
# 稳定性与可配置性
# --------------------------------------------------------------------------- #
def test_clean_text_has_no_findings():
    assert R.check("这是一段规范的中文。没有英文，也没有数字。") == []


def test_fix_is_idempotent():
    src = '我们在github上用Javascript写了个ＡＢＣ小工具, 结果... 他说"你好"。\n\n效果不错！！   \n'
    once = R.fix(src).text
    assert R.fix(once).text == once


def test_rule_selection_and_exclusion():
    assert R.fix("因该没问题", rules="typo").text == "应该没问题"
    assert R.fix("因该没问题", rules="-typo").text == "因该没问题"
    assert R.fix("因该没问题", rules="typo,-typo").text == "因该没问题"


def test_dup_punct_only_when_explicitly_asked():
    assert R.fix("太好了！！").text == "太好了！！"
    assert R.fix("太好了！！", rules="dup-punct").text == "太好了！"


def test_unknown_rule_raises():
    with pytest.raises(ValueError):
        R.fix("随便", rules="并不存在的规则")


def test_severity_filter():
    found = R.check("因该用github", severity="error")
    assert found and all(f.severity == "error" for f in found)


def test_finding_location():
    found = [f for f in R.check("第一行\n\n你好,世界") if f.rule == "punct-halfwidth"]
    assert len(found) == 1
    assert (found[0].line, found[0].column) == (3, 3)


def test_fix_result_reports_changes():
    result = R.fix("因该没问题")
    assert result.changed
    assert result.changes[0].rule == "typo"
    assert result.changes[0].suggestion == "应该"


# --------------------------------------------------------------------------- #
# 统计与平台合规
# --------------------------------------------------------------------------- #
def test_count_text():
    stats = R.count("你好，世界。Hello!")
    assert stats["han"] == 4
    assert stats["latin_words"] == 1
    assert stats["paragraphs"] == 1
    assert stats["platforms"]


def test_count_platform_limits():
    item = R.count("你好", platforms="xhs_title")["platforms"][0]
    assert item["id"] == "xhs_title"
    assert item["limit"] == 20
    assert item["remaining"] == 18
    assert item["status"] == "ok"


def test_count_platform_over_limit():
    item = R.count("字" * 30, platforms="xhs_title")["platforms"][0]
    assert item["remaining"] == -10
    assert item["status"] == "over"


def test_count_unknown_platform_raises():
    with pytest.raises(ValueError):
        R.count("你好", platforms="并不存在的平台")


def test_rules_table_matches_handlers():
    table = {r["id"] for r in R.rules_table()}
    assert table == set(R.RULES)
    assert table == set(R._HANDLERS)
