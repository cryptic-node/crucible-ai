from __future__ import annotations

import urllib.request
import urllib.error
from typing import Any

from ..core.config import get_settings
from ..schemas.tools import WebFetchInput, ToolResult


class WebFetchTool:
    """Web fetch tool with size and timeout enforcement."""

    name = "web_fetch"

    def __init__(self) -> None:
        self.settings = get_settings()

    def fetch(self, input_data: WebFetchInput) -> ToolResult:
        url = input_data.url
        if not url.startswith(("http://", "https://")):
            return ToolResult(
                tool_name="web_fetch",
                success=False,
                error=f"Invalid URL scheme. Only http:// and https:// are allowed. Got: {url[:64]}",
            )

        if input_data.dry_run:
            return ToolResult(
                tool_name="web_fetch",
                success=True,
                output=f"[DRY RUN] Would fetch URL: {url}",
                dry_run=True,
            )

        max_bytes = input_data.max_bytes or self.settings.web_fetch_max_bytes
        timeout = input_data.timeout or self.settings.web_fetch_timeout

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Grokenstein/1.0.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")
                raw = resp.read(max_bytes)
                text = raw.decode("utf-8", errors="replace")
                truncated = len(raw) >= max_bytes
                return ToolResult(
                    tool_name="web_fetch",
                    success=True,
                    output=text,
                    metadata={
                        "url": url,
                        "content_type": content_type,
                        "bytes_read": len(raw),
                        "truncated": truncated,
                    },
                )
        except urllib.error.HTTPError as exc:
            return ToolResult(tool_name="web_fetch", success=False, error=f"HTTP {exc.code}: {exc.reason}")
        except urllib.error.URLError as exc:
            return ToolResult(tool_name="web_fetch", success=False, error=f"URL error: {exc.reason}")
        except TimeoutError:
            return ToolResult(tool_name="web_fetch", success=False, error=f"Request timed out after {timeout}s")
        except Exception as exc:
            return ToolResult(tool_name="web_fetch", success=False, error=f"Fetch error: {exc}")
