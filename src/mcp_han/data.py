"""mcp-han 的数据表：常见错别字、专有名词大小写、平台字数限制。

这里全是纯数据，没有逻辑。如果你所在的团队有自己的规范，直接改这三张表即可，
不需要动 rules.py。欢迎 PR 扩充。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 1. 常见错别字 / 成语误写
#
#    收录原则：只收「高置信度、几乎没有歧义」的写法，宁可漏报也不要误报。
#    面向大陆简体规范；港台用字（如「帳號」）不在范围内。
# ---------------------------------------------------------------------------
TYPOS: dict[str, str] = {
    # --- 日常高频错字 ---
    "因该": "应该",
    "即然": "既然",
    "既使": "即使",
    "另人": "令人",
    "冒然": "贸然",
    "周未": "周末",
    "帐号": "账号",
    "帐户": "账户",
    "渡假": "度假",
    "按耐": "按捺",
    "寒喧": "寒暄",
    "修茸": "修葺",
    "装祯": "装帧",
    "装璜": "装潢",
    "青眯": "青睐",
    "亲睐": "青睐",
    "蜇伏": "蛰伏",
    "影牒": "影碟",
    "精萃": "精粹",
    "和霭": "和蔼",
    "脉膊": "脉搏",
    "脉落": "脉络",
    "造形": "造型",
    "照像": "照相",
    "含胡": "含糊",
    "惊谔": "惊愕",
    "气慨": "气概",
    "前题": "前提",
    "编缉": "编辑",
    "布署": "部署",
    "爆光": "曝光",
    "渲泄": "宣泄",
    "松驰": "松弛",
    "针贬": "针砭",
    # --- 成语误写 ---
    "防患未燃": "防患未然",
    "不径而走": "不胫而走",
    "重蹈复辙": "重蹈覆辙",
    "变本加利": "变本加厉",
    "不明就理": "不明就里",
    "走头无路": "走投无路",
    "迫不急待": "迫不及待",
    "谈笑风声": "谈笑风生",
    "甘败下风": "甘拜下风",
    "兴高彩烈": "兴高采烈",
    "再接再励": "再接再厉",
    "相形见拙": "相形见绌",
    "不加思索": "不假思索",
    "察颜观色": "察言观色",
    "出奇不意": "出其不意",
    "声名雀起": "声名鹊起",
    "有持无恐": "有恃无恐",
    "以逸代劳": "以逸待劳",
    "记忆尤新": "记忆犹新",
    "不记其数": "不计其数",
    "相辅相承": "相辅相成",
    "一愁莫展": "一筹莫展",
    "首曲一指": "首屈一指",
    "汗流夹背": "汗流浃背",
    "山青水秀": "山清水秀",
    "精神可佳": "精神可嘉",
    "直接了当": "直截了当",
    "不醒人事": "不省人事",
    "大名顶顶": "大名鼎鼎",
    "旁证博引": "旁征博引",
    "众口烁金": "众口铄金",
    "肆无忌殚": "肆无忌惮",
    "万事具备": "万事俱备",
    "星罗其布": "星罗棋布",
    "名符其实": "名副其实",
    "如火如茶": "如火如荼",
    "关怀倍至": "关怀备至",
    "不落巢臼": "不落窠臼",
}

# ---------------------------------------------------------------------------
# 2. 专有名词的规范大小写
#
#    键必须全小写（用 .lower() 查表）。只收「写作小写明显不规范」的词；
#    「ai / ui / os / ip / go / node / word」这类歧义太大的词故意不收，
#    否则会在英文散文或拼音注音里误伤。
# ---------------------------------------------------------------------------
LATIN_CASE_TERMS: dict[str, str] = {
    # 平台 / 产品
    "github": "GitHub",
    "gitlab": "GitLab",
    "vscode": "VS Code",
    "vs code": "VS Code",
    "iphone": "iPhone",
    "ipad": "iPad",
    "macbook": "MacBook",
    "airpods": "AirPods",
    "macos": "macOS",
    "ios": "iOS",
    "wifi": "Wi-Fi",
    "wechat": "WeChat",
    "qq": "QQ",
    "bilibili": "Bilibili",
    "weibo": "Weibo",
    "zhihu": "Zhihu",
    "taobao": "Taobao",
    "alipay": "Alipay",
    "comfyui": "ComfyUI",
    # 语言 / 框架
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "nodejs": "Node.js",
    "node js": "Node.js",
    "nextjs": "Next.js",
    "python": "Python",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "numpy": "NumPy",
    "graphql": "GraphQL",
    "markdown": "Markdown",
    "latex": "LaTeX",
    # 协议 / 术语
    "html": "HTML",
    "css": "CSS",
    "json": "JSON",
    "yaml": "YAML",
    "toml": "TOML",
    "api": "API",
    "url": "URL",
    "uri": "URI",
    "sql": "SQL",
    "http": "HTTP",
    "https": "HTTPS",
    "tcp": "TCP",
    "dns": "DNS",
    "jwt": "JWT",
    "oauth": "OAuth",
    "mcp": "MCP",
    "llm": "LLM",
    "gpt": "GPT",
    "cli": "CLI",
    "ide": "IDE",
    "pdf": "PDF",
    "csv": "CSV",
    "cdn": "CDN",
    "gpu": "GPU",
    "cpu": "CPU",
    # AI 相关
    "openai": "OpenAI",
    "chatgpt": "ChatGPT",
    "deepseek": "DeepSeek",
    "claude": "Claude",
    "midjourney": "Midjourney",
    "hugging face": "Hugging Face",
    "stable diffusion": "Stable Diffusion",
    # 基础设施
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "redis": "Redis",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
}

# ---------------------------------------------------------------------------
# 3. 常见平台的字数限制
#
#    limit 的单位是「非空白字符数」，和各家编辑器左上角的字数统计口径基本一致。
#    平台规则会变，且会员/等级可能放宽；发布前请以平台实际提示为准。
#    已核实的来源：微信公众号（标题 64 / 摘要 120 / 作者名 8 / 正文 50000）、
#    小红书（标题 20 / 正文 1000）。
# ---------------------------------------------------------------------------
PLATFORMS: list[dict[str, object]] = [
    {"id": "xhs_title", "name": "小红书标题", "limit": 20, "note": "超出会被截断"},
    {"id": "xhs_body", "name": "小红书正文", "limit": 1000, "note": "长文功能在内测中"},
    {"id": "mp_title", "name": "公众号标题", "limit": 64, "note": "列表页只显示约 30 字"},
    {"id": "mp_digest", "name": "公众号摘要", "limit": 120, "note": ""},
    {"id": "mp_author", "name": "公众号作者名", "limit": 8, "note": ""},
    {"id": "mp_body", "name": "公众号正文", "limit": 50000, "note": ""},
    {"id": "sms", "name": "单条短信", "limit": 70, "note": "70 个汉字，超出按多条计费"},
    {"id": "x_twitter", "name": "X / Twitter", "limit": 280, "note": "英文按 1 字符、中文按 2 计"},
]
