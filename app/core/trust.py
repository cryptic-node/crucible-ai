from __future__ import annotations

from enum import Enum


class TrustLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    def allows_finance(self) -> bool:
        return self == TrustLevel.HIGH

    def allows_identity_change(self) -> bool:
        return self == TrustLevel.HIGH

    def allows_write(self) -> bool:
        return self in (TrustLevel.HIGH, TrustLevel.MEDIUM)

    def allows_read(self) -> bool:
        return True

    def is_read_only(self) -> bool:
        return self == TrustLevel.LOW

    @classmethod
    def from_channel(cls, channel: str) -> "TrustLevel":
        """Derive trust level from channel string."""
        channel_lower = channel.lower()
        if channel_lower in ("local", "cli", "high", "localhost"):
            return cls.HIGH
        if channel_lower in ("api", "web", "medium"):
            return cls.MEDIUM
        return cls.LOW


WORKSPACE_TRUST_DEFAULTS: dict[str, TrustLevel] = {
    "personal": TrustLevel.HIGH,
    "consulting": TrustLevel.MEDIUM,
    "experiments": TrustLevel.MEDIUM,
    "infrastructure": TrustLevel.HIGH,
}


def get_workspace_trust(workspace: str) -> TrustLevel:
    return WORKSPACE_TRUST_DEFAULTS.get(workspace, TrustLevel.LOW)
