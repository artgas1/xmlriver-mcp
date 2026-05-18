"""xmlriver-mcp server entry — FastMCP over stdio.

Usage in a Claude/MCP client config (Claude Desktop, Claude Code, Cursor):

    {
      "mcpServers": {
        "xmlriver": {
          "command": "uvx",
          "args": ["xmlriver-mcp"],
          "env": {
            "XMLRIVER_USER": "<numeric_user_id>",
            "XMLRIVER_KEY": "<40-char-hex>"
          }
        }
      }
    }

Get credentials at https://xmlriver.com after registration + balance top-up.
"""

from __future__ import annotations

import logging
import sys

from fastmcp import FastMCP

logger = logging.getLogger("xmlriver-mcp")

# CRITICAL: logs must go to stderr only. stdout is reserved for JSON-RPC.
# One stray print() breaks the protocol silently — see SKILL.md anti-pattern #20.

mcp: FastMCP = FastMCP(
    name="xmlriver-mcp",
    instructions=(
        "MCP server for XMLRiver — Russian-focused SEO API providing Google and "
        "Yandex SERP parsing, Wordstat keyword frequency, and indexing checks. "
        "Use this for SEO research, competitor analysis, and keyword discovery. "
        "All tools are read-only and call live XMLRiver API (pay-as-you-go, "
        "~25 ₽ per 1000 requests on Basic tariff)."
    ),
)


def _register_tools() -> None:
    """Import tool modules so their @mcp.tool decorators register with FastMCP."""
    # Imports trigger registration via decorators
    from xmlriver_mcp.tools import (  # noqa: F401
        account,
        google,
        utility,
        wordstat,
        yandex,
    )


def main() -> None:
    """Entry point — used by the `xmlriver-mcp` console script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    _register_tools()
    logger.info("xmlriver-mcp ready (stdio transport)")
    mcp.run()


if __name__ == "__main__":
    main()
