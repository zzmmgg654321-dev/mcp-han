"""``python -m mcp_han`` 与 ``mcp-han`` 命令的入口：以 stdio 方式启动 MCP 服务。

MCP 客户端（Claude Desktop / Cursor / Hermes 等）默认就是用 stdio 拉起子进程的，
所以这里不需要任何参数。
"""

from __future__ import annotations

from .server import main

if __name__ == "__main__":
    main()
