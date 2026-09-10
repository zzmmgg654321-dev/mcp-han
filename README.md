# mcp-han · 中文校对 MCP

> AI 写完中文，让它自己再读一遍。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-server-6E56CF.svg)](https://modelcontextprotocol.io)

**mcp-han** 是一个 [MCP](https://modelcontextprotocol.io) 服务：把「中文校对与排版」注册成模型可以直接调用的工具。
接上它，Claude / Cursor / Hermes 写完中文文案之后会自己检查、自己修，不用你再手工过一遍。

```diff
- 我们用github和deepseek api做了个工具, 结果准确率是95 %左右... 既使这样, 因该也没问题 。
+ 我们用 GitHub 和 DeepSeek API 做了个工具，结果准确率是 95%左右……即使这样，应该也没问题。
```

一行接入 · 4 个工具 · 18 条规则 · **零第三方依赖**（只用标准库 + MCP SDK）

---

## 为什么需要它

中文排版工具其实早就有：[zhlint](https://github.com/zhlint-project/zhlint)（1.0k★）、[pangu.js](https://github.com/vinta/pangu.js)（4.8k★）、[autocorrect](https://github.com/huacnlee/autocorrect)（1.6k★）。
但它们都是给**人**和 **CI** 用的：装在编辑器里、跑在命令行上，需要有人记得去按那一下。

AI 写作把这件事翻了过来——文案既然是模型写的，检查就该由模型在**交付前**自己做完。
`mcp-han` 就是这一步：不新增编辑器插件，不新增流水线，只是把中文校对变成一个模型会主动调用的工具。

和上面那些工具相比，它不试图更聪明，只求**接入成本为零、误报足够少**：

| | 谁触发 | 什么时候 |
| --- | --- | --- |
| zhlint / pangu / autocorrect | 人、编辑器、CI | 你想起来的时候 |
| **mcp-han** | 模型自己 | 每次写完中文之后 |

---

## 快速开始

### 1. 接进 Claude Desktop

`claude_desktop_config.json`（macOS：`~/Library/Application Support/Claude/`；Windows：`%APPDATA%\Claude\`）：

```json
{
  "mcpServers": {
    "mcp-han": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/zzmmgg654321-dev/mcp-han", "mcp-han"]
    }
  }
}
```

### 2. 接进 Cursor

`~/.cursor/mcp.json`（或项目里的 `.cursor/mcp.json`）写同样的内容即可，见 [`examples/`](examples/)。

### 3. 接进 Hermes

```bash
hermes mcp add mcp-han --command uvx --args --from git+https://github.com/zzmmgg654321-dev/mcp-han mcp-han
hermes mcp test mcp-han
```

### 4. 本地跑 / 开发

```bash
git clone https://github.com/zzmmgg654321-dev/mcp-han
cd mcp-han
uv run mcp-han          # 以 stdio 方式启动服务
uv run pytest           # 43 项测试（含一次真实 stdio 协议往返）
```

测试矩阵在 `.github/workflows/ci.yml`：ubuntu / windows / macOS × Python 3.10 / 3.13。

> 还没发到 PyPI，所以上面统一用 `git+https://...` 的形式安装。装成本地命令：
> `uv tool install --from git+https://github.com/zzmmgg654321-dev/mcp-han mcp-han`

---

## 四个工具

| 工具 | 干什么 | 什么时候用 |
| --- | --- | --- |
| `check_text` | 报告问题：行号、列号、上下文、修改建议 | 想先看看哪里不对，或复核 |
| `fix_text` | 直接给出修复后的全文 + 改动清单 + 仍需人工确认的地方 | 交付前一把梭 |
| `count_text` | 字数、段落、句子、预计阅读时长，以及小红书 / 公众号 / 短信 / X 的超限情况 | 卡字数的时候 |
| `list_rules` | 列出全部规则（id、级别、能否自动修、说明） | 想只跑某几条规则时 |

`check_text` 的实际输出长这样：

```text
发现 19 处问题（error 2 / warn 3 / style 14）

第 1 行 · 第 4 列 · [warn] 专有名词大小写
  「github」应写作「GitHub」
  建议：'GitHub'
  上下文：我们用github和deepseek api做了个工具…

第 6 行 · 第 4 列 · [error] 常见错别字 / 成语误写
  「既使」应为「即使」
  建议：'即使'
  上下文：…2. 既使写完了，因该也要再检查一遍…

第 7 行 · 第 11 列 · [style] 全角字母数字
  全角应写成半角：ＨＴＭＬ → HTML
  建议：'HTML'
  上下文：…3. 用了全角字符 ＨＴＭＬ 做测试…

提示：其中 19 处可以直接用 fix_text 自动修掉。
```

`fix_text` 会把清单读完的部分一次改掉，并告诉你哪些还得人来定：

```text
已修复 18 处。

【修复后的全文】
我们用 GitHub 和 DeepSeek API 做了个工具，结果准确率是 95%左右……即使这样，应该也没问题。

【改动清单】
第 1 行 · 第 4 列 · [warn] 专有名词大小写  「github」应写作「GitHub」…
…

【仍需人工确认】
第 3 行 · 第 11 列 · [warn] 引号不配对
  直引号数量是奇数，有一处没有闭合（跨行引号不会自动转换）
```

---

## 规则清单

<!-- RULES-TABLE:START -->
| 规则 id | 检查项 | 级别 | 默认 |
| --- | --- | --- | :---: |
| `typo` | 常见错别字 / 成语误写（72 条词表） | error | ✅ 自动修 |
| `latin-case` | 专有名词大小写（69 条词表） | warn | ✅ 自动修 |
| `pangu-space` | 中英文之间空格 | style | ✅ 自动修 |
| `punct-halfwidth` | 半角标点 | style | ✅ 自动修 |
| `paren-halfwidth` | 半角括号 | style | ✅ 自动修 |
| `ellipsis` | 省略号写法 | style | ✅ 自动修 |
| `dash` | 破折号写法 | style | ✅ 自动修 |
| `quote-style` | 引号风格 | style | ✅ 自动修 |
| `quote-switch` | 引号风格切换 | style | 点名才跑 |
| `fullwidth-alnum` | 全角字母数字 | style | ✅ 自动修 |
| `punct-space` | 标点前多余空格 | style | ✅ 自动修 |
| `space-after-punct` | 标点后多余空格 | style | ✅ 自动修 |
| `bracket-padding` | 括号内多余空格 | style | ✅ 自动修 |
| `percent-space` | 百分号前空格 | style | ✅ 自动修 |
| `trailing-space` | 行尾空白 | style | ✅ 自动修 |
| `dup-punct` | 重复标点 | style | 只报告 |
| `fullwidth-space` | 全角空格 | style | 只报告 |
| `unpaired-quote` | 引号不配对 | warn | 只报告 |
<!-- RULES-TABLE:END -->

这张表由 `uv run python scripts/gen_rules_table.py` 从 `RULES` 生成，改规则后跑一次即可同步，
CI 里会用 `--check` 校验它没跑偏。

**点名与排除**——所有接受 `rules` 参数的工具都支持这两种写法：

```text
rules="typo,latin-case"     # 只跑这两条
rules="-dup-punct"          # 除了它，其余全跑
rules="dup-punct"           # 平时只报告不自动修的规则，点名后 fix_text 也会改
rules="quote-switch"        # 默认关闭的规则，点名才跑
```

`fix_text` 的 `quote_style` 决定**半角直引号**变成什么：

| quote_style | 直引号 `"…"` 变成 | 已写好的中文引号 |
| --- | --- | --- |
| `curly`（默认） | `“…”` | 不动 |
| `corner` | `「…」` | 不动 |
| `keep` | 不动 | 不动 |

有意用了直角引号「」的文档不会被默认规则报错——那是一种合法风格。
要让整个文档统一换风格，点名 `quote-switch`：`fix_text(text, rules="quote-switch", quote_style="corner")`
就能把全文的 `“…”` 全换成 `「…」`（反向同理）。

---

## 三个设计取舍

**1. 绝不改你的代码。** 围栏代码块、行内代码、URL、邮箱、HTML 标签、行内公式会先被替换成同长度的占位符，
规则只在剩下的正文上跑。所以 offset / 行号 / 列号与原文严格对齐，而 `pip install xxx`、`https://a.com/x...` 这类内容一根毫毛都不会动。

**2. 一轮到位，且可重复。** 每条规则只产出「在这里替换成什么」，统一从后往前套用，重叠的编辑只留第一个。
所以 `fix(fix(x)) == fix(x)`（测试里有这条），而且它不会把 `3.5` 当成句号、不会把 `---`（Markdown 分隔线）当成破折号。

**3. 宁可不报，不要误报。** 只收高置信度的错别字词表；歧义大的专有名词（`ai`、`ui`、`os`、`go`、`node`）故意不收；
词表匹配要求真正的词边界，所以 `mcp-han`、`node.js`、`my-github-fork` 这类带连字符的名字不会被改；
「的/地/得」这类需要语义判断的一律不碰；有意使用直角引号「」的文档也不会被判成错误。
判断不了的（例如引号不配对）只报告、不自动改。

---

## 当库用

核心引擎不依赖 MCP SDK，可以当普通 Python 库用：

```python
from mcp_han import check, fix, count

result = fix("我们用github写了个工具, 结果...")
print(result.text)          # 我们用 GitHub 写了个工具，结果……
print(len(result.changes))  # 6

for item in check("因该没问题", severity="error"):
    print(item.line, item.column, item.message, "→", item.suggestion)

print(count("你好，世界。", platforms="xhs_title")["platforms"])
```

---

## 已知边界（诚实版）

* 只针对**大陆简体规范**；港台用字（如「帳號」）不在范围内，这类词条可按需删掉。
* 不检查语义错误：「的 / 地 / 得」「度过 / 渡过」这类需要上下文判断的一律不碰。
* 跨行的引号不会自动转换，只会提示你人工确认。
* 平台字数限制会变（会员等级也会放宽），脚本按**非空白字符数**估算，发布前请以平台提示为准。
* 专有名词词表是主观的：`Docker`、`Java`、`Rust` 这类写法在不同团队里标准不同，改 `src/mcp_han/data.py` 即可。

表格想改动？三张数据表（错别字、专有名词、平台限制）都在 [`src/mcp_han/data.py`](src/mcp_han/data.py)，纯数据，欢迎 PR。

---

## Roadmap

- [ ] 拼音注音（`pypinyin`）、繁简互转（`opencc`）——做成可选依赖 `mcp-han[zh]`，保持核心零依赖
- [ ] 命令行模式：`mcp-han check 文案.md`，方便接进 pre-commit
- [ ] 更多平台字数模板（知乎、B 站、抖音）
- [ ] 发布到 PyPI

---

## English

**mcp-han** is an [MCP](https://modelcontextprotocol.io) server that gives an LLM a Chinese proofreading toolkit:
spacing between CJK and Latin, half-width punctuation, common typos, proper-noun casing, quote style,
and character limits for Chinese platforms (Xiaohongshu, WeChat, SMS, X).

Why: Chinese typography linters exist (zhlint, pangu.js, autocorrect), but they are tools *humans* run.
When the model writes the Chinese, the model should check it — before handing it over.

Zero third-party dependencies (stdlib + the MCP SDK). Code blocks, inline code, URLs, emails, HTML tags and
inline math are masked out, so it never touches your code. Fixes are single-pass and idempotent.

```bash
uv run mcp-han   # stdio MCP server
uv run pytest    # 43 tests, including a real stdio handshake
```

Tools: `check_text`, `fix_text`, `count_text`, `list_rules`. Contributions to the data tables in
`src/mcp_han/data.py` are very welcome.

## 许可证

[MIT](LICENSE)
