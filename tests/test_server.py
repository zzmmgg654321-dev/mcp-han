"""MCP 服务端测试。

分两层：
* 函数层——直接调工具函数，验证输出对模型友好、参数错误有友好提示；
* 协议层——真的把服务端当子进程拉起来，走一遍 MCP 的
  initialize → notifications/initialized → tools/list → tools/call，
  确保客户端接得上（而不是「函数能跑」就算完）。
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
import time

import pytest

from mcp_han import server as S

try:  # 协议版本以 SDK 为准，避免写死
    from mcp.types import LATEST_PROTOCOL_VERSION as PROTOCOL_VERSION
except Exception:  # pragma: no cover
    PROTOCOL_VERSION = "2025-06-18"


# --------------------------------------------------------------------------- #
# 函数层
# --------------------------------------------------------------------------- #
def test_check_text_reports_issues():
    out = S.check_text("我们用github写了个工具, 结果...")
    assert "发现" in out and "处问题" in out
    assert "GitHub" in out
    assert "fix_text" in out  # 提示可以自动修


def test_check_text_clean_text():
    assert "没有发现问题" in S.check_text("这是一段规范的中文。")


def test_check_text_rejects_unknown_rule():
    out = S.check_text("你好", rules="并不存在的规则")
    assert out.startswith("参数有误")
    assert "可用规则" in out


def test_fix_text_returns_full_text():
    out = S.fix_text("我们用github写了个工具, 结果...")
    assert "我们用 GitHub 写了个工具，结果……" in out
    assert "改动清单" in out


def test_fix_text_noop_is_explicit():
    out = S.fix_text("这是一段规范的中文。")
    assert "没有需要自动修复的地方" in out


def test_fix_text_quote_style():
    assert "「你好」" in S.fix_text('他说"你好"。', quote_style="corner")


def test_count_text_platforms():
    out = S.count_text("你好", platforms="xhs_title")
    assert "小红书标题" in out
    assert "20" in out


def test_count_text_unknown_platform():
    assert S.count_text("你好", platforms="某个平台").startswith("参数有误")


def test_list_rules_covers_all():
    out = S.list_rules()
    assert all(rid in out for rid in S.R.RULES)


# --------------------------------------------------------------------------- #
# 协议层：真的走一遍 stdio JSON-RPC
# --------------------------------------------------------------------------- #
class StdioClient:
    """最小可用的 MCP stdio 客户端，够测试用。"""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "mcp_han"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._next_id = 0
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def send(self, method: str, params: dict | None = None, notify: bool = False):
        message: dict = {"jsonrpc": "2.0", "method": method}
        if not notify:
            self._next_id += 1
            message["id"] = self._next_id
        if params is not None:
            message["params"] = params
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()
        if notify:
            return None
        return self._await(message["id"])

    def _await(self, want_id: int, timeout: float = 30.0) -> dict:
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"等 id={want_id} 的响应超时")
            line = self._lines.get(timeout=remaining)
            if line is None:
                assert self.proc.stderr is not None
                raise RuntimeError("服务端提前退出：" + self.proc.stderr.read()[-2000:])
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            if data.get("id") == want_id:
                return data

    def close(self) -> None:
        self.proc.kill()


@pytest.fixture
def client():
    cli = StdioClient()
    try:
        yield cli
    finally:
        cli.close()


def test_stdio_initialize_and_list_tools(client):
    init = client.send(
        "initialize",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mcp-han-tests", "version": "0"},
        },
    )
    assert init["result"]["serverInfo"]["name"] == "mcp-han"
    assert "instructions" in init["result"]

    client.send("notifications/initialized", notify=True)

    listed = client.send("tools/list", {})
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert names == {"check_text", "fix_text", "count_text", "list_rules"}
    for tool in listed["result"]["tools"]:
        assert tool["description"], f"{tool['name']} 缺少 description"
        assert "inputSchema" in tool


def test_stdio_call_fix_text(client):
    client.send(
        "initialize",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "mcp-han-tests", "version": "0"},
        },
    )
    client.send("notifications/initialized", notify=True)

    result = client.send(
        "tools/call",
        {"name": "fix_text", "arguments": {"text": "我们用github写了个工具, 结果..."}},
    )
    assert "isError" not in result or not result["isError"]
    payload = json.loads(json.dumps(result["result"], ensure_ascii=False))
    text = "".join(
        block.get("text", "") for block in payload["content"] if block.get("type") == "text"
    )
    assert "我们用 GitHub 写了个工具，结果……" in text
