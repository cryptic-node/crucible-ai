"""Tool package for Grokenstein.

Each tool encapsulates a set of side‑effecting operations that the assistant
may perform.  Tools should validate their inputs and avoid arbitrary
behaviour.  They are instantiated and invoked by the ``ToolBroker``.
"""

from .filesystem import FilesystemTool  # noqa: F401
from .shell import ShellTool  # noqa: F401

__all__ = [
    "FilesystemTool",
    "ShellTool",
]